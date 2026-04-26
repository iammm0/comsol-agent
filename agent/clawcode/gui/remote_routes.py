"""FastAPI router for the local remote-profile runtime.

Same shape as the account router: list discovered profiles, connect (named
or ephemeral), check status, and disconnect.  Persists into
``<cwd>/.port_sessions/remote_runtime.json``.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter
from pydantic import BaseModel

from ..remote_runtime import RemoteRuntime


class ConnectBody(BaseModel):
    target: str
    mode: str | None = None


class DisconnectBody(BaseModel):
    reason: str = 'manual_disconnect'


def _serialize(runtime: RemoteRuntime) -> dict[str, Any]:
    report = runtime.current_report()
    return {
        'status': asdict(report),
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'profiles': [asdict(p) for p in runtime.profiles],
        'history': [dict(entry) for entry in runtime.history],
    }


def create_remote_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/remote', tags=['remote'])

    def _runtime() -> RemoteRuntime:
        return RemoteRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def status() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('/connect')
    def connect(body: ConnectBody) -> dict[str, Any]:
        runtime = _runtime()
        runtime.connect(body.target, mode=body.mode)
        return _serialize(_runtime())

    @router.post('/disconnect')
    def disconnect(body: DisconnectBody) -> dict[str, Any]:
        runtime = _runtime()
        runtime.disconnect(reason=body.reason)
        return _serialize(_runtime())

    return router
