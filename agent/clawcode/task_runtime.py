from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .task import PortingTask, VALID_TASK_STATUSES


DEFAULT_TASK_RUNTIME_PATH = Path('.port_sessions') / 'task_runtime.json'
ACTIONABLE_TASK_STATUSES = ('pending', 'in_progress')
TERMINAL_TASK_STATUSES = ('completed', 'cancelled')


@dataclass(frozen=True)
class TaskMutation:
    task: PortingTask | None
    store_path: str
    before_sha256: str | None
    after_sha256: str
    before_preview: str | None
    after_preview: str
    before_count: int
    after_count: int


@dataclass
class TaskRuntime:
    tasks: tuple[PortingTask, ...] = field(default_factory=tuple)
    storage_path: Path = field(default_factory=lambda: DEFAULT_TASK_RUNTIME_PATH.resolve())

    @classmethod
    def from_workspace(cls, cwd: Path) -> 'TaskRuntime':
        storage_path = (cwd.resolve() / DEFAULT_TASK_RUNTIME_PATH).resolve()
        if not storage_path.exists():
            return cls(tasks=(), storage_path=storage_path)
        try:
            payload = json.loads(storage_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return cls(tasks=(), storage_path=storage_path)
        raw_tasks = payload.get('tasks')
        if not isinstance(raw_tasks, list):
            return cls(tasks=(), storage_path=storage_path)
        tasks: list[PortingTask] = []
        for item in raw_tasks:
            if not isinstance(item, dict):
                continue
            task = PortingTask.from_dict(item)
            if not task.task_id or not task.title:
                continue
            tasks.append(task)
        return cls(tasks=tuple(tasks), storage_path=storage_path)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
        actionable_only: bool = False,
        limit: int | None = None,
    ) -> tuple[PortingTask, ...]:
        tasks = self.tasks
        if status:
            normalized = _normalize_status(status)
            tasks = tuple(task for task in tasks if task.status == normalized)
        if owner:
            tasks = tuple(task for task in tasks if task.owner == owner)
        if actionable_only:
            actionable_ids = {task.task_id for task in self.next_tasks(limit=None)}
            tasks = tuple(task for task in tasks if task.task_id in actionable_ids)
        tasks = tuple(_sort_tasks(tasks))
        if limit is not None and limit >= 0:
            tasks = tasks[:limit]
        return tasks

    def next_tasks(self, *, limit: int | None = 10) -> tuple[PortingTask, ...]:
        tasks_by_id = {task.task_id: task for task in self.tasks}
        actionable: list[PortingTask] = []
        for task in self.tasks:
            if task.status not in ACTIONABLE_TASK_STATUSES:
                continue
            unresolved = _unresolved_dependencies(task, tasks_by_id)
            if task.status == 'in_progress' or not unresolved:
                actionable.append(task)
        actionable = list(_sort_tasks(actionable))
        if limit is not None and limit >= 0:
            actionable = actionable[:limit]
        return tuple(actionable)

    def get_task(self, task_id: str) -> PortingTask | None:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def create_task(
        self,
        *,
        title: str,
        description: str | None = None,
        status: str = 'pending',
        priority: str | None = None,
        task_id: str | None = None,
        active_form: str | None = None,
        owner: str | None = None,
        blocks: tuple[str, ...] | list[str] = (),
        blocked_by: tuple[str, ...] | list[str] = (),
        metadata: dict[str, Any] | None = None,
    ) -> TaskMutation:
        task = PortingTask(
            task_id=task_id or f'task_{uuid4().hex[:10]}',
            title=title.strip(),
            description=description.strip() if isinstance(description, str) and description.strip() else None,
            status=_normalize_status(status),
            priority=priority.strip() if isinstance(priority, str) and priority.strip() else None,
            active_form=(
                active_form.strip()
                if isinstance(active_form, str) and active_form.strip()
                else None
            ),
            owner=owner.strip() if isinstance(owner, str) and owner.strip() else None,
            blocks=_normalize_id_list(blocks),
            blocked_by=_normalize_id_list(blocked_by),
            metadata=dict(metadata or {}),
        )
        return self._persist((*self.tasks, task), task=task)

    def update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        active_form: str | None = None,
        owner: str | None = None,
        blocks: tuple[str, ...] | list[str] | None = None,
        blocked_by: tuple[str, ...] | list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        merge_metadata: bool = False,
    ) -> TaskMutation:
        existing = self.get_task(task_id)
        if existing is None:
            raise KeyError(task_id)
        updated_metadata = dict(existing.metadata)
        if metadata is not None:
            updated_metadata = {**updated_metadata, **metadata} if merge_metadata else dict(metadata)
        updated = replace(
            existing,
            title=title.strip() if isinstance(title, str) and title.strip() else existing.title,
            description=(
                description.strip()
                if isinstance(description, str) and description.strip()
                else None if description == ''
                else existing.description
            ),
            status=_normalize_status(status) if status is not None else existing.status,
            priority=(
                priority.strip()
                if isinstance(priority, str) and priority.strip()
                else None if priority == ''
                else existing.priority
            ),
            active_form=(
                active_form.strip()
                if isinstance(active_form, str) and active_form.strip()
                else None if active_form == ''
                else existing.active_form
            ),
            owner=(
                owner.strip()
                if isinstance(owner, str) and owner.strip()
                else None if owner == ''
                else existing.owner
            ),
            blocks=(
                _normalize_id_list(blocks)
                if blocks is not None
                else existing.blocks
            ),
            blocked_by=(
                _normalize_id_list(blocked_by)
                if blocked_by is not None
                else existing.blocked_by
            ),
            metadata=updated_metadata,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        tasks = tuple(updated if task.task_id == task_id else task for task in self.tasks)
        return self._persist(tasks, task=updated)

    def start_task(
        self,
        task_id: str,
        *,
        owner: str | None = None,
        active_form: str | None = None,
    ) -> TaskMutation:
        existing = self.get_task(task_id)
        if existing is None:
            raise KeyError(task_id)
        unresolved = _unresolved_dependencies(existing, {task.task_id: task for task in self.tasks})
        metadata = dict(existing.metadata)
        if unresolved:
            metadata['blocked_reason'] = f'waiting_on:{",".join(unresolved)}'
            return self.update_task(
                task_id,
                status='blocked',
                owner=owner if owner is not None else existing.owner,
                active_form=active_form if active_form is not None else existing.active_form,
                metadata=metadata,
            )
        if 'blocked_reason' in metadata:
            metadata.pop('blocked_reason')
        return self.update_task(
            task_id,
            status='in_progress',
            owner=owner if owner is not None else existing.owner,
            active_form=active_form if active_form is not None else existing.active_form,
            metadata=metadata,
        )

    def complete_task(self, task_id: str) -> TaskMutation:
        mutation = self.update_task(task_id, status='completed')
        completed_ids = {task.task_id for task in self.tasks if task.status in TERMINAL_TASK_STATUSES}
        updated_tasks: list[PortingTask] = []
        changed = False
        for task in self.tasks:
            if task.status != 'blocked':
                updated_tasks.append(task)
                continue
            unresolved = tuple(
                dependency
                for dependency in task.blocked_by
                if dependency not in completed_ids
            )
            if unresolved:
                updated_tasks.append(task)
                continue
            metadata = dict(task.metadata)
            metadata.pop('blocked_reason', None)
            updated_tasks.append(
                replace(
                    task,
                    status='pending',
                    metadata=metadata,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            changed = True
        if changed:
            return self._persist(tuple(updated_tasks), task=self.get_task(task_id))
        return mutation

    def block_task(
        self,
        task_id: str,
        *,
        blocked_by: tuple[str, ...] | list[str] | None = None,
        reason: str | None = None,
    ) -> TaskMutation:
        existing = self.get_task(task_id)
        if existing is None:
            raise KeyError(task_id)
        merged_blocked_by = tuple(existing.blocked_by)
        if blocked_by is not None:
            merged_blocked_by = _merge_ids(existing.blocked_by, _normalize_id_list(blocked_by))
        metadata = dict(existing.metadata)
        if isinstance(reason, str) and reason.strip():
            metadata['blocked_reason'] = reason.strip()
        return self.update_task(
            task_id,
            status='blocked',
            blocked_by=merged_blocked_by,
            metadata=metadata,
        )

    def cancel_task(self, task_id: str, *, reason: str | None = None) -> TaskMutation:
        existing = self.get_task(task_id)
        if existing is None:
            raise KeyError(task_id)
        metadata = dict(existing.metadata)
        if isinstance(reason, str) and reason.strip():
            metadata['cancel_reason'] = reason.strip()
        return self.update_task(
            task_id,
            status='cancelled',
            metadata=metadata,
        )

    def replace_tasks(self, items: list[dict[str, Any]]) -> TaskMutation:
        tasks: list[PortingTask] = []
        now = datetime.now(timezone.utc).isoformat()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            title = item.get('title')
            if not isinstance(title, str) or not title.strip():
                continue
            task_id = item.get('task_id')
            if not isinstance(task_id, str) or not task_id.strip():
                task_id = item.get('id')
            tasks.append(
                PortingTask(
                    task_id=(
                        task_id.strip()
                        if isinstance(task_id, str) and task_id.strip()
                        else f'task_{index}_{uuid4().hex[:6]}'
                    ),
                    title=title.strip(),
                    description=(
                        item.get('description').strip()
                        if isinstance(item.get('description'), str)
                        and item.get('description').strip()
                        else None
                    ),
                    status=_normalize_status(item.get('status')),
                    priority=(
                        item.get('priority').strip()
                        if isinstance(item.get('priority'), str)
                        and item.get('priority').strip()
                        else None
                    ),
                    active_form=(
                        item.get('active_form').strip()
                        if isinstance(item.get('active_form'), str)
                        and item.get('active_form').strip()
                        else None
                    ),
                    owner=(
                        item.get('owner').strip()
                        if isinstance(item.get('owner'), str)
                        and item.get('owner').strip()
                        else None
                    ),
                    blocks=_normalize_id_list(item.get('blocks', [])),
                    blocked_by=_normalize_id_list(item.get('blocked_by', [])),
                    metadata=(
                        dict(item.get('metadata'))
                        if isinstance(item.get('metadata'), dict)
                        else {}
                    ),
                    created_at=(
                        str(item.get('created_at'))
                        if isinstance(item.get('created_at'), str)
                        else now
                    ),
                    updated_at=now,
                )
            )
        mutation = self._persist(tuple(tasks), task=None)
        return mutation

    def render_summary(self) -> str:
        lines = [
            f'Local task runtime file: {self.storage_path}',
            f'Total tasks: {len(self.tasks)}',
        ]
        counts: dict[str, int] = {}
        for task in self.tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        if counts:
            lines.append(
                '- Status counts: '
                + ', '.join(f'{name}={count}' for name, count in sorted(counts.items()))
            )
        actionable = self.next_tasks(limit=None)
        if actionable:
            lines.append(f'- Actionable tasks: {len(actionable)}')
        blocked = [task for task in self.tasks if task.status == 'blocked']
        if blocked:
            lines.append(f'- Blocked tasks: {len(blocked)}')
        if self.tasks:
            preview = ', '.join(task.title for task in _sort_tasks(self.tasks)[:4])
            if len(self.tasks) > 4:
                preview += f', ... (+{len(self.tasks) - 4} more)'
            lines.append(f'- Task preview: {preview}')
        return '\n'.join(lines)

    def render_tasks(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
        actionable_only: bool = False,
        limit: int = 50,
    ) -> str:
        tasks = self.list_tasks(
            status=status,
            owner=owner,
            actionable_only=actionable_only,
            limit=limit,
        )
        if not tasks:
            return '# Tasks\n\nNo tasks are currently stored.'
        lines = ['# Tasks', '']
        if actionable_only:
            lines.append('Showing actionable tasks only.')
            lines.append('')
        for task in tasks:
            details = [task.task_id, f'status={task.status}']
            if task.priority:
                details.append(f'priority={task.priority}')
            if task.owner:
                details.append(f'owner={task.owner}')
            details.append(f'title={task.title}')
            lines.append('- ' + '; '.join(details))
            if task.description:
                lines.append(f'  description: {task.description}')
            if task.active_form:
                lines.append(f'  active_form: {task.active_form}')
            if task.blocked_by:
                lines.append(f"  blocked_by: {', '.join(task.blocked_by)}")
            if task.blocks:
                lines.append(f"  blocks: {', '.join(task.blocks)}")
        return '\n'.join(lines)

    def render_task(self, task_id: str) -> str:
        task = self.get_task(task_id)
        if task is None:
            return f'# Task\n\nUnknown task id: {task_id}'
        lines = [
            '# Task',
            '',
            f'- ID: {task.task_id}',
            f'- Status: {task.status}',
            f'- Title: {task.title}',
        ]
        if task.priority:
            lines.append(f'- Priority: {task.priority}')
        if task.owner:
            lines.append(f'- Owner: {task.owner}')
        if task.active_form:
            lines.append(f'- Active Form: {task.active_form}')
        if task.description:
            lines.append(f'- Description: {task.description}')
        if task.blocked_by:
            lines.append(f"- Blocked By: {', '.join(task.blocked_by)}")
        if task.blocks:
            lines.append(f"- Blocks: {', '.join(task.blocks)}")
        if task.metadata:
            lines.append('- Metadata:')
            for key, value in sorted(task.metadata.items()):
                lines.append(f'  - {key}={value}')
        lines.append(f'- Updated: {task.updated_at}')
        return '\n'.join(lines)

    def render_next_tasks(self, *, limit: int = 10) -> str:
        tasks = self.next_tasks(limit=limit)
        if not tasks:
            return '# Next Tasks\n\nNo actionable tasks are currently available.'
        lines = ['# Next Tasks', '']
        for task in tasks:
            details = [task.task_id, f'status={task.status}', f'title={task.title}']
            if task.owner:
                details.append(f'owner={task.owner}')
            lines.append('- ' + '; '.join(details))
            unresolved = _unresolved_dependencies(task, {item.task_id: item for item in self.tasks})
            if unresolved:
                lines.append(f"  unresolved_dependencies: {', '.join(unresolved)}")
            if task.active_form:
                lines.append(f'  active_form: {task.active_form}')
        return '\n'.join(lines)

    def _persist(
        self,
        tasks: tuple[PortingTask, ...],
        *,
        task: PortingTask | None,
    ) -> TaskMutation:
        before_tasks = self.tasks
        before_text = self._serialize_payload(before_tasks)
        before_preview = _snapshot_text(before_text)
        before_sha256 = (
            hashlib.sha256(before_text.encode('utf-8')).hexdigest()
            if self.storage_path.exists() or before_tasks
            else None
        )
        payload_text = self._serialize_payload(tasks)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(payload_text, encoding='utf-8')
        self.tasks = tasks
        after_sha256 = hashlib.sha256(payload_text.encode('utf-8')).hexdigest()
        return TaskMutation(
            task=task,
            store_path=str(self.storage_path),
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            before_preview=before_preview if before_text.strip() else None,
            after_preview=_snapshot_text(payload_text),
            before_count=len(before_tasks),
            after_count=len(tasks),
        )

    def _serialize_payload(self, tasks: tuple[PortingTask, ...]) -> str:
        payload = {
            'tasks': [task.to_dict() for task in tasks],
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)


def _snapshot_text(text: str, limit: int = 240) -> str:
    normalized = ' '.join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + '...'


def _normalize_status(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower().replace('-', '_').replace(' ', '_')
        aliases = {
            'complete': 'completed',
            'done': 'completed',
            'todo': 'pending',
            'open': 'pending',
        }
        lowered = aliases.get(lowered, lowered)
        if lowered in VALID_TASK_STATUSES:
            return lowered
    return 'pending'


def _normalize_id_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        items = list(value)
    elif isinstance(value, list):
        items = value
    else:
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return tuple(normalized)


def _merge_ids(existing: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    merged = list(existing)
    seen = set(existing)
    for item in additions:
        if item in seen:
            continue
        merged.append(item)
        seen.add(item)
    return tuple(merged)


def _unresolved_dependencies(
    task: PortingTask,
    tasks_by_id: dict[str, PortingTask],
) -> tuple[str, ...]:
    unresolved: list[str] = []
    for dependency_id in task.blocked_by:
        dependency = tasks_by_id.get(dependency_id)
        if dependency is None:
            unresolved.append(dependency_id)
            continue
        if dependency.status not in TERMINAL_TASK_STATUSES:
            unresolved.append(dependency_id)
    return tuple(unresolved)


def _task_sort_key(task: PortingTask) -> tuple[int, int, str, str]:
    status_rank = {
        'in_progress': 0,
        'pending': 1,
        'blocked': 2,
        'completed': 3,
        'cancelled': 4,
    }.get(task.status, 9)
    priority_rank = {
        'critical': 0,
        'high': 1,
        'medium': 2,
        'low': 3,
    }.get((task.priority or '').lower(), 9)
    return (status_rank, priority_rank, task.title.lower(), task.task_id)


def _sort_tasks(tasks: tuple[PortingTask, ...] | list[PortingTask]) -> tuple[PortingTask, ...]:
    return tuple(sorted(tasks, key=_task_sort_key))
