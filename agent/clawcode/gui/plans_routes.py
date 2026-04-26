"""FastAPI router for the local plan runtime.

The plan runtime stores a single ordered list of steps.  Mutations are full
replaces (`update_plan`) or wipes (`clear_plan`) — there's no per-step API,
so the GUI submits the whole edited plan back on save.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..plan_runtime import PlanRuntime, VALID_PLAN_STATUSES
from ..task_runtime import TaskRuntime


class PlanStepBody(BaseModel):
    step: str = Field(min_length=1)
    status: str = 'pending'
    task_id: str | None = None
    description: str | None = None
    priority: str | None = None
    active_form: str | None = None
    owner: str | None = None
    depends_on: list[str] = Field(default_factory=list)


class PlanUpdateBody(BaseModel):
    steps: list[PlanStepBody]
    explanation: str | None = None
    sync_tasks: bool = True


class PlanClearBody(BaseModel):
    sync_tasks: bool = True


def _serialize(runtime: PlanRuntime) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for step in runtime.steps:
        counts[step.status] = counts.get(step.status, 0) + 1
    return {
        'storage_path': str(runtime.storage_path),
        'explanation': runtime.explanation,
        'updated_at': runtime.updated_at,
        'steps': [step.to_dict() for step in runtime.steps],
        'counts': {status: counts.get(status, 0) for status in VALID_PLAN_STATUSES},
    }


def create_plans_router(get_cwd: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix='/api/plan', tags=['plan'])

    def _runtime() -> PlanRuntime:
        return PlanRuntime.from_workspace(get_cwd())

    def _task_runtime() -> TaskRuntime:
        return TaskRuntime.from_workspace(get_cwd())

    @router.get('')
    def get_plan() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.put('')
    def replace_plan(body: PlanUpdateBody) -> dict[str, Any]:
        for step in body.steps:
            if step.status not in VALID_PLAN_STATUSES:
                raise HTTPException(status_code=400, detail=f'invalid status: {step.status}')
        try:
            _runtime().update_plan(
                items=[step.model_dump() for step in body.steps],
                explanation=body.explanation,
                task_runtime=_task_runtime() if body.sync_tasks else None,
                sync_tasks=body.sync_tasks,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _serialize(_runtime())

    @router.post('/clear')
    def clear_plan(body: PlanClearBody) -> dict[str, Any]:
        _runtime().clear_plan(task_runtime=_task_runtime() if body.sync_tasks else None)
        return _serialize(_runtime())

    return router
