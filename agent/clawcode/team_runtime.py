from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_TEAM_STATE_FILE = Path('.port_sessions') / 'team_runtime.json'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TeamDefinition:
    name: str
    description: str | None = None
    members: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'TeamDefinition | None':
        name = payload.get('name')
        if not isinstance(name, str) or not name.strip():
            return None
        description = payload.get('description')
        if description is not None and not isinstance(description, str):
            description = None
        raw_members = payload.get('members', ())
        members = tuple(
            item.strip()
            for item in raw_members
            if isinstance(item, str) and item.strip()
        ) if isinstance(raw_members, (list, tuple)) else ()
        metadata = payload.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
        created_at = payload.get('created_at')
        if not isinstance(created_at, str) or not created_at.strip():
            created_at = _utc_now()
        return cls(
            name=name.strip(),
            description=description.strip() if description else None,
            members=members,
            metadata=dict(metadata),
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'members': list(self.members),
            'metadata': dict(self.metadata),
            'created_at': self.created_at,
        }


@dataclass(frozen=True)
class TeamMessage:
    message_id: str
    team_name: str
    sender: str
    text: str
    recipient: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'TeamMessage | None':
        message_id = payload.get('message_id')
        team_name = payload.get('team_name')
        sender = payload.get('sender')
        text = payload.get('text')
        if not all(isinstance(value, str) and value.strip() for value in (message_id, team_name, sender, text)):
            return None
        recipient = payload.get('recipient')
        if recipient is not None and not isinstance(recipient, str):
            recipient = None
        metadata = payload.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
        created_at = payload.get('created_at')
        if not isinstance(created_at, str) or not created_at.strip():
            created_at = _utc_now()
        return cls(
            message_id=message_id.strip(),
            team_name=team_name.strip(),
            sender=sender.strip(),
            text=text,
            recipient=recipient.strip() if isinstance(recipient, str) and recipient.strip() else None,
            metadata=dict(metadata),
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'message_id': self.message_id,
            'team_name': self.team_name,
            'sender': self.sender,
            'text': self.text,
            'recipient': self.recipient,
            'metadata': dict(self.metadata),
            'created_at': self.created_at,
        }


@dataclass
class TeamRuntime:
    cwd: Path
    teams: tuple[TeamDefinition, ...] = field(default_factory=tuple)
    messages: tuple[TeamMessage, ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_TEAM_STATE_FILE.resolve())

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'TeamRuntime':
        manifest_paths = _discover_manifest_paths(cwd, additional_working_directories)
        manifest_teams: list[TeamDefinition] = []
        for manifest_path in manifest_paths:
            manifest_teams.extend(_load_teams_from_manifest(manifest_path))
        state_path = cwd.resolve() / DEFAULT_TEAM_STATE_FILE
        payload = _load_state_payload(state_path)
        raw_teams = payload.get('teams')
        raw_messages = payload.get('messages')
        if isinstance(raw_teams, list):
            teams = tuple(
                team
                for team in (
                    TeamDefinition.from_dict(item)
                    for item in raw_teams
                    if isinstance(item, dict)
                )
                if team is not None
            )
        else:
            teams = tuple(manifest_teams)
        messages = tuple(
            message
            for message in (
                TeamMessage.from_dict(item)
                for item in raw_messages
                if isinstance(item, dict)
            )
            if message is not None
        ) if isinstance(raw_messages, list) else ()
        return cls(
            cwd=cwd.resolve(),
            teams=teams,
            messages=messages,
            manifests=tuple(str(path) for path in manifest_paths),
            state_path=state_path,
        )

    def has_team_state(self) -> bool:
        return bool(self.teams or self.messages or self.manifests)

    def list_teams(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> tuple[TeamDefinition, ...]:
        teams = self.teams
        if query:
            needle = query.lower()
            teams = tuple(
                team
                for team in teams
                if needle in team.name.lower()
                or needle in (team.description or '').lower()
                or any(needle in member.lower() for member in team.members)
            )
        teams = tuple(sorted(teams, key=lambda team: team.name.lower()))
        if limit is not None and limit >= 0:
            teams = teams[:limit]
        return teams

    def get_team(self, name: str) -> TeamDefinition | None:
        needle = name.strip().lower()
        for team in self.teams:
            if team.name.lower() == needle:
                return team
        return None

    def create_team(
        self,
        name: str,
        *,
        description: str | None = None,
        members: tuple[str, ...] | list[str] = (),
        metadata: dict[str, Any] | None = None,
    ) -> TeamDefinition:
        normalized = name.strip()
        if not normalized:
            raise KeyError('team_name')
        if self.get_team(normalized) is not None:
            raise KeyError(normalized)
        team = TeamDefinition(
            name=normalized,
            description=description.strip() if isinstance(description, str) and description.strip() else None,
            members=tuple(
                member.strip()
                for member in members
                if isinstance(member, str) and member.strip()
            ),
            metadata=dict(metadata or {}),
        )
        self.teams = tuple(sorted((*self.teams, team), key=lambda item: item.name.lower()))
        self._persist_state()
        return team

    def delete_team(self, name: str) -> TeamDefinition:
        team = self.get_team(name)
        if team is None:
            raise KeyError(name)
        self.teams = tuple(existing for existing in self.teams if existing.name != team.name)
        self.messages = tuple(message for message in self.messages if message.team_name != team.name)
        self._persist_state()
        return team

    def send_message(
        self,
        *,
        team_name: str,
        text: str,
        sender: str,
        recipient: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TeamMessage:
        team = self.get_team(team_name)
        if team is None:
            raise KeyError(team_name)
        message = TeamMessage(
            message_id=f'msg_{uuid4().hex[:10]}',
            team_name=team.name,
            sender=sender.strip(),
            text=text,
            recipient=recipient.strip() if isinstance(recipient, str) and recipient.strip() else None,
            metadata=dict(metadata or {}),
        )
        self.messages = (*self.messages, message)
        self._persist_state()
        return message

    def render_summary(self) -> str:
        lines = [
            f'Configured teams: {len(self.teams)}',
            f'Message history entries: {len(self.messages)}',
            f'Team manifests: {len(self.manifests)}',
        ]
        if self.teams:
            lines.append('- Teams:')
            for team in self.list_teams(limit=10):
                lines.append(f'  - {team.name} ({len(team.members)} members)')
            if len(self.teams) > 10:
                lines.append(f'  - ... plus {len(self.teams) - 10} more')
        return '\n'.join(lines)

    def render_team(self, name: str) -> str:
        team = self.get_team(name)
        if team is None:
            raise KeyError(name)
        lines = ['# Team', '', f'- Name: {team.name}']
        if team.description:
            lines.append(f'- Description: {team.description}')
        lines.append(f'- Members: {len(team.members)}')
        if team.members:
            lines.extend(f'  - {member}' for member in team.members)
        recent_messages = [message for message in self.messages if message.team_name == team.name][-5:]
        if recent_messages:
            lines.extend(['', '## Recent Messages'])
            for message in recent_messages:
                target = f' -> {message.recipient}' if message.recipient else ''
                lines.append(f'- {message.sender}{target}: {message.text}')
        return '\n'.join(lines)

    def render_teams_index(self, *, query: str | None = None, limit: int = 50) -> str:
        lines = ['# Teams', '']
        teams = self.list_teams(query=query, limit=limit)
        if not teams:
            lines.append('No local teams are configured.')
            return '\n'.join(lines)
        for team in teams:
            details = [team.name]
            if team.description:
                details.append(team.description)
            if team.members:
                details.append(f'members={",".join(team.members)}')
            lines.append('- ' + ' ; '.join(details))
        return '\n'.join(lines)

    def render_messages(self, *, team_name: str | None = None, limit: int = 20) -> str:
        lines = ['# Team Messages', '']
        messages = list(self.messages)
        if team_name:
            team = self.get_team(team_name)
            if team is None:
                raise KeyError(team_name)
            messages = [message for message in messages if message.team_name == team.name]
        messages = messages[-limit:]
        if not messages:
            lines.append('No team messages recorded.')
            return '\n'.join(lines)
        for message in messages:
            target = f' -> {message.recipient}' if message.recipient else ''
            lines.append(
                f'- [{message.team_name}] {message.sender}{target}: {message.text}'
            )
        return '\n'.join(lines)

    def _persist_state(self) -> None:
        payload = {
            'teams': [team.to_dict() for team in self.teams],
            'messages': [message.to_dict() for message in self.messages],
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding='utf-8',
        )


def _discover_manifest_paths(cwd: Path, additional_working_directories: tuple[str, ...]) -> tuple[Path, ...]:
    candidates = [
        cwd.resolve() / '.claw-teams.json',
        cwd.resolve() / '.claw-team.json',
        cwd.resolve() / '.claude' / 'teams.json',
    ]
    for raw_path in additional_working_directories:
        root = Path(raw_path).resolve()
        candidates.extend(
            [
                root / '.claw-teams.json',
                root / '.claw-team.json',
                root / '.claude' / 'teams.json',
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


def _load_teams_from_manifest(path: Path) -> list[TeamDefinition]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    teams_payload = payload.get('teams')
    if not isinstance(teams_payload, list):
        return []
    teams: list[TeamDefinition] = []
    for item in teams_payload:
        if not isinstance(item, dict):
            continue
        team = TeamDefinition.from_dict(item)
        if team is not None:
            teams.append(team)
    return teams


def _load_state_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
