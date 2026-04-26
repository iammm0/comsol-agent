"""FastAPI router exposing the local plugin runtime for the GUI.

The plugin runtime is read-only by design: manifests are discovered from
``.claw-plugin/plugin.json``, ``.codex-plugin/plugin.json``, and
``plugins/*/plugin.json`` files relative to the workspace.  There's no
enable/disable concept — a manifest exists or it doesn't — so this router
just serves that listing for browsing.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter

from ..plugin_runtime import PluginRuntime


def _serialize_manifest(manifest: Any) -> dict[str, Any]:
    raw = asdict(manifest)
    return {
        'name': raw['name'],
        'path': raw['path'],
        'version': raw.get('version'),
        'description': raw.get('description'),
        'tool_names': raw.get('tool_names', []),
        'hook_names': raw.get('hook_names', []),
        'tool_aliases': raw.get('tool_aliases', []),
        'virtual_tools': raw.get('virtual_tools', []),
        'tool_hooks': raw.get('tool_hooks', []),
        'blocked_tools': raw.get('blocked_tools', []),
        'before_prompt': raw.get('before_prompt'),
        'after_turn': raw.get('after_turn'),
        'on_resume': raw.get('on_resume'),
        'before_persist': raw.get('before_persist'),
        'before_delegate': raw.get('before_delegate'),
        'after_delegate': raw.get('after_delegate'),
    }


def create_plugins_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/plugins', tags=['plugins'])

    def _runtime() -> PluginRuntime:
        return PluginRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def list_plugins() -> dict[str, Any]:
        runtime = _runtime()
        return {
            'manifests': [_serialize_manifest(m) for m in runtime.manifests],
            'instruction_blocks': list(runtime.instruction_blocks()),
        }

    return router
