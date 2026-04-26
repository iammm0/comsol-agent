"""Pasted-content reference parsing, formatting, and expansion.

Mirrors the small surface of the npm ``src/history.ts`` paste handling that's
actually useful for a programmatic / GUI front-end:

* short ``[Pasted text #N]`` / ``[Pasted text #N +M lines]`` refs returned to
  the user when they paste a large blob,
* a parser that finds those refs in a prompt,
* an expander that splices the original content back in before the agent runs.

The npm runtime additionally persists pasted text under a content hash and
ships full prompt-history with up-arrow recall.  Both are TUI-specific and
out of scope here; the in-memory ``PastedContent`` dict the GUI maintains per
chat is enough for our purposes.

Image pastes are intentionally out of scope: vision-model framing belongs in a
later slice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


REFERENCE_PATTERN = re.compile(
    r'\[(?:Pasted text|Image|\.\.\.Truncated text) #(\d+)(?: \+\d+ lines)?(?:\.)*\]'
)


@dataclass(frozen=True)
class PastedContent:
    """A single pasted blob the front-end is keeping around for the next turn."""

    id: int
    type: str  # 'text' or 'image' (image kept for forward-compatibility only)
    content: str
    media_type: str | None = None
    filename: str | None = None


@dataclass(frozen=True)
class ParsedReference:
    """One paste reference found inside a prompt string."""

    id: int
    match: str
    index: int


def get_pasted_text_ref_num_lines(text: str) -> int:
    """Return the line-count suffix for ``[Pasted text #N +M lines]``.

    Matches the npm convention: ``"a\\nb\\nc"`` reports ``+2``, not ``+3``.
    """
    return len(re.findall(r'\r\n|\r|\n', text))


def format_pasted_text_ref(ref_id: int, num_lines: int) -> str:
    if num_lines == 0:
        return f'[Pasted text #{ref_id}]'
    return f'[Pasted text #{ref_id} +{num_lines} lines]'


def format_image_ref(ref_id: int) -> str:
    return f'[Image #{ref_id}]'


def parse_references(text: str) -> list[ParsedReference]:
    """Find every ``[Pasted text #N ...]`` / ``[Image #N]`` reference."""
    refs: list[ParsedReference] = []
    for match in REFERENCE_PATTERN.finditer(text):
        ref_id = int(match.group(1))
        if ref_id <= 0:
            continue
        refs.append(
            ParsedReference(id=ref_id, match=match.group(0), index=match.start())
        )
    return refs


def expand_pasted_text_refs(
    text: str,
    pasted_contents: Mapping[int, PastedContent],
) -> str:
    """Replace ``[Pasted text #N]`` placeholders with their stored content.

    Image references are deliberately left alone — they would become content
    blocks rather than inline text, and that path isn't wired up yet.
    """
    refs = parse_references(text)
    expanded = text
    # Splice from the back so earlier offsets stay valid after later edits.
    for ref in reversed(refs):
        content = pasted_contents.get(ref.id)
        if content is None or content.type != 'text':
            continue
        expanded = (
            expanded[: ref.index]
            + content.content
            + expanded[ref.index + len(ref.match) :]
        )
    return expanded


__all__ = [
    'PastedContent',
    'ParsedReference',
    'expand_pasted_text_refs',
    'format_image_ref',
    'format_pasted_text_ref',
    'get_pasted_text_ref_num_lines',
    'parse_references',
]
