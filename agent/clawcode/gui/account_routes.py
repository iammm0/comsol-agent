"""FastAPI router for the local account runtime.

Wraps :class:`AccountRuntime` so the GUI can browse manifest-defined
profiles, log in (named profile or ephemeral identity), check current
status, and log out.  Reads & writes the same state file the CLI uses
under ``<cwd>/.port_sessions/account_runtime.json``.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter
from pydantic import BaseModel

from ..account_runtime import AccountRuntime


class LoginBody(BaseModel):
    target: str
    provider: str | None = None
    auth_mode: str | None = None


class LogoutBody(BaseModel):
    reason: str = 'manual_logout'


def _serialize(runtime: AccountRuntime) -> dict[str, Any]:
    report = runtime.current_report()
    return {
        'status': asdict(report),
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'profiles': [asdict(p) for p in runtime.profiles],
        'history': [dict(entry) for entry in runtime.history],
    }


def create_account_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/account', tags=['account'])

    def _runtime() -> AccountRuntime:
        return AccountRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def status() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('/login')
    def login(body: LoginBody) -> dict[str, Any]:
        runtime = _runtime()
        runtime.login(body.target, provider=body.provider, auth_mode=body.auth_mode)
        return _serialize(_runtime())

    @router.post('/logout')
    def logout(body: LogoutBody) -> dict[str, Any]:
        runtime = _runtime()
        runtime.logout(reason=body.reason)
        return _serialize(_runtime())

    return router
