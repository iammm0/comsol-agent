"""Session-scoped environment variables — Python port of
``utils/sessionEnvVars.ts``.

These are env vars set during a session (via the upstream ``/env`` slash
command in npm) and applied only to spawned child processes — not to the
host Python REPL/agent process itself. Bash and similar tool providers
read this map to merge into ``subprocess`` environments.

Mirrors the upstream module-level singleton: callers import the helpers
directly rather than passing a registry around.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

_session_env_vars: dict[str, str] = {}


def get_session_env_vars() -> Mapping[str, str]:
    """Return a read-only view of the current session env vars."""
    return MappingProxyType(_session_env_vars)


def set_session_env_var(name: str, value: str) -> None:
    """Set ``name=value`` for the rest of this session's child processes."""
    _session_env_vars[name] = value


def delete_session_env_var(name: str) -> None:
    """Remove ``name`` from the session env (no-op if absent)."""
    _session_env_vars.pop(name, None)


def clear_session_env_vars() -> None:
    """Drop every session-scoped env var."""
    _session_env_vars.clear()


__all__ = [
    'get_session_env_vars',
    'set_session_env_var',
    'delete_session_env_var',
    'clear_session_env_vars',
]
