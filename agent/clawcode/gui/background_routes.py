"""FastAPI router for the local background-session runtime.

Wraps :class:`BackgroundSessionRuntime` so the GUI can list, inspect, and
terminate detached agent runs.  The runtime roots itself at
``<cwd>/.port_sessions/background`` to match the CLI layout.

Launching a new background session from the GUI isn't wired up here yet —
that needs careful thought about which CLI flags to forward, and belongs in
a follow-up slice.  Read + logs + kill is enough to make existing background
runs observable and recoverable.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..background_runtime import (
    DEFAULT_BACKGROUND_DIR,
    BackgroundSessionRuntime,
)


def create_background_router(get_cwd: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix='/api/background', tags=['background'])

    def _runtime() -> BackgroundSessionRuntime:
        return BackgroundSessionRuntime(
            root=get_cwd().resolve() / DEFAULT_BACKGROUND_DIR
        )

    @router.get('')
    def list_background() -> dict[str, Any]:
        runtime = _runtime()
        records = runtime.list_records()
        return {
            'root': str(runtime.root),
            'sessions': [asdict(record) for record in records],
            'counts': {
                'running': sum(1 for r in records if r.status == 'running'),
                'completed': sum(1 for r in records if r.status == 'completed'),
                'failed': sum(1 for r in records if r.status == 'failed'),
                'exited': sum(1 for r in records if r.status == 'exited'),
            },
        }

    @router.get('/{background_id}')
    def get_background(background_id: str) -> dict[str, Any]:
        try:
            record = _runtime().load_record(background_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail='background session not found')
        return asdict(record)

    @router.get('/{background_id}/logs')
    def get_logs(background_id: str, tail: int | None = None) -> dict[str, Any]:
        runtime = _runtime()
        try:
            runtime.load_record(background_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail='background session not found')
        return {
            'background_id': background_id,
            'tail': tail,
            'content': runtime.read_logs(background_id, tail=tail),
        }

    @router.post('/{background_id}/kill')
    def kill_background(background_id: str) -> dict[str, Any]:
        runtime = _runtime()
        try:
            record = runtime.kill(background_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail='background session not found')
        return asdict(record)

    return router
