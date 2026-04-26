"""Bundled portable utilities — Python ports of small npm `utils/` files.

This module collects narrow, dependency-free helpers from
``utils/array.ts``, ``utils/set.ts``, ``utils/objectGroupBy.ts``,
``utils/xml.ts``, and ``utils/uuid.ts``. Keeping them in one file mirrors
how a user of the npm SDK would reach for these as a small toolbox.

Design notes:
- Function names mirror upstream where idiomatic in Python; ``every`` is
  renamed ``every_in`` to avoid shadowing the built-in name in callers.
- ``object_group_by`` returns a plain ``dict`` rather than a ``Mapping`` so
  callers can mutate it the same way the JS object would behave.
- ``create_agent_id`` mirrors the upstream format exactly:
  ``a{label-}{16 hex chars}``.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Iterable
from typing import TypeVar

A = TypeVar('A')
T = TypeVar('T')
K = TypeVar('K')


# ---------------------------------------------------------------------------
# array.ts
# ---------------------------------------------------------------------------

def intersperse(items: Iterable[A], separator: Callable[[int], A]) -> list[A]:
    """Insert ``separator(i)`` between consecutive items.

    Mirrors ``utils/array.ts`` ``intersperse``: the separator callable
    receives the 1-based index of the item it precedes.
    """
    out: list[A] = []
    for i, item in enumerate(items):
        if i:
            out.append(separator(i))
        out.append(item)
    return out


def count(items: Iterable[T], predicate: Callable[[T], object]) -> int:
    """Count items where ``predicate(item)`` is truthy."""
    return sum(1 for x in items if predicate(x))


def uniq(items: Iterable[T]) -> list[T]:
    """Return unique items preserving first-seen order.

    Note: upstream JS uses ``[...new Set(xs)]`` which preserves insertion
    order for primitive values; this matches that behavior.
    """
    seen: set[T] = set()
    out: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# objectGroupBy.ts
# ---------------------------------------------------------------------------

def object_group_by(
    items: Iterable[T],
    key_selector: Callable[[T, int], K],
) -> dict[K, list[T]]:
    """Group items by ``key_selector(item, index)``.

    Mirrors ``Object.groupBy`` semantics from the TC39 proposal.
    """
    out: dict[K, list[T]] = {}
    for index, item in enumerate(items):
        key = key_selector(item, index)
        bucket = out.get(key)
        if bucket is None:
            bucket = []
            out[key] = bucket
        bucket.append(item)
    return out


# ---------------------------------------------------------------------------
# set.ts
# ---------------------------------------------------------------------------

def difference(a: set[T], b: set[T]) -> set[T]:
    """Items in ``a`` but not ``b``."""
    return {item for item in a if item not in b}


def intersects(a: set[T], b: set[T]) -> bool:
    """Whether ``a`` and ``b`` share at least one element."""
    if not a or not b:
        return False
    return any(item in b for item in a)


def every_in(a: set[T], b: set[T]) -> bool:
    """Whether every element of ``a`` is in ``b`` (renamed from ``every``)."""
    return all(item in b for item in a)


def union(a: set[T], b: set[T]) -> set[T]:
    """Set union."""
    return a | b


# ---------------------------------------------------------------------------
# xml.ts
# ---------------------------------------------------------------------------

def escape_xml(value: str) -> str:
    """Escape ``& < >`` for safe interpolation between XML/HTML tags."""
    return value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def escape_xml_attr(value: str) -> str:
    """Escape ``& < > " '`` for safe interpolation into an attribute value."""
    return escape_xml(value).replace('"', '&quot;').replace("'", '&apos;')


# ---------------------------------------------------------------------------
# uuid.ts
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def validate_uuid(maybe_uuid: object) -> str | None:
    """Return the input as a UUID string if it matches the canonical format."""
    if not isinstance(maybe_uuid, str):
        return None
    return maybe_uuid if _UUID_RE.match(maybe_uuid) else None


def create_agent_id(label: str | None = None) -> str:
    """Generate an agent ID with the upstream ``a{label-}{hex16}`` format."""
    suffix = secrets.token_hex(8)
    return f'a{label}-{suffix}' if label else f'a{suffix}'


__all__ = [
    'intersperse',
    'count',
    'uniq',
    'object_group_by',
    'difference',
    'intersects',
    'every_in',
    'union',
    'escape_xml',
    'escape_xml_attr',
    'validate_uuid',
    'create_agent_id',
]
