"""FastAPI router for the workflow runtime.

Workflows are read-mostly: definitions come from `.claw-workflows.json` /
`.claw-workflow.json`, and `run_workflow` records a row of history.  The
GUI exposes both: list the catalog, list run history, trigger a run with
optional arguments.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..workflow_runtime import WorkflowRuntime


class RunWorkflowBody(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


def _serialize(runtime: WorkflowRuntime) -> dict[str, Any]:
    return {
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'workflows': [asdict(w) for w in runtime.workflows],
        'history': [asdict(record) for record in runtime.history],
    }


def create_workflow_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/workflows', tags=['workflows'])

    def _runtime() -> WorkflowRuntime:
        return WorkflowRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def list_workflows() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('/{name}/run')
    def run_workflow(name: str, body: RunWorkflowBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            record = runtime.run_workflow(name, arguments=body.arguments)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'workflow not found: {name}')
        return {
            'record': asdict(record),
            'state': _serialize(_runtime()),
        }

    return router
