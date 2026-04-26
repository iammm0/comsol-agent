"""Local release-notes parsing — Python port of utils/releaseNotes.ts.

The Python runtime has no network/cache layer, so this module only reads a
local CHANGELOG.md (typically in the project root). The npm version fetches
from GitHub and caches under ~/.claude/cache/changelog.md; here, callers
provide the changelog text or pass the project cwd so we can read it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

MAX_RELEASE_NOTES_SHOWN = 5


def parse_changelog(content: str) -> dict[str, list[str]]:
    """Parse a markdown CHANGELOG into {version: [bullet, ...]}.

    Recognises sections starting with `## <version>` (optionally followed by
    ` - YYYY-MM-DD`). Bullet lines starting with `- ` become entries.
    """
    if not content:
        return {}
    notes: dict[str, list[str]] = {}
    sections = re.split(r'^## ', content, flags=re.MULTILINE)[1:]
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        version = lines[0].split(' - ')[0].strip()
        if not version:
            continue
        bullets: list[str] = []
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith('- '):
                text = stripped[2:].strip()
                if text:
                    bullets.append(text)
        if bullets:
            notes[version] = bullets
    return notes


def _coerce_version(value: str | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?', value.strip())
    if match is None:
        return None
    return tuple(int(part) if part else 0 for part in match.groups())


def _gt(a: str, b: str) -> bool:
    parsed_a = _coerce_version(a)
    parsed_b = _coerce_version(b)
    if parsed_a is None or parsed_b is None:
        return False
    return parsed_a > parsed_b


def get_recent_release_notes(
    current_version: str,
    previous_version: str | None,
    changelog_content: str,
) -> list[str]:
    """Return up to MAX_RELEASE_NOTES_SHOWN bullets newer than previous_version."""
    notes = parse_changelog(changelog_content)
    base_current = _coerce_version(current_version)
    base_previous = _coerce_version(previous_version)
    if base_previous is not None and base_current is not None and base_current <= base_previous:
        return []
    relevant = [
        (version, bullets)
        for version, bullets in notes.items()
        if base_previous is None or _gt(version, previous_version or '0')
    ]
    relevant.sort(key=lambda item: _coerce_version(item[0]) or (), reverse=True)
    flat: list[str] = []
    for _, bullets in relevant:
        flat.extend(bullets)
    return flat[:MAX_RELEASE_NOTES_SHOWN]


def get_all_release_notes(changelog_content: str) -> list[tuple[str, list[str]]]:
    """Return all [(version, bullets)] entries sorted oldest-first."""
    notes = parse_changelog(changelog_content)
    versions = sorted(notes.keys(), key=lambda v: _coerce_version(v) or ())
    return [(version, notes[version]) for version in versions if notes[version]]


def read_local_changelog(cwd: Path) -> str:
    """Read CHANGELOG.md from the workspace root, returning '' if missing."""
    path = cwd / 'CHANGELOG.md'
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ''


def check_for_release_notes(
    current_version: str,
    last_seen_version: str | None,
    cwd: Path | None = None,
    changelog_content: str | None = None,
) -> dict:
    """Return {'hasReleaseNotes': bool, 'releaseNotes': [...]}.

    If `changelog_content` is supplied it is used directly; otherwise the
    workspace CHANGELOG.md is read. Mirrors the npm `checkForReleaseNotes`
    return shape (without the network fetch — no cache update).
    """
    content = (
        changelog_content
        if changelog_content is not None
        else read_local_changelog(cwd or Path.cwd())
    )
    bullets = get_recent_release_notes(current_version, last_seen_version, content)
    return {
        'hasReleaseNotes': bool(bullets),
        'releaseNotes': bullets,
    }


__all__ = [
    'MAX_RELEASE_NOTES_SHOWN',
    'parse_changelog',
    'get_recent_release_notes',
    'get_all_release_notes',
    'read_local_changelog',
    'check_for_release_notes',
]
