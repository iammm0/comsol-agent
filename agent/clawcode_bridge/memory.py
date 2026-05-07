"""会话记忆压缩：把 mph-agent 的 conversation history 接到 clawcode compaction。

核心思路：
- 老的 ``agent.memory.memory_agent`` 仅触发本地"摘要重算"，没有真正"压缩"语义；
  这里复用 ``compact.format_compact_summary`` 与 ``microcompact_messages`` 把长对话
  缩成 9 段式的结构化摘要，并把超长 tool 结果折叠为占位符。
- 不要求外部 LLM 配合：``format_compact_summary`` 只是 XML 解析器，可在没有 LLM
  支持时直接传入已有摘要文本（来自现有的 SummaryAgent）做格式归一。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.clawcode.agent_session import AgentMessage
from agent.clawcode.compact import format_compact_summary, get_compact_user_summary_message
from agent.clawcode.microcompact import (
    DEFAULT_GAP_THRESHOLD_MINUTES,
    DEFAULT_KEEP_RECENT,
    MicrocompactResult,
    microcompact_messages,
)


@dataclass(frozen=True)
class CompactSummaryResult:
    """对外暴露的紧凑摘要结果。"""

    summary: str
    user_facing_message: str
    raw_input: str


def summarize_history_with_compact(
    history: List[Dict[str, Any]],
    *,
    raw_summary: str,
    transcript_path: Optional[str] = None,
) -> CompactSummaryResult:
    """把会话 history + 原始 LLM 摘要文本压缩为 ``Summary:`` 段。

    - ``raw_summary``: 上游 SummaryAgent 输出的自由文本（可能包含 ``<analysis>`` /
      ``<summary>`` XML 标签，clawcode 的 compact prompt 就是这种格式）。
    - 返回的 ``summary`` 已剥离 analysis、规范化空行；``user_facing_message``
      是建议在新会话续接时写到 system prompt 的 "previous conversation" 块。
    """

    cleaned = format_compact_summary(raw_summary or "")
    if not cleaned and history:
        # fallback：直接拼最近几条用户消息，避免摘要为空
        tails: List[str] = []
        for entry in history[-4:]:
            user_input = (entry.get("user_input") or "").strip()
            if user_input:
                tails.append(f"- {user_input[:160]}")
        if tails:
            cleaned = "Summary:\n" + "\n".join(tails)
    user_facing = get_compact_user_summary_message(
        cleaned or "Summary:\n（没有可用的历史摘要）",
        suppress_follow_up=False,
        transcript_path=transcript_path,
    )
    return CompactSummaryResult(
        summary=cleaned,
        user_facing_message=user_facing,
        raw_input=raw_summary or "",
    )


def microcompact_history_messages(
    history: List[Dict[str, Any]],
    *,
    model: str = "",
    gap_threshold_minutes: float = DEFAULT_GAP_THRESHOLD_MINUTES,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> MicrocompactResult:
    """把 mph-agent 的历史条目映射成 clawcode 消息序列后再做 microcompact。

    mph-agent 的 ``ContextManager.history.json`` 每条记录形如：
    ``{ "timestamp", "user_input", "assistant_summary", "plan", "model_path",
       "success", "error" }``，并不直接是 OpenAI message。我们这里做最小映射：
    - user_input → role=user
    - assistant_summary → role=assistant，metadata.timestamp 用于触发判定
    超长的 ``plan`` JSON 不算入 tool 结果（mph-agent 没有 tool 结果概念），
    主要利用 microcompact 的"老 assistant 文案折叠"侧效果。
    """

    messages: List[AgentMessage] = []
    for entry in history:
        ts = entry.get("timestamp")
        ts_value: Any = ts
        if isinstance(ts, str):
            ts_value = ts
        user_text = (entry.get("user_input") or "").strip()
        if user_text:
            messages.append(
                AgentMessage(
                    role="user",
                    content=user_text,
                    metadata={"timestamp": ts_value} if ts_value else {},
                )
            )
        assistant_text = (entry.get("assistant_summary") or "").strip()
        if assistant_text:
            messages.append(
                AgentMessage(
                    role="assistant",
                    content=assistant_text,
                    metadata={"timestamp": ts_value or time.time()},
                )
            )
    return microcompact_messages(
        messages,
        model=model,
        gap_threshold_minutes=gap_threshold_minutes,
        keep_recent=keep_recent,
    )
