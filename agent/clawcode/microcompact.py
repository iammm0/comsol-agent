"""Microcompact service — lightweight tool-result clearing for context efficiency.

Mirrors the npm ``src/services/compact/microCompact.ts`` module.

Provides time-based microcompaction: when a significant gap exists since the
last assistant message (indicating cache has expired), old tool results are
replaced with a short cleared marker to reduce context size on the next
API call.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .agent_context_usage import estimate_tokens
from .agent_session import AgentMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIME_BASED_MC_CLEARED_MESSAGE = '[Old tool result content cleared]'
"""Replacement content for cleared tool results."""

IMAGE_MAX_TOKEN_SIZE = 2000
"""Fixed token estimate for image/document blocks."""

# Tools whose results can be safely cleared during microcompaction.
COMPACTABLE_TOOLS: frozenset[str] = frozenset({
    'read_file',
    'bash',
    'grep_search',
    'glob_search',
    'web_search',
    'web_fetch',
    'edit_file',
    'write_file',
})

DEFAULT_GAP_THRESHOLD_MINUTES = 60.0
"""Minimum gap (in minutes) since the last assistant message before
time-based microcompact fires.  Mirrors the npm default."""

DEFAULT_KEEP_RECENT = 3
"""Number of most-recent compactable tool results to always preserve."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class MicrocompactResult:
    """Outcome of a microcompact pass."""

    messages: list[AgentMessage]
    cleared_tool_count: int = 0
    kept_tool_count: int = 0
    estimated_tokens_saved: int = 0
    triggered: bool = False
    gap_minutes: float = 0.0


# ---------------------------------------------------------------------------
# Time-based microcompact
# ---------------------------------------------------------------------------

def _find_last_assistant_timestamp(messages: list[AgentMessage]) -> float | None:
    """Find the timestamp of the last assistant message.

    Returns seconds since epoch, or ``None`` if no assistant message has a
    ``timestamp`` metadata entry.
    """
    for msg in reversed(messages):
        if msg.role != 'assistant':
            continue
        ts = msg.metadata.get('timestamp')
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, str):
            try:
                from datetime import datetime, timezone
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                return dt.timestamp()
            except (ValueError, TypeError):
                pass
        # Fall back to message creation time tracked by the session
        created = msg.metadata.get('created_at')
        if isinstance(created, (int, float)):
            return float(created)
    return None


def _collect_compactable_tool_ids(
    messages: list[AgentMessage],
) -> list[str]:
    """Collect tool_call_ids for tool results that can be safely cleared.

    Walks messages in order and returns IDs for tool-result messages whose
    name is in :data:`COMPACTABLE_TOOLS`.
    """
    ids: list[str] = []
    for msg in messages:
        if msg.role != 'tool':
            continue
        if not msg.tool_call_id:
            continue
        tool_name = msg.name or msg.metadata.get('tool_name', '')
        if tool_name in COMPACTABLE_TOOLS:
            ids.append(msg.tool_call_id)
    return ids


def evaluate_time_based_trigger(
    messages: list[AgentMessage],
    *,
    gap_threshold_minutes: float = DEFAULT_GAP_THRESHOLD_MINUTES,
) -> float | None:
    """Return the gap in minutes since the last assistant message, or ``None``.

    Returns ``None`` when the trigger does not fire (gap below threshold,
    no assistant messages, etc.).
    """
    ts = _find_last_assistant_timestamp(messages)
    if ts is None:
        return None
    gap_seconds = time.time() - ts
    if gap_seconds < 0:
        return None
    gap_minutes = gap_seconds / 60.0
    if gap_minutes < gap_threshold_minutes:
        return None
    return gap_minutes


def microcompact_messages(
    messages: list[AgentMessage],
    *,
    model: str = '',
    gap_threshold_minutes: float = DEFAULT_GAP_THRESHOLD_MINUTES,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> MicrocompactResult:
    """Run time-based microcompaction on session messages.

    When the gap since the last assistant message exceeds
    *gap_threshold_minutes*, old tool results (beyond the *keep_recent*
    most recent) are replaced with a short cleared marker.

    This is useful when the server-side prompt cache has expired and the
    entire prefix will be rewritten anyway — clearing old tool results
    shrinks the rewrite payload.

    Parameters
    ----------
    messages:
        The session messages to process (not mutated — new list returned).
    model:
        Model name for token estimation.
    gap_threshold_minutes:
        Minimum idle gap before trigger fires.
    keep_recent:
        Number of most-recent compactable tool results to keep.

    Returns
    -------
    MicrocompactResult
        A result containing the (possibly modified) message list and
        diagnostic counters.
    """
    gap_minutes = evaluate_time_based_trigger(
        messages, gap_threshold_minutes=gap_threshold_minutes,
    )

    if gap_minutes is None:
        return MicrocompactResult(messages=messages)

    # Collect compactable tool IDs in order
    compactable_ids = _collect_compactable_tool_ids(messages)
    if not compactable_ids:
        return MicrocompactResult(messages=messages, gap_minutes=gap_minutes)

    # Keep the most recent `keep_recent` tools untouched
    keep_count = max(1, keep_recent)
    if len(compactable_ids) <= keep_count:
        return MicrocompactResult(
            messages=messages,
            kept_tool_count=len(compactable_ids),
            gap_minutes=gap_minutes,
        )

    clear_ids = set(compactable_ids[:-keep_count])
    keep_ids = set(compactable_ids[-keep_count:])

    # Build a new message list with cleared tool results
    new_messages: list[AgentMessage] = []
    tokens_saved = 0
    cleared_count = 0

    for msg in messages:
        if (
            msg.role == 'tool'
            and msg.tool_call_id
            and msg.tool_call_id in clear_ids
        ):
            original_tokens = estimate_tokens(msg.content, model)
            replacement_tokens = estimate_tokens(TIME_BASED_MC_CLEARED_MESSAGE, model)
            tokens_saved += max(original_tokens - replacement_tokens, 0)
            cleared_count += 1

            # Create a new message with cleared content
            new_msg = AgentMessage(
                role=msg.role,
                content=TIME_BASED_MC_CLEARED_MESSAGE,
                name=msg.name,
                tool_call_id=msg.tool_call_id,
                message_id=msg.message_id,
                metadata={
                    **msg.metadata,
                    'microcompact_cleared': True,
                    'original_token_estimate': original_tokens,
                },
            )
            new_messages.append(new_msg)
        else:
            new_messages.append(msg)

    return MicrocompactResult(
        messages=new_messages,
        cleared_tool_count=cleared_count,
        kept_tool_count=len(keep_ids),
        estimated_tokens_saved=tokens_saved,
        triggered=cleared_count > 0,
        gap_minutes=gap_minutes,
    )
