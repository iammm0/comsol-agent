"""FastAPI router for the GUI's CLAUDE.md / `.claude/rules/*.md` memory view.

The agent's "memory" today is whatever `_load_memory_bundle` discovers — the
hierarchical CLAUDE.md / CLAUDE.local.md files, plus `.claude/rules/*.md`
fragments, plus the global `~/.claude/CLAUDE.md`.  The router lets the GUI
list those files, read their contents, and write changes back.

Writes are sandboxed: a path is only writable if it lives under the active
cwd, one of the additional working dirs, or the user's `~/.claude` global
dir.  Anywhere else returns 403 — the GUI shouldn't be a general file editor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent_context import (
    _discover_global_memory_files,
    _discover_memory_files_for_directory,
    _walk_upwards,
)


@dataclass(frozen=True)
class MemoryPathContext:
    """The set of paths the GUI is allowed to read and write under."""

    cwd: Path
    additional_working_directories: tuple[Path, ...]


class MemoryWriteBody(BaseModel):
    path: str = Field(min_length=1)
    content: str


def _allowed_roots(ctx: MemoryPathContext) -> list[Path]:
    roots = [ctx.cwd.resolve()]
    roots.extend(p.resolve() for p in ctx.additional_working_directories)
    home_claude = (Path.home() / '.claude').resolve()
    roots.append(home_claude)
    return roots


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _ensure_writable(target: Path, ctx: MemoryPathContext) -> Path:
    target = target.resolve()
    if any(_is_under(target, root) for root in _allowed_roots(ctx)):
        return target
    raise HTTPException(
        status_code=403,
        detail=f'path is outside the allowed memory roots: {target}',
    )


def _discover(ctx: MemoryPathContext) -> list[Path]:
    discovered: list[Path] = []
    seen: set[Path] = set()

    def remember(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        discovered.append(resolved)

    for candidate in _discover_global_memory_files():
        remember(candidate)
    for directory in _walk_upwards(ctx.cwd):
        for candidate in _discover_memory_files_for_directory(directory):
            remember(candidate)
    for extra in ctx.additional_working_directories:
        for candidate in _discover_memory_files_for_directory(extra):
            remember(candidate)
    return discovered


def _entry(path: Path, ctx: MemoryPathContext) -> dict[str, Any]:
    try:
        size = path.stat().st_size
        modified = path.stat().st_mtime
    except OSError:
        size = 0
        modified = None
    return {
        'path': str(path),
        'name': path.name,
        'parent': str(path.parent),
        'size': size,
        'modified_at': modified,
        'writable': any(_is_under(path, root) for root in _allowed_roots(ctx)),
    }


def create_memory_router(get_context: Callable[[], MemoryPathContext]) -> APIRouter:
    router = APIRouter(prefix='/api/memory', tags=['memory'])

    @router.get('')
    def list_memory() -> dict[str, Any]:
        ctx = get_context()
        files = _discover(ctx)
        return {
            'cwd': str(ctx.cwd),
            'additional_working_directories': [str(p) for p in ctx.additional_working_directories],
            'global_dir': str(Path.home() / '.claude'),
            'files': [_entry(p, ctx) for p in files],
        }

    @router.get('/file')
    def read_memory(path: str) -> dict[str, Any]:
        ctx = get_context()
        target = Path(path).expanduser()
        # Reads can target any discovered file even if it's outside the
        # writable roots — the model already sees it, the GUI just mirrors that.
        if not target.is_file():
            raise HTTPException(status_code=404, detail=f'file not found: {target}')
        try:
            content = target.read_text(encoding='utf-8', errors='replace')
        except OSError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        entry = _entry(target.resolve(), ctx)
        entry['content'] = content
        return entry

    @router.put('/file')
    def write_memory(body: MemoryWriteBody) -> dict[str, Any]:
        ctx = get_context()
        target = _ensure_writable(Path(body.path).expanduser(), ctx)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.content, encoding='utf-8')
        entry = _entry(target, ctx)
        entry['content'] = body.content
        return entry

    @router.delete('/file')
    def delete_memory(path: str) -> dict[str, Any]:
        ctx = get_context()
        target = _ensure_writable(Path(path).expanduser(), ctx)
        if target.is_file():
            target.unlink()
        return {'deleted': str(target)}

    return router
