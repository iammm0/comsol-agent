"""
记忆 Agent：负责按会话整理用户建模指令的摘要式记忆。
- 同步入口仍保留 ``update_conversation_memory`` / ``update_conversation_memory_async`` 签名；
- 实际更新流程串联了 ``agent.clawcode_bridge`` 的 ``microcompact_history_messages`` 和
  ``summarize_history_with_compact``：先做时间窗口压缩，再把"系统自动摘要"喂给
  ``compact.format_compact_summary`` 做格式归一，最后把 ``Summary:`` 段落写回 ContextManager。
- 不再单独依赖 ContextManager.update_summary 的启发式拼接：clawcode 的 9 段式摘要更稳定，
  桌面端读到的 "系统自动摘要" 会更结构化。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.clawcode_bridge.memory import (
    microcompact_history_messages,
    summarize_history_with_compact,
)
from agent.memory.store import get_default_store
from agent.utils.config import get_settings
from agent.utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_model_name() -> str:
    settings = get_settings()
    backend = (settings.llm_backend or "").strip().lower()
    return settings.get_model_for_backend(backend) or settings.claw_code_model or ""


def _enrich_summary_via_clawcode(conversation_id: str) -> None:
    """在 ContextManager 完成基础摘要重算后，再做一次 clawcode 风格的归一化。"""

    from agent.utils.context_manager import get_context_manager

    cm = get_context_manager(conversation_id)
    summary = cm.load_summary()
    history: List[Dict[str, Any]] = cm.load_history()
    if not summary and not history:
        return

    raw_summary = ""
    if summary:
        raw_summary = "\n\n".join(
            block
            for block in (summary.auto_summary, summary.manual_summary)
            if block and block.strip()
        )
    model_name = _resolve_model_name()

    micro_result = microcompact_history_messages(history, model=model_name)
    micro_meta = {
        "triggered": micro_result.triggered,
        "cleared_tool_count": micro_result.cleared_tool_count,
        "kept_tool_count": micro_result.kept_tool_count,
        "estimated_tokens_saved": micro_result.estimated_tokens_saved,
        "gap_minutes": micro_result.gap_minutes,
    }

    compact = summarize_history_with_compact(history, raw_summary=raw_summary)
    new_auto = compact.summary or (summary.auto_summary if summary else "")
    if not new_auto:
        return

    if summary is None:
        from agent.utils.context_manager import ContextSummary

        summary = ContextSummary(
            summary=new_auto,
            last_updated=datetime.now().isoformat(),
            total_conversations=len(history),
            recent_shapes=[],
            preferences={},
            manual_summary="",
            auto_summary=new_auto,
        )
    else:
        summary.auto_summary = new_auto
        summary.last_updated = datetime.now().isoformat()
        summary.summary = cm._compose_summary_text(  # type: ignore[attr-defined]
            summary.manual_summary,
            new_auto,
        )
    cm.save_summary(summary)
    logger.debug(
        "会话 %s 摘要已通过 clawcode 压缩归一化（micro=%s）",
        conversation_id[:8] if conversation_id else "?",
        micro_meta,
    )


def update_conversation_memory(
    conversation_id: str,
    user_input: str,
    assistant_summary: str,
    success: bool = True,
) -> None:
    """更新会话的摘要记忆（同步入口）。"""

    if not conversation_id:
        return
    try:
        store = get_default_store()
        store.update_summary_sync(conversation_id)
        _enrich_summary_via_clawcode(conversation_id)
        logger.debug("会话 %s 摘要已更新", conversation_id[:8])
    except Exception as exc:
        logger.warning("更新会话记忆失败: %s", exc)


async def update_conversation_memory_async(
    conversation_id: str,
    user_input: str,
    assistant_summary: str,
    success: bool = True,
) -> None:
    """异步更新会话的摘要记忆。"""

    if not conversation_id:
        return
    store = get_default_store()
    await store.update_conversation_memory_async(
        conversation_id=conversation_id,
        user_input=user_input,
        assistant_summary=assistant_summary,
        success=success,
    )
    try:
        _enrich_summary_via_clawcode(conversation_id)
    except Exception as exc:
        logger.warning("clawcode 摘要归一化失败: %s", exc)
