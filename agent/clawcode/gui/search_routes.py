"""FastAPI router for the local search runtime.

List discovered providers, activate one, and run queries.  Network calls
require the right `api_key_env` variable to be set in the GUI process —
without it, the search call fails with a 502 here.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..search_runtime import SearchRuntime


class QueryBody(BaseModel):
    query: str = Field(min_length=1)
    provider_name: str | None = None
    max_results: int = 5
    domains: list[str] = Field(default_factory=list)
    timeout_seconds: float = 20.0


def _serialize(runtime: SearchRuntime) -> dict[str, Any]:
    current = runtime.current_provider()
    return {
        'state_path': str(runtime.state_path),
        'manifests': list(runtime.manifests),
        'providers': [asdict(p) for p in runtime.providers],
        'active_provider_name': runtime.active_provider_name,
        'current_provider': asdict(current) if current is not None else None,
    }


def create_search_router(
    get_cwd: Callable[[], Path],
    get_additional_dirs: Callable[[], tuple[Path, ...]],
) -> APIRouter:
    router = APIRouter(prefix='/api/search', tags=['search'])

    def _runtime() -> SearchRuntime:
        return SearchRuntime.from_workspace(
            get_cwd(),
            additional_working_directories=tuple(str(p) for p in get_additional_dirs()),
        )

    @router.get('')
    def status() -> dict[str, Any]:
        return _serialize(_runtime())

    @router.post('/activate/{name}')
    def activate(name: str) -> dict[str, Any]:
        runtime = _runtime()
        try:
            runtime.activate_provider(name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f'unknown provider: {name}')
        return _serialize(_runtime())

    @router.post('/query')
    def query(body: QueryBody) -> dict[str, Any]:
        runtime = _runtime()
        try:
            provider, results = runtime.search(
                body.query,
                provider_name=body.provider_name,
                max_results=body.max_results,
                domains=tuple(body.domains),
                timeout_seconds=body.timeout_seconds,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail='unknown provider')
        except LookupError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f'search failed: {exc}')
        return {
            'provider': asdict(provider),
            'results': [asdict(result) for result in results],
        }

    return router
