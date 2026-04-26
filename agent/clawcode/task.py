from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


VALID_TASK_STATUSES = (
    'pending',
    'in_progress',
    'completed',
    'blocked',
    'cancelled',
)


@dataclass(frozen=True)
class PortingTask:
    task_id: str
    title: str
    status: str = 'pending'
    description: str | None = None
    priority: str | None = None
    active_form: str | None = None
    owner: str | None = None
    blocks: tuple[str, ...] = ()
    blocked_by: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'title': self.title,
            'status': self.status,
            'description': self.description,
            'priority': self.priority,
            'active_form': self.active_form,
            'owner': self.owner,
            'blocks': list(self.blocks),
            'blocked_by': list(self.blocked_by),
            'metadata': dict(self.metadata),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'PortingTask':
        return cls(
            task_id=str(payload.get('task_id') or payload.get('id') or ''),
            title=str(payload.get('title') or ''),
            status=_normalize_task_status(payload.get('status')),
            description=(
                str(payload.get('description'))
                if isinstance(payload.get('description'), str)
                else None
            ),
            priority=(
                str(payload.get('priority'))
                if isinstance(payload.get('priority'), str)
                else None
            ),
            active_form=(
                str(payload.get('active_form'))
                if isinstance(payload.get('active_form'), str)
                and payload.get('active_form')
                else None
            ),
            owner=(
                str(payload.get('owner'))
                if isinstance(payload.get('owner'), str)
                and payload.get('owner')
                else None
            ),
            blocks=_normalize_string_tuple(payload.get('blocks')),
            blocked_by=_normalize_string_tuple(payload.get('blocked_by')),
            metadata=(
                dict(payload.get('metadata'))
                if isinstance(payload.get('metadata'), dict)
                else {}
            ),
            created_at=(
                str(payload.get('created_at'))
                if isinstance(payload.get('created_at'), str)
                else datetime.now(timezone.utc).isoformat()
            ),
            updated_at=(
                str(payload.get('updated_at'))
                if isinstance(payload.get('updated_at'), str)
                else datetime.now(timezone.utc).isoformat()
            ),
        )


def _normalize_task_status(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        aliases = {
            'in-progress': 'in_progress',
            'in progress': 'in_progress',
            'complete': 'completed',
            'done': 'completed',
            'todo': 'pending',
            'open': 'pending',
        }
        lowered = aliases.get(lowered, lowered)
        if lowered in VALID_TASK_STATUSES:
            return lowered
    return 'pending'


def _normalize_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return tuple(normalized)
