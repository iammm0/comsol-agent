"""FastAPI router for the ask-user runtime.

The agent's `Ask` flow consumes pre-staged answers out of an on-disk queue.
This router lets the GUI inspect that queue, enqueue more answers, drop
specific ones, and clear history.

We talk to the underlying `_persist_state` because the runtime doesn't
expose a public enqueue method — same code path the runtime itself uses
when consuming answers, so persistence stays consistent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ask_user_runtime import AskUserRuntime, QueuedUserAnswer


class EnqueueBody(BaseModel):
    answer: str = Field(min_length=1)
    question: str | None = None
    question_id: str | None = None
    header: str | None = None
    match: str = 'exact'
    consume: bool = True


def _serialize(runtime: AskUserRuntime) -> dict[str, Any]:
    return {
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'interactive': runtime.interactive,
        'queued_answers': [a.to_dict() for a in runtime.queued_answers],
        'history': [dict(entry) for entry in runtime.history],
    }


def create_ask_user_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/ask-user', tags=['ask-user'])

    def _runtime() -> AskUserRuntime:
        return AskUserRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def status() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('/queue')
    def enqueue(body: EnqueueBody) -> dict[str, Any]:
        if body.match not in ('exact', 'contains'):
            raise HTTPException(status_code=400, detail='match must be "exact" or "contains"')
        runtime = _runtime()
        new_entry = QueuedUserAnswer(
            answer=body.answer,
            question=body.question,
            question_id=body.question_id,
            header=body.header,
            match=body.match,
            consume=body.consume,
        )
        runtime.queued_answers = (*runtime.queued_answers, new_entry)
        runtime._persist_state()
        return _serialize(_runtime())

    @router.delete('/queue/{index}')
    def remove_queued(index: int) -> dict[str, Any]:
        runtime = _runtime()
        if index < 0 or index >= len(runtime.queued_answers):
            raise HTTPException(status_code=404, detail=f'queued index out of range: {index}')
        queued = list(runtime.queued_answers)
        queued.pop(index)
        runtime.queued_answers = tuple(queued)
        runtime._persist_state()
        return _serialize(_runtime())

    @router.post('/clear-history')
    def clear_history() -> dict[str, Any]:
        runtime = _runtime()
        runtime.history = ()
        runtime._persist_state()
        return _serialize(_runtime())

    return router
