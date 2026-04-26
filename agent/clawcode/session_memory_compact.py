"""Session-memory-based compaction — uses an on-disk session memory summary
instead of an API call to compact the conversation.

Mirrors the npm ``src/services/compact/sessionMemoryCompact.ts`` module.

When session memory is available and up-to-date, this avoids the cost
of an API round-trip by reusing the background-maintained summary as
the compaction text.  Falls back to ``None`` so the caller can use
the legacy API-based compact instead.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .agent_context_usage import estimate_tokens
from .agent_session import AgentMessage

if TYPE_CHECKING:
    from .compact import CompactionResult

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SessionMemoryCompactConfig:
    """Configuration for session-memory compaction thresholds."""

    min_tokens: int = 10_000
    """Minimum tokens to preserve after compaction."""

    min_text_block_messages: int = 5
    """Minimum number of messages with text content to keep."""

    max_tokens: int = 40_000
    """Hard cap — never preserve more than this many tokens."""

    max_section_tokens: int = 2_000
    """Maximum tokens per section in the session memory."""

    max_total_tokens: int = 12_000
    """Maximum total tokens for the session memory summary."""


DEFAULT_CONFIG = SessionMemoryCompactConfig()

# ---------------------------------------------------------------------------
# Session memory file management
# ---------------------------------------------------------------------------

SESSION_MEMORY_TEMPLATE_SECTIONS = (
    '## User Profile',
    '## Project Context',
    '## Key Decisions & Rationale',
    '## Current Task Context',
    '## Important Patterns & Preferences',
    '## Learned Corrections',
    '## Tool Usage Patterns',
    '## Conversation Flow',
    '## Open Questions & Uncertainties',
)
"""Section headers used in the session memory template."""


def get_session_memory_dir() -> Path:
    """Return the directory where session memory files are stored."""
    home = Path.home()
    return home / '.claude' / 'session-memory'


def get_session_memory_path() -> Path:
    """Return the path to the session memory file."""
    return get_session_memory_dir() / 'session.md'


def load_session_memory() -> str | None:
    """Load session memory from disk, returning None if absent or empty."""
    path = get_session_memory_path()
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding='utf-8').strip()
        if not content:
            return None
        return content
    except (OSError, UnicodeDecodeError):
        return None


def save_session_memory(content: str) -> None:
    """Save session memory to disk."""
    path = get_session_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def is_template_only(content: str) -> bool:
    """Check if the session memory is just the empty template.

    Returns True if all sections are present but contain no real content
    beyond the template headers and italic descriptions.
    """
    lines = content.strip().splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip section headers
        if stripped.startswith('##'):
            continue
        # Skip italic template descriptions
        if stripped.startswith('*') and stripped.endswith('*'):
            continue
        if stripped.startswith('_') and stripped.endswith('_'):
            continue
        # Found non-template content
        return False
    return True


# ---------------------------------------------------------------------------
# Message analysis helpers
# ---------------------------------------------------------------------------

def _has_text_content(msg: AgentMessage) -> bool:
    """Check if a message has meaningful text content."""
    content = msg.content.strip()
    if not content:
        return False
    if content == '[Old tool result content cleared]':
        return False
    return True


def _get_tool_result_ids(msg: AgentMessage) -> list[str]:
    """Extract tool_call_ids from a tool-result message."""
    if msg.role == 'tool' and msg.tool_call_id:
        return [msg.tool_call_id]
    return []


def _has_tool_use_with_ids(msg: AgentMessage, ids: set[str]) -> bool:
    """Check if an assistant message contains tool_use blocks matching any of the given IDs."""
    if msg.role != 'assistant':
        return False
    tool_calls = msg.metadata.get('tool_calls') or msg.tool_calls
    if not tool_calls:
        return False
    for tc in tool_calls:
        tc_id = tc.get('id', '') if isinstance(tc, dict) else ''
        if tc_id in ids:
            return True
    return False


# ---------------------------------------------------------------------------
# Index calculation
# ---------------------------------------------------------------------------

def adjust_index_to_preserve_api_invariants(
    messages: list[AgentMessage],
    keep_from: int,
) -> int:
    """Walk backwards to ensure kept messages maintain API-valid structure.

    Specifically:
    1. All tool_result messages must have corresponding tool_use messages.
    2. Assistant messages sharing the same message_id (thinking blocks)
       must be kept together.
    """
    if keep_from <= 0:
        return 0

    # Step 1: Ensure tool_use/tool_result pairs
    kept_tool_result_ids: set[str] = set()
    for msg in messages[keep_from:]:
        for tid in _get_tool_result_ids(msg):
            kept_tool_result_ids.add(tid)

    if kept_tool_result_ids:
        idx = keep_from - 1
        while idx >= 0:
            msg = messages[idx]
            if _has_tool_use_with_ids(msg, kept_tool_result_ids):
                keep_from = idx
                # Include any new tool_results this brings in
                for m in messages[idx:keep_from]:
                    for tid in _get_tool_result_ids(m):
                        kept_tool_result_ids.add(tid)
            idx -= 1

    # Step 2: Ensure thinking block continuity (same message_id)
    kept_msg_ids: set[str] = set()
    for msg in messages[keep_from:]:
        if msg.role == 'assistant' and msg.message_id:
            kept_msg_ids.add(msg.message_id)

    if kept_msg_ids:
        idx = keep_from - 1
        while idx >= 0:
            msg = messages[idx]
            if msg.role == 'assistant' and msg.message_id in kept_msg_ids:
                keep_from = idx
            idx -= 1

    return keep_from


def calculate_messages_to_keep_index(
    messages: list[AgentMessage],
    last_summarized_index: int,
    model: str = '',
    config: SessionMemoryCompactConfig | None = None,
) -> int:
    """Calculate the index from which to preserve messages.

    Starts from ``last_summarized_index + 1`` and expands backwards
    to meet the configured minimums (token count, text block count).
    Stops if the hard max_tokens cap is reached.
    """
    if config is None:
        config = DEFAULT_CONFIG

    start_index = last_summarized_index + 1
    if start_index >= len(messages):
        return len(messages)

    keep_from = start_index
    token_count = 0
    text_block_count = 0

    # Count forward from keep_from to end
    for msg in messages[keep_from:]:
        token_count += estimate_tokens(msg.content, model)
        if _has_text_content(msg):
            text_block_count += 1

    # Expand backwards if minimums not met
    idx = keep_from - 1
    while idx >= 0:
        # Check if we've reached a compact boundary — don't go past it
        if messages[idx].metadata.get('kind') == 'compact_boundary':
            break

        msg_tokens = estimate_tokens(messages[idx].content, model)

        # Hard cap: stop if adding this would exceed max_tokens
        if token_count + msg_tokens > config.max_tokens:
            break

        # Expand backwards
        keep_from = idx
        token_count += msg_tokens
        if _has_text_content(messages[idx]):
            text_block_count += 1

        # Check if minimums are met
        if (token_count >= config.min_tokens
                and text_block_count >= config.min_text_block_messages):
            break

        idx -= 1

    # Ensure API invariants
    keep_from = adjust_index_to_preserve_api_invariants(messages, keep_from)

    return keep_from


# ---------------------------------------------------------------------------
# Session memory truncation
# ---------------------------------------------------------------------------

def truncate_session_memory(
    content: str,
    config: SessionMemoryCompactConfig | None = None,
) -> tuple[str, bool]:
    """Truncate session memory sections to fit within token limits.

    Returns ``(truncated_content, was_truncated)``.
    """
    if config is None:
        config = DEFAULT_CONFIG

    total_tokens = estimate_tokens(content, '')
    if total_tokens <= config.max_total_tokens:
        return content, False

    # Split by section headers and truncate each
    lines = content.splitlines(keepends=True)
    sections: list[list[str]] = []
    current_section: list[str] = []

    for line in lines:
        if line.strip().startswith('## ') and current_section:
            sections.append(current_section)
            current_section = [line]
        else:
            current_section.append(line)
    if current_section:
        sections.append(current_section)

    truncated_sections: list[str] = []
    was_truncated = False

    for section in sections:
        section_text = ''.join(section)
        section_tokens = estimate_tokens(section_text, '')
        if section_tokens > config.max_section_tokens:
            # Truncate to fit within section limit
            truncated_lines: list[str] = []
            running_tokens = 0
            for line in section:
                line_tokens = estimate_tokens(line, '')
                if running_tokens + line_tokens > config.max_section_tokens:
                    truncated_lines.append('...(truncated)\n')
                    was_truncated = True
                    break
                truncated_lines.append(line)
                running_tokens += line_tokens
            truncated_sections.append(''.join(truncated_lines))
        else:
            truncated_sections.append(section_text)

    result = ''.join(truncated_sections)

    # Check total again
    if estimate_tokens(result, '') > config.max_total_tokens:
        was_truncated = True

    return result, was_truncated


# ---------------------------------------------------------------------------
# Core session memory compaction
# ---------------------------------------------------------------------------

def try_session_memory_compaction(
    messages: list[AgentMessage],
    model: str = '',
    last_summarized_message_id: str | None = None,
    auto_compact_threshold: int | None = None,
    config: SessionMemoryCompactConfig | None = None,
) -> 'CompactionResult | None':
    """Attempt session-memory-based compaction.

    Returns a :class:`CompactionResult` if session memory is available
    and the compaction succeeds, or ``None`` to signal the caller should
    fall back to API-based compaction.

    Parameters
    ----------
    messages:
        The current session messages.
    model:
        Model name for token estimation.
    last_summarized_message_id:
        The message_id of the last message that was included in the
        session memory summary.  Messages after this are preserved.
    auto_compact_threshold:
        If provided, return None if post-compact tokens exceed this.
    config:
        Compaction configuration thresholds.
    """
    from .compact import CompactionResult

    if config is None:
        config = DEFAULT_CONFIG

    # Check environment gates
    if os.environ.get('DISABLE_CLAUDE_CODE_SM_COMPACT'):
        return None

    # Load session memory
    session_memory = load_session_memory()
    if session_memory is None:
        return None

    if is_template_only(session_memory):
        return None

    # Find the boundary message
    last_summarized_index: int | None = None

    if last_summarized_message_id:
        for i, msg in enumerate(messages):
            if msg.message_id == last_summarized_message_id:
                last_summarized_index = i
                break

    if last_summarized_index is None:
        # No boundary found — can't determine what's already summarized
        # Fall back to legacy compact
        return None

    # Calculate which messages to preserve
    keep_from = calculate_messages_to_keep_index(
        messages, last_summarized_index, model=model, config=config,
    )

    messages_to_keep = list(messages[keep_from:])

    # Filter out old compact boundaries from kept messages
    messages_to_keep = [
        m for m in messages_to_keep
        if m.metadata.get('kind') != 'compact_boundary'
    ]

    # Truncate session memory if needed
    truncated_memory, was_truncated = truncate_session_memory(
        session_memory, config=config,
    )

    # Build the compaction result
    pre_tokens = sum(estimate_tokens(m.content, model) for m in messages)

    boundary = AgentMessage(
        role='user',
        content=(
            '<system-reminder>\n'
            f'Earlier conversation was compacted using session memory. '
            f'{len(messages) - len(messages_to_keep)} messages summarized.\n'
            '</system-reminder>'
        ),
        message_id='compact_boundary',
        metadata={
            'kind': 'compact_boundary',
            'source': 'session_memory',
            'pre_compact_token_count': pre_tokens,
        },
    )

    summary_content = (
        'Here is a summary of our conversation so far:\n\n'
        f'{truncated_memory}'
    )
    if was_truncated:
        memory_path = get_session_memory_path()
        summary_content += (
            f'\n\n(Session memory was truncated. '
            f'Full version at: {memory_path})'
        )

    summary_msg = AgentMessage(
        role='user',
        content=summary_content,
        message_id='compact_summary',
        metadata={
            'kind': 'compact_summary',
            'is_compact_summary': True,
            'source': 'session_memory',
        },
    )

    post_messages = [boundary, summary_msg] + messages_to_keep
    post_tokens = sum(estimate_tokens(m.content, model) for m in post_messages)

    # Check threshold
    if auto_compact_threshold is not None and post_tokens > auto_compact_threshold:
        return None

    return CompactionResult(
        boundary_message=boundary,
        summary_messages=[summary_msg],
        messages_to_keep=messages_to_keep,
        pre_compact_token_count=pre_tokens,
        post_compact_token_count=post_tokens,
        true_post_compact_token_count=post_tokens,
        summary_text=truncated_memory,
    )


# ---------------------------------------------------------------------------
# Session memory extraction (lightweight background summary updater)
# ---------------------------------------------------------------------------

SESSION_MEMORY_EXTRACTION_PROMPT = """Analyze the conversation so far and update the session memory.
Extract key information into these sections:

## User Profile
Who the user is, their role, expertise level, and preferences.

## Project Context
What project/codebase is being worked on, its structure, and tech stack.

## Key Decisions & Rationale
Important decisions made during this session and why.

## Current Task Context
What the user is currently working on and the state of that work.

## Important Patterns & Preferences
Coding style, conventions, or preferences observed.

## Learned Corrections
Mistakes made and corrections applied — things to avoid repeating.

## Tool Usage Patterns
Which tools work well, preferred approaches for common tasks.

## Conversation Flow
Major topic transitions and how the conversation has progressed.

## Open Questions & Uncertainties
Unresolved questions or areas of ambiguity.

Write concisely. Focus on information that would be useful for continuing
this conversation after a context reset. Omit sections with no content."""


def extract_session_memory_from_messages(
    messages: list[AgentMessage],
    model: str = '',
) -> str:
    """Build a session memory summary from conversation messages.

    This is a lightweight local extraction — it walks the messages and
    builds a structured summary without an API call.  For richer
    summaries, the full LLM-based extraction should be used.
    """
    user_messages: list[str] = []
    tool_names_used: set[str] = set()
    file_paths: set[str] = set()
    corrections: list[str] = []

    for msg in messages:
        if msg.role == 'user' and _has_text_content(msg):
            user_messages.append(msg.content[:200])
        elif msg.role == 'tool' and msg.name:
            tool_names_used.add(msg.name)
            path = msg.metadata.get('path')
            if isinstance(path, str):
                file_paths.add(path)

    sections: list[str] = []

    if user_messages:
        sections.append('## Current Task Context')
        # Use recent user messages as task context
        recent = user_messages[-5:]
        for um in recent:
            sections.append(f'- {um[:100]}')

    if tool_names_used:
        sections.append('\n## Tool Usage Patterns')
        sections.append(f'Tools used: {", ".join(sorted(tool_names_used))}')

    if file_paths:
        sections.append('\n## Project Context')
        sections.append(f'Files accessed: {", ".join(sorted(list(file_paths)[:20]))}')

    sections.append('\n## Conversation Flow')
    sections.append(f'Total messages: {len(messages)}')
    sections.append(
        f'User messages: {sum(1 for m in messages if m.role == "user")}'
    )

    return '\n'.join(sections)
