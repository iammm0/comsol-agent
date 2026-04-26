"""FastAPI router for the local MCP runtime.

Exposes discovered MCP resources / tools / server profiles, plus read-resource
and call-tool actions.  Reads/writes live MCP servers over stdio just like the
CLI does, so calling a tool from the GUI may spawn a subprocess.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..mcp_runtime import MCPRuntime


class ReadResourceBody(BaseModel):
    uri: str
    max_chars: int = 12000


class CallToolBody(BaseModel):
    tool_name: str = Field(min_length=1)
    server_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    max_chars: int = 12000


def _serialize(runtime: MCPRuntime, *, include_remote: bool = False) -> dict[str, Any]:
    # `include_remote=False` skips probing live stdio servers — the default
    # discovery view should be cheap.  Calling a tool or reading a resource
    # explicitly is the moment we accept subprocess cost.
    if include_remote:
        resources = runtime.list_resources()
        tools = runtime.list_tools()
    else:
        resources = runtime.resources
        tools = ()
    return {
        'manifests': list(runtime.manifests),
        'servers': [asdict(s) for s in runtime.servers],
        'resources': [asdict(r) for r in resources],
        'tools': [asdict(t) for t in tools],
        'has_transport_servers': runtime.has_transport_servers(),
    }


def create_mcp_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/mcp', tags=['mcp'])

    def _runtime() -> MCPRuntime:
        return MCPRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def status(include_remote: bool = False) -> dict[str, Any]:
        return _serialize(_runtime(), include_remote=include_remote)

    @router.post('/resources/read')
    def read_resource(body: ReadResourceBody) -> dict[str, Any]:
        try:
            content = _runtime().read_resource(body.uri, max_chars=body.max_chars)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {'uri': body.uri, 'content': content}

    @router.post('/tools/call')
    def call_tool(body: CallToolBody) -> dict[str, Any]:
        try:
            rendered, metadata = _runtime().call_tool(
                body.tool_name,
                arguments=body.arguments,
                server_name=body.server_name,
                max_chars=body.max_chars,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # subprocess failures bubble up
            raise HTTPException(status_code=500, detail=f'tool call failed: {exc}')
        return {'content': rendered, 'metadata': metadata}

    return router
