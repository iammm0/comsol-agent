"""FastAPI router for the team/message runtime.

List + create + delete teams; send messages to a team and read history.
Mirrors :class:`TeamRuntime` 1:1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..team_runtime import TeamRuntime


class CreateTeamBody(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    members: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SendMessageBody(BaseModel):
    text: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    recipient: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _serialize(runtime: TeamRuntime) -> dict[str, Any]:
    return {
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'teams': [t.to_dict() for t in runtime.teams],
        'messages': [m.to_dict() for m in runtime.messages],
    }


def create_team_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/teams', tags=['teams'])

    def _runtime() -> TeamRuntime:
        return TeamRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def list_teams() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('')
    def create_team(body: CreateTeamBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            runtime.create_team(
                body.name,
                description=body.description,
                members=body.members,
                metadata=body.metadata,
            )
        except KeyError as exc:
            raise HTTPException(status_code=409, detail=f'team already exists: {exc.args[0]}')
        return _serialize(_runtime())

    @router.delete('/{name}')
    def delete_team(name: str) -> dict[str, Any]:
        runtime = _runtime()
        try:
            runtime.delete_team(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'team not found: {name}')
        return _serialize(_runtime())

    @router.post('/{name}/messages')
    def send_message(name: str, body: SendMessageBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            message = runtime.send_message(
                team_name=name,
                text=body.text,
                sender=body.sender,
                recipient=body.recipient,
                metadata=body.metadata,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f'team not found: {name}')
        return {'message': message.to_dict(), 'state': _serialize(_runtime())}

    return router
