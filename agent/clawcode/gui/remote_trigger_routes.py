"""FastAPI router for the remote-trigger runtime.

List + create + update + run remote triggers.  Triggers come either from
manifests (read-only) or from the local state file (writable).  Running a
trigger records a history row.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..remote_trigger_runtime import RemoteTriggerRuntime


class TriggerBody(BaseModel):
    trigger_id: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None
    schedule: str | None = None
    workflow: str | None = None
    remote_target: str | None = None
    body: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriggerUpdateBody(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule: str | None = None
    workflow: str | None = None
    remote_target: str | None = None
    body: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class RunTriggerBody(BaseModel):
    body: dict[str, Any] = Field(default_factory=dict)


def _serialize(runtime: RemoteTriggerRuntime) -> dict[str, Any]:
    return {
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'triggers': [asdict(t) for t in runtime.triggers],
        'history': [asdict(h) for h in runtime.history],
    }


def create_remote_trigger_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/remote-triggers', tags=['remote-triggers'])

    def _runtime() -> RemoteTriggerRuntime:
        return RemoteTriggerRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def list_triggers() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('')
    def create_trigger(body: TriggerBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            runtime.create_trigger(body.model_dump())
        except KeyError:
            raise HTTPException(status_code=409, detail=f'trigger already exists: {body.trigger_id}')
        return _serialize(_runtime())

    @router.patch('/{trigger_id}')
    def update_trigger(trigger_id: str, body: TriggerUpdateBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            runtime.update_trigger(trigger_id, body.model_dump(exclude_unset=True))
        except KeyError:
            raise HTTPException(status_code=404, detail=f'trigger not found: {trigger_id}')
        return _serialize(_runtime())

    @router.post('/{trigger_id}/run')
    def run_trigger(trigger_id: str, body: RunTriggerBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            record = runtime.run_trigger(trigger_id, body=body.body)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'trigger not found: {trigger_id}')
        return {'record': asdict(record), 'state': _serialize(_runtime())}

    return router
