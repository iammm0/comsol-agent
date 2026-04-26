from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_WORKFLOW_STATE_PATH = Path('.port_sessions') / 'workflow_runtime.json'
WORKFLOW_MANIFEST_FILES = ('.claw-workflows.json', '.claw-workflow.json')


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    source_manifest: str
    description: str | None = None
    prompt: str | None = None
    steps: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowRunRecord:
    run_id: str
    workflow_name: str
    status: str
    created_at: str
    arguments: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None


@dataclass
class WorkflowRuntime:
    cwd: Path
    workflows: tuple[WorkflowDefinition, ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    history: tuple[WorkflowRunRecord, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_WORKFLOW_STATE_PATH.resolve())

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'WorkflowRuntime':
        resolved_cwd = cwd.resolve()
        manifest_paths = _discover_manifest_paths(resolved_cwd, additional_working_directories)
        workflows: list[WorkflowDefinition] = []
        for manifest_path in manifest_paths:
            workflows.extend(_load_workflows_from_manifest(manifest_path))
        state_path = resolved_cwd / DEFAULT_WORKFLOW_STATE_PATH
        payload = _load_payload(state_path)
        history_payload = payload.get('history')
        history = tuple(
            _run_record_from_payload(item)
            for item in history_payload
            if isinstance(item, dict) and _run_record_from_payload(item) is not None
        ) if isinstance(history_payload, list) else ()
        return cls(
            cwd=resolved_cwd,
            workflows=tuple(workflows),
            manifests=tuple(str(path) for path in manifest_paths),
            history=history,
            state_path=state_path,
        )

    def has_workflows(self) -> bool:
        return bool(self.workflows or self.history)

    def list_workflows(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> tuple[WorkflowDefinition, ...]:
        workflows = self.workflows
        if query:
            needle = query.lower()
            workflows = tuple(
                workflow
                for workflow in workflows
                if needle in workflow.name.lower()
                or needle in (workflow.description or '').lower()
            )
        if limit is not None and limit >= 0:
            workflows = workflows[:limit]
        return workflows

    def get_workflow(self, name: str) -> WorkflowDefinition | None:
        needle = name.strip().lower()
        if not needle:
            return None
        for workflow in self.workflows:
            if workflow.name.lower() == needle:
                return workflow
        return None

    def run_workflow(
        self,
        name: str,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> WorkflowRunRecord:
        workflow = self.get_workflow(name)
        if workflow is None:
            raise KeyError(name)
        normalized_arguments = dict(arguments or {})
        rendered_steps = _render_steps(workflow.steps, normalized_arguments)
        summary = (
            rendered_steps[0]
            if rendered_steps
            else workflow.description
            or f'Workflow {workflow.name} recorded without steps.'
        )
        record = WorkflowRunRecord(
            run_id=f'workflow_run_{uuid4().hex[:10]}',
            workflow_name=workflow.name,
            status='recorded',
            created_at=_utc_now(),
            arguments=normalized_arguments,
            summary=summary,
        )
        self.history = (*self.history, record)
        self._persist_state()
        return record

    def render_summary(self) -> str:
        lines = [
            f'Local workflow manifests: {len(self.manifests)}',
            f'Configured workflows: {len(self.workflows)}',
            f'Workflow run history: {len(self.history)}',
        ]
        if self.workflows:
            lines.append('- Latest workflows:')
            for workflow in self.workflows[:5]:
                description = workflow.description or 'No description.'
                lines.append(f'  - {workflow.name}: {description}')
        return '\n'.join(lines)

    def render_workflows_index(self, *, query: str | None = None) -> str:
        workflows = self.list_workflows(query=query, limit=100)
        lines = ['# Workflows', '']
        if not workflows:
            lines.append('No local workflows discovered.')
            return '\n'.join(lines)
        for workflow in workflows:
            description = workflow.description or 'No description.'
            lines.append(f'- {workflow.name} ; steps={len(workflow.steps)} ; {description}')
        return '\n'.join(lines)

    def render_workflow(self, name: str) -> str:
        workflow = self.get_workflow(name)
        if workflow is None:
            raise KeyError(name)
        lines = ['# Workflow', '', f'name={workflow.name}']
        lines.append(f'source_manifest={workflow.source_manifest}')
        lines.append(f'step_count={len(workflow.steps)}')
        if workflow.description:
            lines.extend(['', '## Description', workflow.description])
        if workflow.prompt:
            lines.extend(['', '## Prompt', workflow.prompt])
        if workflow.steps:
            lines.extend(['', '## Steps'])
            for index, step in enumerate(workflow.steps, start=1):
                title = step.get('title') or step.get('name') or f'Step {index}'
                detail = step.get('detail') or step.get('command') or step.get('prompt') or ''
                lines.append(f'{index}. {title}')
                if detail:
                    lines.append(f'   {detail}')
        return '\n'.join(lines)

    def render_run_report(
        self,
        name: str,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> str:
        workflow = self.get_workflow(name)
        if workflow is None:
            raise KeyError(name)
        normalized_arguments = dict(arguments or {})
        record = self.run_workflow(name, arguments=normalized_arguments)
        lines = ['# Workflow Run', '', f'run_id={record.run_id}', f'workflow={record.workflow_name}']
        lines.append(f'status={record.status}')
        lines.append(f'created_at={record.created_at}')
        if normalized_arguments:
            lines.extend(['', '## Arguments', json.dumps(normalized_arguments, indent=2, ensure_ascii=True)])
        rendered_steps = _render_steps(workflow.steps, normalized_arguments)
        if rendered_steps:
            lines.extend(['', '## Resolved Steps'])
            lines.extend(f'- {step}' for step in rendered_steps)
        if workflow.prompt:
            lines.extend(['', '## Prompt', _safe_format(workflow.prompt, normalized_arguments)])
        return '\n'.join(lines)

    def _persist_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
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
        for filename in WORKFLOW_MANIFEST_FILES:
            candidate = (directory / filename).resolve()
            if candidate in seen or not candidate.exists():
                continue
            seen.add(candidate)
            found.append(candidate)
    return tuple(found)


def _load_workflows_from_manifest(manifest_path: Path) -> list[WorkflowDefinition]:
    try:
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    items: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_workflows = payload.get('workflows')
        if isinstance(raw_workflows, list):
            items.extend(item for item in raw_workflows if isinstance(item, dict))
        raw_workflow = payload.get('workflow')
        if isinstance(raw_workflow, dict):
            items.append(raw_workflow)
    workflows: list[WorkflowDefinition] = []
    for item in items:
        name = item.get('name')
        if not isinstance(name, str) or not name.strip():
            continue
        raw_steps = item.get('steps')
        steps: list[dict[str, Any]] = []
        if isinstance(raw_steps, list):
            for entry in raw_steps:
                if isinstance(entry, str):
                    steps.append({'title': entry})
                elif isinstance(entry, dict):
                    steps.append(dict(entry))
        workflows.append(
            WorkflowDefinition(
                name=name.strip(),
                source_manifest=str(manifest_path),
                description=(
                    item['description'].strip()
                    if isinstance(item.get('description'), str) and item['description'].strip()
                    else None
                ),
                prompt=(
                    item['prompt'].strip()
                    if isinstance(item.get('prompt'), str) and item['prompt'].strip()
                    else None
                ),
                steps=tuple(steps),
                metadata=dict(item.get('metadata', {})) if isinstance(item.get('metadata'), dict) else {},
            )
        )
    return workflows


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_record_from_payload(payload: dict[str, Any]) -> WorkflowRunRecord | None:
    run_id = payload.get('run_id')
    workflow_name = payload.get('workflow_name')
    status = payload.get('status')
    created_at = payload.get('created_at')
    if not all(isinstance(value, str) and value for value in (run_id, workflow_name, status, created_at)):
        return None
    arguments = payload.get('arguments')
    return WorkflowRunRecord(
        run_id=run_id,
        workflow_name=workflow_name,
        status=status,
        created_at=created_at,
        arguments=dict(arguments) if isinstance(arguments, dict) else {},
        summary=str(payload['summary']) if isinstance(payload.get('summary'), str) else None,
    )


def _render_steps(steps: tuple[dict[str, Any], ...], arguments: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for index, step in enumerate(steps, start=1):
        title = step.get('title') or step.get('name') or f'Step {index}'
        detail = step.get('detail') or step.get('command') or step.get('prompt')
        text = str(title)
        if isinstance(detail, str) and detail.strip():
            text = f'{text}: {_safe_format(detail, arguments)}'
        rendered.append(_safe_format(text, arguments))
    return rendered


def _safe_format(template: str, arguments: dict[str, Any]) -> str:
    text = template
    for key, value in arguments.items():
        text = text.replace('{' + str(key) + '}', str(value))
    return text


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
