"""ReasoningEngine 端的 token 预算监控。

设计目标：
- 不阻塞主流程：预算计算失败时返回 None，调用方按"无预算"语义继续推进。
- 不重复造轮子：只把 ``tokenizer_runtime`` + ``token_budget`` 包装成 mph-agent 友好的 API。
- 让 EventBus 拿到的 payload 直接可序列化（dict[str, Any]），方便桌面端展示。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agent.clawcode.agent_session import AgentMessage, AgentSessionState
from agent.clawcode.agent_types import BudgetConfig, UsageStats
from agent.clawcode.token_budget import (
    TokenBudgetSnapshot,
    calculate_token_budget,
    format_token_budget,
)
from agent.clawcode.tokenizer_runtime import describe_token_counter, count_tokens


@dataclass(frozen=True)
class BudgetSnapshot:
    """ReasoningEngine 调用 LLM 前的轻量预算快照。"""

    model: str
    prompt_tokens: int
    context_window_tokens: int
    soft_input_limit_tokens: int
    hard_input_limit_tokens: int
    exceeds_soft_limit: bool
    exceeds_hard_limit: bool
    backend: str
    accurate: bool
    raw: TokenBudgetSnapshot

    def to_event_payload(self, *, phase: str) -> Dict[str, Any]:
        return format_budget_event_payload(self, phase=phase)


def estimate_prompt_budget(
    prompt: str,
    *,
    model: str,
    extra_messages: Optional[tuple[str, ...]] = None,
) -> Optional[BudgetSnapshot]:
    """根据 prompt 文本估算一次 LLM 调用的 token 预算。

    ``extra_messages`` 可以传入历史摘要、记忆等额外正文，预算会一并算入。
    """

    if not (prompt or "").strip():
        return None

    try:
        messages: list[AgentMessage] = [AgentMessage(role="user", content=prompt)]
        for extra in extra_messages or ():
            text = (extra or "").strip()
            if not text:
                continue
            messages.append(AgentMessage(role="user", content=text))
        session = AgentSessionState(
            system_prompt_parts=(),
            messages=messages,
        )
        snapshot = calculate_token_budget(
            session=session,
            model=model,
            budget_config=BudgetConfig(),
        )
        info = describe_token_counter(model)
    except Exception:
        return None

    return BudgetSnapshot(
        model=snapshot.model,
        prompt_tokens=snapshot.projected_input_tokens,
        context_window_tokens=snapshot.context_window_tokens,
        soft_input_limit_tokens=snapshot.soft_input_limit_tokens,
        hard_input_limit_tokens=snapshot.hard_input_limit_tokens,
        exceeds_soft_limit=snapshot.exceeds_soft_limit,
        exceeds_hard_limit=snapshot.exceeds_hard_limit,
        backend=info.backend,
        accurate=info.accurate,
        raw=snapshot,
    )


def format_budget_event_payload(snapshot: BudgetSnapshot, *, phase: str) -> Dict[str, Any]:
    return {
        "phase": phase,
        "model": snapshot.model,
        "prompt_tokens": snapshot.prompt_tokens,
        "context_window_tokens": snapshot.context_window_tokens,
        "soft_input_limit_tokens": snapshot.soft_input_limit_tokens,
        "hard_input_limit_tokens": snapshot.hard_input_limit_tokens,
        "exceeds_soft_limit": snapshot.exceeds_soft_limit,
        "exceeds_hard_limit": snapshot.exceeds_hard_limit,
        "tokenizer_backend": snapshot.backend,
        "tokenizer_accurate": snapshot.accurate,
        "report": format_token_budget(snapshot.raw),
    }


def quick_count_tokens(text: str, *, model: Optional[str] = None) -> int:
    """对外暴露的同步 token 计数。"""

    if not text:
        return 0
    return count_tokens(text, model)


def usage_to_dict(usage: UsageStats) -> Dict[str, int]:
    return usage.to_dict()
