"""FastAPI router for the local task runtime.

The router reads a fresh :class:`TaskRuntime` per request via
:meth:`TaskRuntime.from_workspace` so the GUI always reflects what's actually
on disk — agents and slash commands write to the same file, so caching here
would silently desync the view.

Mutations call back into the runtime's existing methods so persistence,
ordering, and "complete unblocks dependents" semantics stay identical to the
slash-command path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..task import VALID_TASK_STATUSES
from ..task_runtime import TaskRuntime


class CreateTaskBody(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    status: str = 'pending'
    priority: str | None = None
    active_form: str | None = None
    owner: str | None = None
    blocks: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateTaskBody(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    active_form: str | None = None
    owner: str | None = None
    blocks: list[str] | None = None
    blocked_by: list[str] | None = None
    metadata: dict[str, Any] | None = None
    merge_metadata: bool = False


class CancelBody(BaseModel):
    reason: str | None = None


class BlockBody(BaseModel):
    blocked_by: list[str] | None = None
    reason: str | None = None


def _serialize_runtime(runtime: TaskRuntime) -> dict[str, Any]:
    tasks = runtime.list_tasks()
    next_ids = {t.task_id for t in runtime.next_tasks(limit=None)}
    return {
        'storage_path': str(runtime.storage_path),
        'tasks': [
            {**task.to_dict(), 'is_next_actionable': task.task_id in next_ids}
            for task in tasks
        ],
        'counts': {
            status: sum(1 for t in tasks if t.status == status)
            for status in VALID_TASK_STATUSES
        },
    }


def create_tasks_router(get_cwd: Callable[[], Path]) -> APIRouter:
    """Build the router; ``get_cwd`` returns the latest workspace dir.

    The cwd is fetched per-request rather than captured in a closure so that
    saving a new working directory in the settings panel reroutes the task
    view immediately.
    """
    router = APIRouter(prefix='/api/tasks', tags=['tasks'])

    def _runtime() -> TaskRuntime:
        return TaskRuntime.from_workspace(get_cwd())

    @router.get('')
    def list_tasks() -> dict[str, Any]:
        return _serialize_runtime(_runtime())

    @router.post('')
    def create_task(body: CreateTaskBody) -> dict[str, Any]:
        if body.status not in VALID_TASK_STATUSES:
            raise HTTPException(status_code=400, detail=f'invalid status: {body.status}')
        try:
            mutation = _runtime().create_task(**body.model_dump())
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            'task': mutation.task.to_dict() if mutation.task else None,
            'state': _serialize_runtime(_runtime()),
        }

    @router.patch('/{task_id}')
    def update_task(task_id: str, body: UpdateTaskBody) -> dict[str, Any]:
        kwargs = body.model_dump(exclude_unset=True)
        if 'status' in kwargs and kwargs['status'] not in VALID_TASK_STATUSES:
            raise HTTPException(status_code=400, detail=f'invalid status: {kwargs["status"]}')
        try:
            mutation = _runtime().update_task(task_id, **kwargs)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'task not found: {task_id}')
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            'task': mutation.task.to_dict() if mutation.task else None,
            'state': _serialize_runtime(_runtime()),
        }

    @router.post('/{task_id}/start')
    def start_task(task_id: str) -> dict[str, Any]:
        try:
            mutation = _runtime().start_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'task not found: {task_id}')
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            'task': mutation.task.to_dict() if mutation.task else None,
            'state': _serialize_runtime(_runtime()),
        }

    @router.post('/{task_id}/complete')
    def complete_task(task_id: str) -> dict[str, Any]:
        try:
            mutation = _runtime().complete_task(task_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'task not found: {task_id}')
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            'task': mutation.task.to_dict() if mutation.task else None,
            'state': _serialize_runtime(_runtime()),
        }

    @router.post('/{task_id}/cancel')
    def cancel_task(task_id: str, body: CancelBody) -> dict[str, Any]:
        try:
            mutation = _runtime().cancel_task(task_id, reason=body.reason)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'task not found: {task_id}')
        return {
            'task': mutation.task.to_dict() if mutation.task else None,
            'state': _serialize_runtime(_runtime()),
        }

    @router.post('/{task_id}/block')
    def block_task(task_id: str, body: BlockBody) -> dict[str, Any]:
        try:
            mutation = _runtime().block_task(
                task_id, blocked_by=body.blocked_by, reason=body.reason
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f'task not found: {task_id}')
        return {
            'task': mutation.task.to_dict() if mutation.task else None,
            'state': _serialize_runtime(_runtime()),
        }

    return router
