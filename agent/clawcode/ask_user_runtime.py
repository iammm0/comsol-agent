from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_ASK_USER_STATE_FILE = Path('.port_sessions') / 'ask_user_runtime.json'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class QueuedUserAnswer:
    answer: str
    question: str | None = None
    question_id: str | None = None
    header: str | None = None
    match: str = 'exact'
    consume: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'QueuedUserAnswer | None':
        answer = payload.get('answer')
        if not isinstance(answer, str) or not answer.strip():
            return None
        question = payload.get('question')
        if question is not None and not isinstance(question, str):
            question = None
        question_id = payload.get('question_id')
        if question_id is not None and not isinstance(question_id, str):
            question_id = None
        header = payload.get('header')
        if header is not None and not isinstance(header, str):
            header = None
        match = payload.get('match')
        if not isinstance(match, str) or match not in {'exact', 'contains'}:
            match = 'exact'
        consume = payload.get('consume', True)
        if not isinstance(consume, bool):
            consume = True
        return cls(
            answer=answer,
            question=question.strip() if question else None,
            question_id=question_id.strip() if question_id else None,
            header=header.strip() if header else None,
            match=match,
            consume=consume,
        )

    def matches(
        self,
        *,
        question: str,
        question_id: str | None,
        header: str | None,
    ) -> bool:
        if question_id and self.question_id and self.question_id == question_id:
            return True
        if header and self.header and self.header.lower() == header.lower():
            return True
        if self.question is None:
            return False
        if self.match == 'contains':
            return self.question.lower() in question.lower()
        return self.question.strip().lower() == question.strip().lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            'answer': self.answer,
            'question': self.question,
            'question_id': self.question_id,
            'header': self.header,
            'match': self.match,
            'consume': self.consume,
        }


@dataclass(frozen=True)
class AskUserResponse:
    answer: str
    source: str
    matched_question: str | None = None
    question_id: str | None = None
    header: str | None = None


@dataclass
class AskUserRuntime:
    cwd: Path
    queued_answers: tuple[QueuedUserAnswer, ...] = field(default_factory=tuple)
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_ASK_USER_STATE_FILE.resolve())
    interactive: bool = False
    input_func: Callable[[str], str] | None = None

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
        *,
        interactive: bool | None = None,
        input_func: Callable[[str], str] | None = None,
    ) -> 'AskUserRuntime':
        manifest_paths = _discover_manifest_paths(cwd, additional_working_directories)
        manifest_answers: list[QueuedUserAnswer] = []
        for manifest_path in manifest_paths:
            manifest_answers.extend(_load_answers_from_manifest(manifest_path))
        state_path = cwd.resolve() / DEFAULT_ASK_USER_STATE_FILE
        payload = _load_state_payload(state_path)
        queued_payload = payload.get('queued_answers')
        if isinstance(queued_payload, list):
            queued_answers = tuple(
                answer
                for answer in (
                    QueuedUserAnswer.from_dict(item)
                    for item in queued_payload
                    if isinstance(item, dict)
                )
                if answer is not None
            )
        else:
            queued_answers = tuple(manifest_answers)
        history_payload = payload.get('history')
        history = tuple(item for item in history_payload if isinstance(item, dict)) if isinstance(history_payload, list) else ()
        if interactive is None:
            env_value = os.environ.get('CLAW_ASK_USER_INTERACTIVE', '')
            interactive = env_value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return cls(
            cwd=cwd.resolve(),
            queued_answers=queued_answers,
            history=history,
            manifests=tuple(str(path) for path in manifest_paths),
            state_path=state_path,
            interactive=bool(interactive),
            input_func=input_func,
        )

    def has_state(self) -> bool:
        return bool(self.queued_answers or self.history or self.manifests)

    def answer(
        self,
        *,
        question: str,
        choices: tuple[str, ...] = (),
        question_id: str | None = None,
        header: str | None = None,
        allow_free_text: bool = True,
    ) -> AskUserResponse:
        for index, entry in enumerate(self.queued_answers):
            if not entry.matches(question=question, question_id=question_id, header=header):
                continue
            if entry.consume:
                queued_answers = list(self.queued_answers)
                queued_answers.pop(index)
                self.queued_answers = tuple(queued_answers)
            response = AskUserResponse(
                answer=entry.answer,
                source='queued',
                matched_question=entry.question,
                question_id=question_id or entry.question_id,
                header=header or entry.header,
            )
            self._record_history(question, response, choices=choices)
            self._persist_state()
            return response

        if self.interactive and self.input_func is not None:
            prompt_lines = ['# Ask User']
            if header:
                prompt_lines.append(f'header={header}')
            if question_id:
                prompt_lines.append(f'question_id={question_id}')
            prompt_lines.append(question)
            if choices:
                prompt_lines.append('choices=' + ', '.join(choices))
            raw_answer = self.input_func('\n'.join(prompt_lines) + '\nanswer> ')
            answer = raw_answer.strip()
            if not answer:
                raise LookupError('Interactive ask-user prompt returned an empty answer.')
            if choices and not allow_free_text and answer not in choices:
                raise LookupError(
                    'Interactive answer did not match the allowed choices: '
                    + ', '.join(choices)
                )
            response = AskUserResponse(
                answer=answer,
                source='interactive',
                question_id=question_id,
                header=header,
            )
            self._record_history(question, response, choices=choices)
            self._persist_state()
            return response

        raise LookupError(
            'No queued ask-user answer is available. '
            'Add .claw-ask-user.json or enable CLAW_ASK_USER_INTERACTIVE=1 for interactive prompting.'
        )

    def render_summary(self) -> str:
        lines = [
            f'Ask-user manifests: {len(self.manifests)}',
            f'Queued answers: {len(self.queued_answers)}',
            f'History entries: {len(self.history)}',
            f'Interactive mode: {self.interactive}',
        ]
        if self.queued_answers:
            lines.append('- Pending queued answers:')
            for entry in self.queued_answers[:10]:
                label = entry.question_id or entry.header or entry.question or '(wildcard answer)'
                lines.append(f'  - {label}')
            if len(self.queued_answers) > 10:
                lines.append(f'  - ... plus {len(self.queued_answers) - 10} more')
        return '\n'.join(lines)

    def render_history(self, *, limit: int = 20) -> str:
        lines = ['# Ask User History', '']
        entries = list(self.history[-limit:])
        if not entries:
            lines.append('No ask-user interactions recorded.')
            return '\n'.join(lines)
        for entry in entries:
            lines.append(f"- {entry.get('created_at', '(unknown time)')} :: {entry.get('question', '(unknown question)')}")
            lines.append(f"  - answer={entry.get('answer', '')}")
            lines.append(f"  - source={entry.get('source', 'unknown')}")
            if entry.get('choices'):
                lines.append('  - choices=' + ', '.join(entry['choices']))
        return '\n'.join(lines)

    def _record_history(
        self,
        question: str,
        response: AskUserResponse,
        *,
        choices: tuple[str, ...],
    ) -> None:
        entry = {
            'question': question,
            'answer': response.answer,
            'source': response.source,
            'question_id': response.question_id,
            'header': response.header,
            'choices': list(choices),
            'created_at': _utc_now(),
        }
        self.history = (*self.history, entry)

    def _persist_state(self) -> None:
        payload = {
            'queued_answers': [answer.to_dict() for answer in self.queued_answers],
            'history': list(self.history),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding='utf-8',
        )


def _discover_manifest_paths(cwd: Path, additional_working_directories: tuple[str, ...]) -> tuple[Path, ...]:
    candidates = [
        cwd.resolve() / '.claw-ask-user.json',
        cwd.resolve() / '.claude' / 'ask-user.json',
    ]
    for raw_path in additional_working_directories:
        root = Path(raw_path).resolve()
        candidates.extend(
            [
                root / '.claw-ask-user.json',
                root / '.claude' / 'ask-user.json',
            ]
        )
    discovered: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        discovered.append(resolved)
    return tuple(discovered)


def _load_answers_from_manifest(path: Path) -> list[QueuedUserAnswer]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    answers_payload = payload.get('answers')
    if not isinstance(answers_payload, list):
        return []
    answers: list[QueuedUserAnswer] = []
    for item in answers_payload:
        if not isinstance(item, dict):
            continue
        answer = QueuedUserAnswer.from_dict(item)
        if answer is not None:
            answers.append(answer)
    return answers


def _load_state_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
