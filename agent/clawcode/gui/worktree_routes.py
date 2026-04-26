"""FastAPI router for the local managed git-worktree runtime.

Wraps :class:`WorktreeRuntime` so the GUI can show the current worktree
status, view enter/exit history, create a new managed worktree (which
swaps the agent's cwd), and exit one (which restores the previous cwd).

Because entering swaps the active cwd, the router accepts an
``apply_cwd`` callback so it can push that change back into
:class:`AgentState`.  Without that, the agent and the worktree would
disagree about which directory it's operating in.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..worktree_runtime import VALID_EXIT_ACTIONS, WorktreeRuntime


class EnterBody(BaseModel):
    name: str | None = None


class ExitBody(BaseModel):
    action: str = 'keep'
    discard_changes: bool = False


def _serialize(runtime: WorktreeRuntime) -> dict[str, Any]:
    report = runtime.current_report()
    return {
        'status': asdict(report),
        'state_path': str(runtime.state_path),
        'history': [dict(entry) for entry in runtime.history],
        'has_state': runtime.has_state(),
    }


def create_worktree_router(
    get_cwd: Callable[[], Path],
    apply_cwd: Callable[[Path], None],
) -> APIRouter:
    router = APIRouter(prefix='/api/worktree', tags=['worktree'])

    def _runtime() -> WorktreeRuntime:
        return WorktreeRuntime.from_workspace(get_cwd())

    @router.get('')
    def status() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('/enter')
    def enter(body: EnterBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            report = runtime.enter(body.name)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        # The runtime swapped its own cwd to the new worktree; mirror that
        # back into AgentState so subsequent agent runs follow.
        if report.current_cwd:
            apply_cwd(Path(report.current_cwd))
        return _serialize(_runtime())

    @router.post('/exit')
    def exit_(body: ExitBody) -> dict[str, Any]:
        if body.action not in VALID_EXIT_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail=f'action must be one of {", ".join(VALID_EXIT_ACTIONS)}',
            )
        runtime = _runtime()
        try:
            report = runtime.exit(action=body.action, discard_changes=body.discard_changes)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if report.current_cwd:
            apply_cwd(Path(report.current_cwd))
        return _serialize(_runtime())

    return router
