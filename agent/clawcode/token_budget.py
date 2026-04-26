from __future__ import annotations

from dataclasses import dataclass

from .agent_context_usage import collect_context_usage, infer_context_window
from .agent_session import AgentSessionState
from .agent_types import BudgetConfig, OutputSchemaConfig
from .compact import AUTOCOMPACT_BUFFER_TOKENS


DEFAULT_OUTPUT_RESERVE_TOKENS = 4096
MIN_OUTPUT_RESERVE_TOKENS = 1024
CHAT_MESSAGE_OVERHEAD_TOKENS = 5
CHAT_TOOL_CALL_OVERHEAD_TOKENS = 12
CHAT_NAME_OVERHEAD_TOKENS = 2
OUTPUT_SCHEMA_OVERHEAD_TOKENS = 256


@dataclass(frozen=True)
class TokenBudgetSnapshot:
    model: str
    context_window_tokens: int
    projected_input_tokens: int
    message_tokens: int
    chat_overhead_tokens: int
    reserved_output_tokens: int
    reserved_compaction_buffer_tokens: int
    reserved_schema_tokens: int
    hard_input_limit_tokens: int
    soft_input_limit_tokens: int
    overflow_tokens: int
    soft_overflow_tokens: int
    exceeds_hard_limit: bool
    exceeds_soft_limit: bool
    token_counter_backend: str
    token_counter_source: str
    token_counter_accurate: bool


def calculate_token_budget(
    *,
    session: AgentSessionState,
    model: str,
    budget_config: BudgetConfig,
    output_schema: OutputSchemaConfig | None = None,
) -> TokenBudgetSnapshot:
    usage = collect_context_usage(
        session=session,
        model=model,
        strategy='token_budget',
    )
    context_window_tokens = infer_context_window(model)
    chat_overhead_tokens = estimate_chat_overhead(session)
    reserved_output_tokens = _resolve_output_reserve(
        context_window_tokens,
        budget_config,
    )
    reserved_schema_tokens = OUTPUT_SCHEMA_OVERHEAD_TOKENS if output_schema is not None else 0
    hard_input_limit_tokens = max(
        context_window_tokens - reserved_output_tokens - reserved_schema_tokens,
        0,
    )
    if budget_config.max_input_tokens is not None:
        hard_input_limit_tokens = min(
            hard_input_limit_tokens,
            max(budget_config.max_input_tokens, 0),
        )
    reserved_compaction_buffer_tokens = min(
        AUTOCOMPACT_BUFFER_TOKENS,
        max(context_window_tokens // 10, MIN_OUTPUT_RESERVE_TOKENS),
    )
    soft_input_limit_tokens = max(
        hard_input_limit_tokens - reserved_compaction_buffer_tokens,
        0,
    )
    projected_input_tokens = usage.total_tokens + chat_overhead_tokens
    overflow_tokens = max(projected_input_tokens - hard_input_limit_tokens, 0)
    soft_overflow_tokens = max(projected_input_tokens - soft_input_limit_tokens, 0)
    return TokenBudgetSnapshot(
        model=model,
        context_window_tokens=context_window_tokens,
        projected_input_tokens=projected_input_tokens,
        message_tokens=usage.total_tokens,
        chat_overhead_tokens=chat_overhead_tokens,
        reserved_output_tokens=reserved_output_tokens,
        reserved_compaction_buffer_tokens=reserved_compaction_buffer_tokens,
        reserved_schema_tokens=reserved_schema_tokens,
        hard_input_limit_tokens=hard_input_limit_tokens,
        soft_input_limit_tokens=soft_input_limit_tokens,
        overflow_tokens=overflow_tokens,
        soft_overflow_tokens=soft_overflow_tokens,
        exceeds_hard_limit=overflow_tokens > 0,
        exceeds_soft_limit=soft_overflow_tokens > 0,
        token_counter_backend=usage.token_counter_backend,
        token_counter_source=usage.token_counter_source,
        token_counter_accurate=usage.token_counter_accurate,
    )


def format_token_budget(snapshot: TokenBudgetSnapshot) -> str:
    lines = [
        '# Token Budget',
        '',
        f'- Model: {snapshot.model}',
        f'- Context window: {snapshot.context_window_tokens:,}',
        f'- Prompt tokens: {snapshot.projected_input_tokens:,}',
        f'- Message/body tokens: {snapshot.message_tokens:,}',
        f'- Chat framing overhead: {snapshot.chat_overhead_tokens:,}',
        f'- Reserved output tokens: {snapshot.reserved_output_tokens:,}',
        f'- Reserved schema tokens: {snapshot.reserved_schema_tokens:,}',
        f'- Auto-compact buffer: {snapshot.reserved_compaction_buffer_tokens:,}',
        f'- Hard input limit: {snapshot.hard_input_limit_tokens:,}',
        f'- Soft input limit: {snapshot.soft_input_limit_tokens:,}',
        f'- Token counter: {snapshot.token_counter_backend} ({snapshot.token_counter_source})'
        + (' [accurate]' if snapshot.token_counter_accurate else ' [fallback]'),
    ]
    if snapshot.exceeds_hard_limit:
        lines.append(f'- Hard overflow: {snapshot.overflow_tokens:,}')
    elif snapshot.exceeds_soft_limit:
        lines.append(f'- Soft overflow: {snapshot.soft_overflow_tokens:,}')
    else:
        remaining = max(snapshot.soft_input_limit_tokens - snapshot.projected_input_tokens, 0)
        lines.append(f'- Remaining soft headroom: {remaining:,}')
    return '\n'.join(lines)


def estimate_chat_overhead(session: AgentSessionState) -> int:
    total = 0
    for message in session.messages:
        total += CHAT_MESSAGE_OVERHEAD_TOKENS
        if message.name:
            total += CHAT_NAME_OVERHEAD_TOKENS
        total += len(message.tool_calls) * CHAT_TOOL_CALL_OVERHEAD_TOKENS
    return total + 3


def _resolve_output_reserve(
    context_window_tokens: int,
    budget_config: BudgetConfig,
) -> int:
    if budget_config.max_output_tokens is not None:
        return max(budget_config.max_output_tokens, 0)
    suggested = min(DEFAULT_OUTPUT_RESERVE_TOKENS, max(context_window_tokens // 16, MIN_OUTPUT_RESERVE_TOKENS))
    return suggested
