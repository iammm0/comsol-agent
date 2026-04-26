"""Display formatters — Python port of pure helpers from ``utils/format.ts``.

Only the leaf-safe formatters are ported here (no Intl dependencies, no
Ink-specific layout). These mirror the upstream output exactly so existing
golden snapshots and tests of formatted strings stay aligned.

Ported:
- ``format_file_size`` — bytes → ``"1.5KB"`` / ``"2MB"`` / ``"3.4GB"``
- ``format_seconds_short`` — ms → ``"1.2s"``
- ``format_duration`` — ms → ``"3h 4m 5s"`` with hide/most-significant flags
- ``format_number`` — compact notation (``"1.3k"``, ``"2.5m"``)
- ``format_tokens`` — like ``format_number`` but trims trailing ``.0``

Not ported (stay in TypeScript-only paths):
``formatRelativeTime`` / ``formatRelativeTimeAgo`` / ``formatLogMetadata``
/ ``formatResetTime`` / ``formatResetText`` — they depend on
``intl.ts`` and the Ink reset-time UX.
"""

from __future__ import annotations


def _trim_trailing_zero(value: str) -> str:
    return value[:-2] if value.endswith('.0') else value


def format_file_size(size_in_bytes: float) -> str:
    """Bytes to a human-readable string, mirroring the JS thresholds."""
    kb = size_in_bytes / 1024
    if kb < 1:
        return f'{int(size_in_bytes)} bytes'
    if kb < 1024:
        return f'{_trim_trailing_zero(f"{kb:.1f}")}KB'
    mb = kb / 1024
    if mb < 1024:
        return f'{_trim_trailing_zero(f"{mb:.1f}")}MB'
    gb = mb / 1024
    return f'{_trim_trailing_zero(f"{gb:.1f}")}GB'


def format_seconds_short(ms: float) -> str:
    """Milliseconds → ``"1.2s"`` (always one decimal)."""
    return f'{ms / 1000:.1f}s'


def format_duration(
    ms: float,
    *,
    hide_trailing_zeros: bool = False,
    most_significant_only: bool = False,
) -> str:
    """Format a millisecond duration with d/h/m/s components.

    Mirrors ``utils/format.ts#formatDuration`` including the rounding
    carry-over (``59.5s`` rounds up to the next minute).
    """
    if ms < 60_000:
        if ms == 0:
            return '0s'
        if ms < 1:
            return f'{ms / 1000:.1f}s'
        return f'{int(ms // 1000)}s'

    days = int(ms // 86_400_000)
    hours = int((ms % 86_400_000) // 3_600_000)
    minutes = int((ms % 3_600_000) // 60_000)
    seconds = int(round((ms % 60_000) / 1000))

    if seconds == 60:
        seconds = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        hours += 1
    if hours == 24:
        hours = 0
        days += 1

    if most_significant_only:
        if days > 0:
            return f'{days}d'
        if hours > 0:
            return f'{hours}h'
        if minutes > 0:
            return f'{minutes}m'
        return f'{seconds}s'

    hide = hide_trailing_zeros

    if days > 0:
        if hide and hours == 0 and minutes == 0:
            return f'{days}d'
        if hide and minutes == 0:
            return f'{days}d {hours}h'
        return f'{days}d {hours}h {minutes}m'
    if hours > 0:
        if hide and minutes == 0 and seconds == 0:
            return f'{hours}h'
        if hide and seconds == 0:
            return f'{hours}h {minutes}m'
        return f'{hours}h {minutes}m {seconds}s'
    if minutes > 0:
        if hide and seconds == 0:
            return f'{minutes}m'
        return f'{minutes}m {seconds}s'
    return f'{seconds}s'


_COMPACT_SUFFIXES = (
    (1_000_000_000_000, 't'),
    (1_000_000_000, 'b'),
    (1_000_000, 'm'),
    (1_000, 'k'),
)


def format_number(number: float) -> str:
    """Compact notation matching ``Intl.NumberFormat`` with one fraction digit.

    The npm version emits e.g. ``"1.3k"`` from 1321 and ``"900"`` from 900.
    For values < 1000 the integer is returned with no separator. For larger
    values one fraction digit is shown when ``number >= 1000`` to mirror the
    ``minimumFractionDigits: 1`` consistent-decimal branch.
    """
    if number < 1000:
        return str(int(number))

    for threshold, suffix in _COMPACT_SUFFIXES:
        if number >= threshold:
            scaled = number / threshold
            return f'{scaled:.1f}{suffix}'

    return str(int(number))


def format_tokens(count: float) -> str:
    """Like ``format_number`` but trims a trailing ``.0`` (e.g. ``"1k"``)."""
    return format_number(count).replace('.0', '')


__all__ = [
    'format_file_size',
    'format_seconds_short',
    'format_duration',
    'format_number',
    'format_tokens',
]
