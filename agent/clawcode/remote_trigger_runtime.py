from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_REMOTE_TRIGGER_STATE_PATH = Path('.port_sessions') / 'remote_trigger_runtime.json'
REMOTE_TRIGGER_MANIFEST_FILES = ('.claw-remote-triggers.json', '.claw-triggers.json')


@dataclass(frozen=True)
class RemoteTriggerDefinition:
    trigger_id: str
    source: str
    name: str | None = None
    description: str | None = None
    schedule: str | None = None
    workflow: str | None = None
    remote_target: str | None = None
    body: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteTriggerRunRecord:
    run_id: str
    trigger_id: str
    created_at: str
    status: str
    body: dict[str, Any] = field(default_factory=dict)
    workflow: str | None = None
    remote_target: str | None = None


@dataclass
class RemoteTriggerRuntime:
    cwd: Path
    triggers: tuple[RemoteTriggerDefinition, ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    history: tuple[RemoteTriggerRunRecord, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_REMOTE_TRIGGER_STATE_PATH.resolve())

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'RemoteTriggerRuntime':
        resolved_cwd = cwd.resolve()
        manifest_paths = _discover_manifest_paths(resolved_cwd, additional_working_directories)
        manifest_triggers: dict[str, RemoteTriggerDefinition] = {}
        for manifest_path in manifest_paths:
            for trigger in _load_triggers_from_manifest(manifest_path):
                manifest_triggers[trigger.trigger_id] = trigger
        state_path = resolved_cwd / DEFAULT_REMOTE_TRIGGER_STATE_PATH
        payload = _load_payload(state_path)
        custom_payload = payload.get('custom_triggers')
        custom_triggers: dict[str, RemoteTriggerDefinition] = {}
        if isinstance(custom_payload, list):
            for item in custom_payload:
                trigger = _definition_from_payload(item)
                if trigger is not None:
                    custom_triggers[trigger.trigger_id] = trigger
        merged = {**manifest_triggers, **custom_triggers}
        history_payload = payload.get('history')
        history = tuple(
            _run_record_from_payload(item)
            for item in history_payload
            if isinstance(item, dict) and _run_record_from_payload(item) is not None
        ) if isinstance(history_payload, list) else ()
        return cls(
            cwd=resolved_cwd,
            triggers=tuple(sorted(merged.values(), key=lambda item: item.trigger_id.lower())),
            manifests=tuple(str(path) for path in manifest_paths),
            history=history,
            state_path=state_path,
        )

    def has_state(self) -> bool:
        return bool(self.triggers or self.history)

    def list_triggers(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> tuple[RemoteTriggerDefinition, ...]:
        triggers = self.triggers
        if query:
            needle = query.lower()
            triggers = tuple(
                trigger
                for trigger in triggers
                if needle in trigger.trigger_id.lower()
                or needle in (trigger.name or '').lower()
                or needle in (trigger.description or '').lower()
                or needle in (trigger.workflow or '').lower()
            )
        if limit is not None and limit >= 0:
            triggers = triggers[:limit]
        return triggers

    def get_trigger(self, trigger_id: str) -> RemoteTriggerDefinition | None:
        needle = trigger_id.strip().lower()
        if not needle:
            return None
        for trigger in self.triggers:
            if trigger.trigger_id.lower() == needle:
                return trigger
        return None

    def create_trigger(self, body: dict[str, Any]) -> RemoteTriggerDefinition:
        trigger = _definition_from_body(body, source='local_state')
        if trigger.trigger_id in {item.trigger_id for item in self.triggers}:
            raise KeyError(trigger.trigger_id)
        self.triggers = tuple(sorted((*self.triggers, trigger), key=lambda item: item.trigger_id.lower()))
        self._persist_state()
        return trigger

    def update_trigger(self, trigger_id: str, body: dict[str, Any]) -> RemoteTriggerDefinition:
        existing = self.get_trigger(trigger_id)
        if existing is None:
            raise KeyError(trigger_id)
        merged_body = {
            'trigger_id': existing.trigger_id,
            'name': existing.name,
            'description': existing.description,
            'schedule': existing.schedule,
            'workflow': existing.workflow,
            'remote_target': existing.remote_target,
            'body': dict(existing.body),
            'metadata': dict(existing.metadata),
        }
        merged_body.update(body)
        if isinstance(body.get('body'), dict):
            merged_body['body'] = dict(body['body'])
        trigger = _definition_from_body(merged_body, source='local_state')
        self.triggers = tuple(
            sorted(
                (trigger if item.trigger_id == trigger_id else item for item in self.triggers),
                key=lambda item: item.trigger_id.lower(),
            )
        )
        self._persist_state()
        return trigger

    def run_trigger(
        self,
        trigger_id: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> RemoteTriggerRunRecord:
        trigger = self.get_trigger(trigger_id)
        if trigger is None:
            raise KeyError(trigger_id)
        merged_body = dict(trigger.body)
        if body:
            merged_body.update(body)
        record = RemoteTriggerRunRecord(
            run_id=f'trigger_run_{uuid4().hex[:10]}',
            trigger_id=trigger.trigger_id,
            created_at=_utc_now(),
            status='queued',
            body=merged_body,
            workflow=trigger.workflow,
            remote_target=trigger.remote_target,
        )
        self.history = (*self.history, record)
        self._persist_state()
        return record

    def render_summary(self) -> str:
        lines = [
            f'Local remote trigger manifests: {len(self.manifests)}',
            f'Configured remote triggers: {len(self.triggers)}',
            f'Remote trigger run history: {len(self.history)}',
        ]
        if self.triggers:
            lines.append('- Latest triggers:')
            for trigger in self.triggers[:5]:
                label = trigger.name or trigger.trigger_id
                workflow = trigger.workflow or 'none'
                lines.append(f'  - {label}: workflow={workflow}')
        return '\n'.join(lines)

    def render_trigger_index(self, *, query: str | None = None) -> str:
        triggers = self.list_triggers(query=query, limit=100)
        lines = ['# Remote Triggers', '']
        if not triggers:
            lines.append('No local remote triggers discovered.')
            return '\n'.join(lines)
        for trigger in triggers:
            label = trigger.name or trigger.trigger_id
            details = [trigger.trigger_id, label]
            if trigger.schedule:
                details.append(f'schedule={trigger.schedule}')
            if trigger.workflow:
                details.append(f'workflow={trigger.workflow}')
            if trigger.remote_target:
                details.append(f'remote_target={trigger.remote_target}')
            lines.append('- ' + ' ; '.join(details))
        return '\n'.join(lines)

    def render_trigger(self, trigger_id: str) -> str:
        trigger = self.get_trigger(trigger_id)
        if trigger is None:
            raise KeyError(trigger_id)
        lines = ['# Remote Trigger', '', f'trigger_id={trigger.trigger_id}']
        lines.append(f'source={trigger.source}')
        if trigger.name:
            lines.append(f'name={trigger.name}')
        if trigger.description:
            lines.append(f'description={trigger.description}')
        if trigger.schedule:
            lines.append(f'schedule={trigger.schedule}')
        if trigger.workflow:
            lines.append(f'workflow={trigger.workflow}')
        if trigger.remote_target:
            lines.append(f'remote_target={trigger.remote_target}')
        lines.append('body=' + json.dumps(trigger.body, ensure_ascii=True, sort_keys=True))
        return '\n'.join(lines)

    def render_run_report(
        self,
        trigger_id: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> str:
        record = self.run_trigger(trigger_id, body=body)
        lines = ['# Remote Trigger Run', '', f'run_id={record.run_id}', f'trigger_id={record.trigger_id}']
        lines.append(f'status={record.status}')
        lines.append(f'created_at={record.created_at}')
        if record.workflow:
            lines.append(f'workflow={record.workflow}')
        if record.remote_target:
            lines.append(f'remote_target={record.remote_target}')
        lines.append('body=' + json.dumps(record.body, indent=2, ensure_ascii=True, sort_keys=True))
        return '\n'.join(lines)

    def _persist_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'custom_triggers': [
                asdict(trigger)
                for trigger in self.triggers
                if trigger.source == 'local_state'
            ],
            'history': [asdict(record) for record in self.history[-128:]],
        }
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding='utf-8',
        )


def _discover_manifest_paths(cwd: Path, additional_working_directories: tuple[str, ...]) -> tuple[Path, ...]:
    directories = [cwd, *(Path(path).resolve() for path in additional_working_directories)]
    seen: set[Path] = set()
    found: list[Path] = []
    for directory in directories:
        for filename in REMOTE_TRIGGER_MANIFEST_FILES:
            candidate = (directory / filename).resolve()
            if candidate in seen or not candidate.exists():
                continue
            seen.add(candidate)
            found.append(candidate)
    return tuple(found)


def _load_triggers_from_manifest(manifest_path: Path) -> list[RemoteTriggerDefinition]:
    try:
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    raw_triggers = payload.get('triggers') if isinstance(payload, dict) else None
    if not isinstance(raw_triggers, list):
        return []
    triggers: list[RemoteTriggerDefinition] = []
    for item in raw_triggers:
        if not isinstance(item, dict):
            continue
        trigger = _definition_from_body(item, source=str(manifest_path))
        triggers.append(trigger)
    return triggers


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _definition_from_payload(payload: dict[str, Any]) -> RemoteTriggerDefinition | None:
    try:
        return _definition_from_body(payload, source=str(payload.get('source') or 'local_state'))
    except (TypeError, ValueError):
        return None


def _definition_from_body(body: dict[str, Any], *, source: str) -> RemoteTriggerDefinition:
    trigger_id = body.get('trigger_id') or body.get('id') or body.get('name')
    if not isinstance(trigger_id, str) or not trigger_id.strip():
        raise ValueError('trigger body must define trigger_id, id, or name')
    raw_body = body.get('body')
    if raw_body is not None and not isinstance(raw_body, dict):
        raise TypeError('body must be a JSON object when provided')
    metadata = body.get('metadata')
    if metadata is not None and not isinstance(metadata, dict):
        raise TypeError('metadata must be a JSON object when provided')
    return RemoteTriggerDefinition(
        trigger_id=trigger_id.strip(),
        source=source,
        name=body['name'].strip() if isinstance(body.get('name'), str) and body['name'].strip() else None,
        description=(
            body['description'].strip()
            if isinstance(body.get('description'), str) and body['description'].strip()
            else None
        ),
        schedule=(
            body['schedule'].strip()
            if isinstance(body.get('schedule'), str) and body['schedule'].strip()
            else None
        ),
        workflow=(
            body['workflow'].strip()
            if isinstance(body.get('workflow'), str) and body['workflow'].strip()
            else None
        ),
        remote_target=(
            body['remote_target'].strip()
            if isinstance(body.get('remote_target'), str) and body['remote_target'].strip()
            else None
        ),
        body=dict(raw_body or {}),
        metadata=dict(metadata or {}),
    )


def _run_record_from_payload(payload: dict[str, Any]) -> RemoteTriggerRunRecord | None:
    run_id = payload.get('run_id')
    trigger_id = payload.get('trigger_id')
    created_at = payload.get('created_at')
    status = payload.get('status')
    if not all(isinstance(value, str) and value for value in (run_id, trigger_id, created_at, status)):
        return None
    body = payload.get('body')
    return RemoteTriggerRunRecord(
        run_id=run_id,
        trigger_id=trigger_id,
        created_at=created_at,
        status=status,
        body=dict(body) if isinstance(body, dict) else {},
        workflow=str(payload['workflow']) if isinstance(payload.get('workflow'), str) else None,
        remote_target=(
            str(payload['remote_target'])
            if isinstance(payload.get('remote_target'), str)
            else None
        ),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
