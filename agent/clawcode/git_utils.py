"""Git utility ports — subset of ``utils/git.ts`` plus ``utils/gitSettings.ts``.

This module covers the pure / filesystem-only pieces:

- ``find_git_root`` — walks up from ``start_path`` looking for ``.git``
- ``normalize_git_remote_url`` — canonicalizes SSH/HTTPS remote URLs
- ``get_repo_remote_hash`` — sha256[:16] of the normalized remote URL
- ``should_include_git_instructions`` — env-var override + settings opt-out

The shell-driven git operations (``getHead``, ``getBranch``, ``getDefaultBranch``,
``getChangedFiles``, etc.) are intentionally left for a later slice — they
need the full settings/cache plumbing the npm version uses.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Tiny LRU helper that mirrors lodash memoizeWithLRU semantics
# ---------------------------------------------------------------------------

def _lru_memoize(
    fn: Callable[[str], str | None], max_size: int,
) -> Callable[[str], str | None]:
    cache: OrderedDict[str, str | None] = OrderedDict()

    def wrapper(key: str) -> str | None:
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        value = fn(key)
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > max_size:
            cache.popitem(last=False)
        return value

    wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# find_git_root
# ---------------------------------------------------------------------------

def _find_git_root_uncached(start_path: str) -> str | None:
    current = Path(start_path).resolve()
    while True:
        git_path = current / '.git'
        try:
            stat = git_path.stat()
            if stat.st_mode and (
                git_path.is_dir() or git_path.is_file()
            ):
                return str(current)
        except OSError:
            pass
        parent = current.parent
        if parent == current:
            return None
        current = parent


find_git_root = _lru_memoize(_find_git_root_uncached, max_size=50)
"""Walk up from ``start_path`` to find the first directory containing ``.git``.

Returns the absolute path of that directory, or ``None`` if not in a repo.
Memoized per ``start_path`` with an LRU cache (max 50 entries).
"""


# ---------------------------------------------------------------------------
# normalize_git_remote_url
# ---------------------------------------------------------------------------

_SSH_RE = re.compile(r'^git@([^:]+):(.+?)(?:\.git)?$')
_URL_RE = re.compile(
    r'^(?:https?|ssh)://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?$',
)
_LOCAL_HOST_IPV4 = re.compile(r'^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$')


def _is_local_host(host: str) -> bool:
    host_no_port = host.split(':', 1)[0]
    return host_no_port == 'localhost' or bool(_LOCAL_HOST_IPV4.match(host_no_port))


def normalize_git_remote_url(url: str) -> str | None:
    """Canonicalize a git remote URL to ``host/owner/repo`` lowercased.

    Returns ``None`` if the URL doesn't match a recognized SSH/HTTPS shape.
    """
    trimmed = url.strip()
    if not trimmed:
        return None

    ssh = _SSH_RE.match(trimmed)
    if ssh:
        return f'{ssh.group(1)}/{ssh.group(2)}'.lower()

    url_match = _URL_RE.match(trimmed)
    if url_match:
        host = url_match.group(1)
        path = url_match.group(2)

        # CCR git proxy: http://...@127.0.0.1:PORT/git/[host/]owner/repo
        if _is_local_host(host) and path.startswith('git/'):
            proxy_path = path[len('git/'):]
            segments = proxy_path.split('/')
            if len(segments) >= 3 and '.' in segments[0]:
                return proxy_path.lower()
            return f'github.com/{proxy_path}'.lower()

        return f'{host}/{path}'.lower()

    return None


def get_repo_remote_hash(remote_url: str | None) -> str | None:
    """Return sha256[:16] of the normalized remote URL, or None.

    Unlike the npm version this takes the URL as a parameter rather than
    invoking ``git remote get-url`` itself, so it can be called from
    contexts where git binary access is unavailable.
    """
    if not remote_url:
        return None
    normalized = normalize_git_remote_url(remote_url)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------------------
# gitSettings.ts — env-var + settings opt-out for git instructions
# ---------------------------------------------------------------------------

_TRUTHY_ENV = frozenset({'1', 'true', 'yes', 'on'})
_FALSY_ENV = frozenset({'0', 'false', 'no', 'off'})


def _env_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_ENV


def _env_defined_falsy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _FALSY_ENV


def should_include_git_instructions(
    *,
    settings_value: bool | None = None,
    env: dict[str, str] | None = None,
) -> bool:
    """Whether to surface git-aware prompt sections.

    Mirrors ``utils/gitSettings.ts``: env var
    ``CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS`` overrides
    ``settings.includeGitInstructions``; default is ``True``.
    """
    chosen_env = env if env is not None else os.environ
    raw = chosen_env.get('CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS')
    if _env_truthy(raw):
        return False
    if _env_defined_falsy(raw):
        return True
    return True if settings_value is None else settings_value


__all__ = [
    'find_git_root',
    'normalize_git_remote_url',
    'get_repo_remote_hash',
    'should_include_git_instructions',
]
