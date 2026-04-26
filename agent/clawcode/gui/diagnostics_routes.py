"""FastAPI router for diagnostic commands.

Wraps the markdown-producing diagnostic helpers from :mod:`src.main` so the
GUI can show their output without shelling out to ``python -m src.main``.

These commands are read-only and have no side effects, so the router is
content-negotiation-free: each endpoint just returns the rendered text.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..bootstrap_graph import build_bootstrap_graph
from ..command_graph import build_command_graph
from ..parity_audit import run_parity_audit
from ..port_manifest import build_port_manifest
from ..query_engine import QueryEnginePort
from ..setup import run_setup
from ..tool_pool import assemble_tool_pool


# Each entry maps a diagnostic name to (label, lazy-renderer-callable).  The
# value callable is only invoked on request so the GUI listing endpoint
# stays fast even when a renderer is expensive.
_DIAGNOSTICS: dict[str, tuple[str, Callable[[], str]]] = {
    'summary': (
        'Workspace summary',
        lambda: QueryEnginePort(build_port_manifest()).render_summary(),
    ),
    'manifest': (
        'Workspace manifest',
        lambda: build_port_manifest().to_markdown(),
    ),
    'parity-audit': (
        'Parity audit (vs. archived TS)',
        lambda: run_parity_audit().to_markdown(),
    ),
    'setup-report': (
        'Setup / prefetch report',
        lambda: run_setup().as_markdown(),
    ),
    'command-graph': (
        'Command graph segmentation',
        lambda: build_command_graph().as_markdown(),
    ),
    'tool-pool': (
        'Tool pool (default settings)',
        lambda: assemble_tool_pool().as_markdown(),
    ),
    'bootstrap-graph': (
        'Bootstrap / runtime graph',
        lambda: build_bootstrap_graph().as_markdown(),
    ),
}


def create_diagnostics_router() -> APIRouter:
    router = APIRouter(prefix='/api/diagnostics', tags=['diagnostics'])

    @router.get('')
    def list_diagnostics() -> dict[str, Any]:
        return {
            'reports': [
                {'name': name, 'label': label}
                for name, (label, _) in _DIAGNOSTICS.items()
            ]
        }

    @router.get('/{name}')
    def get_diagnostic(name: str) -> dict[str, Any]:
        entry = _DIAGNOSTICS.get(name)
        if entry is None:
            raise HTTPException(status_code=404, detail=f'unknown diagnostic: {name}')
        label, renderer = entry
        try:
            content = renderer()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f'diagnostic failed: {exc}')
        return {'name': name, 'label': label, 'content': content}

    return router
