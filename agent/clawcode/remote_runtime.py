from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REMOTE_STATE_DIR = Path('.port_sessions')
DEFAULT_REMOTE_STATE_FILE = DEFAULT_REMOTE_STATE_DIR / 'remote_runtime.json'
SUPPORTED_REMOTE_MODES = (
    'remote',
    'ssh',
    'teleport',
    'direct-connect',
    'deep-link',
)


@dataclass(frozen=True)
class RemoteProfile:
    name: str
    mode: str
    target: str
    source_manifest: str
    description: str | None = None
    workspace_cwd: str | None = None
    session_url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteConnectionState:
    mode: str
    target: str
    connected: bool
    connected_at: str
    profile_name: str | None = None
    workspace_cwd: str | None = None
    session_url: str | None = None
    source_manifest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeModeReport:
    mode: str
    connected: bool
    detail: str
    target: str | None = None
    profile_name: str | None = None
    workspace_cwd: str | None = None
    session_url: str | None = None
    source_manifest: str | None = None
    manifest_count: int = 0
    profile_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        lines = [
            f'mode={self.mode}',
            f'connected={self.connected}',
            f'detail={self.detail}',
        ]
        if self.target:
            lines.append(f'target={self.target}')
        if self.profile_name:
            lines.append(f'profile={self.profile_name}')
        if self.workspace_cwd:
            lines.append(f'workspace_cwd={self.workspace_cwd}')
        if self.session_url:
            lines.append(f'session_url={self.session_url}')
        if self.source_manifest:
            lines.append(f'source_manifest={self.source_manifest}')
        lines.append(f'manifest_count={self.manifest_count}')
        lines.append(f'profile_count={self.profile_count}')
        if self.metadata:
            for key, value in sorted(self.metadata.items()):
                lines.append(f'metadata.{key}={value}')
        return '\n'.join(lines)


@dataclass
class RemoteRuntime:
    cwd: Path
    profiles: tuple[RemoteProfile, ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_REMOTE_STATE_FILE.resolve())
    active_connection: RemoteConnectionState | None = None
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'RemoteRuntime':
        manifest_paths = _discover_manifest_paths(cwd, additional_working_directories)
        profiles: list[RemoteProfile] = []
        for manifest_path in manifest_paths:
            profiles.extend(_load_profiles_from_manifest(manifest_path))
        state_path = cwd.resolve() / DEFAULT_REMOTE_STATE_FILE
        payload = _load_state_payload(state_path)
        active_connection = _connection_from_payload(payload.get('active_connection'))
        history_payload = payload.get('history')
        history = tuple(
            item for item in history_payload if isinstance(item, dict)
        ) if isinstance(history_payload, list) else ()
        return cls(
            cwd=cwd.resolve(),
            profiles=tuple(profiles),
            manifests=tuple(str(path) for path in manifest_paths),
            state_path=state_path,
            active_connection=active_connection,
            history=history,
        )

    def has_remote_config(self) -> bool:
        return bool(self.profiles or self.active_connection is not None)

    def list_profiles(
        self,
        *,
        query: str | None = None,
        mode: str | None = None,
        limit: int | None = None,
    ) -> tuple[RemoteProfile, ...]:
        profiles = self.profiles
        if query:
            needle = query.lower()
            profiles = tuple(
                profile
                for profile in profiles
                if needle in profile.name.lower()
                or needle in profile.mode.lower()
                or needle in profile.target.lower()
                or needle in (profile.description or '').lower()
            )
        if mode:
            profiles = tuple(profile for profile in profiles if profile.mode == _normalize_mode(mode))
        if limit is not None and limit >= 0:
            profiles = profiles[:limit]
        return profiles

    def get_profile(self, name_or_target: str) -> RemoteProfile | None:
        needle = name_or_target.strip().lower()
        if not needle:
            return None
        for profile in self.profiles:
            if profile.name.lower() == needle or profile.target.lower() == needle:
                return profile
        return None

    def connect(
        self,
        target: str,
        *,
        mode: str | None = None,
    ) -> RuntimeModeReport:
        normalized_mode = _normalize_mode(mode or 'remote')
        profile = self.get_profile(target)
        if profile is not None:
            normalized_mode = _normalize_mode(profile.mode or normalized_mode)
            connection = RemoteConnectionState(
                mode=normalized_mode,
                target=profile.target,
                connected=True,
                connected_at=_utc_now(),
                profile_name=profile.name,
                workspace_cwd=profile.workspace_cwd,
                session_url=profile.session_url,
                source_manifest=profile.source_manifest,
                metadata=dict(profile.metadata),
            )
            detail = f'Activated remote profile {profile.name}'
        else:
            connection = RemoteConnectionState(
                mode=normalized_mode,
                target=target.strip(),
                connected=True,
                connected_at=_utc_now(),
                metadata={'ephemeral': True},
            )
            detail = f'Activated {normalized_mode} target {target.strip()}'
        self.active_connection = connection
        self._append_history(
            {
                'action': 'connect',
                'mode': connection.mode,
                'target': connection.target,
                'profile_name': connection.profile_name,
                'connected_at': connection.connected_at,
            }
        )
        self._persist_state()
        return self.current_report(detail=detail)

    def disconnect(self, *, reason: str = 'manual_disconnect') -> RuntimeModeReport:
        previous = self.active_connection
        detail = (
            f'Disconnected {previous.mode} target {previous.target}'
            if previous is not None
            else 'No active remote connection was present.'
        )
        if previous is not None:
            self._append_history(
                {
                    'action': 'disconnect',
                    'mode': previous.mode,
                    'target': previous.target,
                    'profile_name': previous.profile_name,
                    'reason': reason,
                    'disconnected_at': _utc_now(),
                }
            )
        self.active_connection = None
        self._persist_state()
        return RuntimeModeReport(
            mode=previous.mode if previous is not None else 'remote',
            connected=False,
            detail=detail,
            manifest_count=len(self.manifests),
            profile_count=len(self.profiles),
        )

    def current_report(self, *, detail: str | None = None) -> RuntimeModeReport:
        if self.active_connection is None:
            return RuntimeModeReport(
                mode='remote',
                connected=False,
                detail=detail or 'No active remote connection.',
                manifest_count=len(self.manifests),
                profile_count=len(self.profiles),
            )
        connection = self.active_connection
        return RuntimeModeReport(
            mode=connection.mode,
            connected=connection.connected,
            detail=detail or f'Active {connection.mode} connection for {connection.target}',
            target=connection.target,
            profile_name=connection.profile_name,
            workspace_cwd=connection.workspace_cwd,
            session_url=connection.session_url,
            source_manifest=connection.source_manifest,
            manifest_count=len(self.manifests),
            profile_count=len(self.profiles),
            metadata=dict(connection.metadata),
        )

    def render_summary(self) -> str:
        lines = [
            f'Local remote manifests: {len(self.manifests)}',
            f'Configured remote profiles: {len(self.profiles)}',
        ]
        if self.active_connection is None:
            lines.append('- Active remote connection: none')
        else:
            connection = self.active_connection
            active = f'- Active remote connection: {connection.mode} -> {connection.target}'
            if connection.profile_name:
                active += f' (profile={connection.profile_name})'
            lines.append(active)
            if connection.workspace_cwd:
                lines.append(f'- Active remote workspace: {connection.workspace_cwd}')
            if connection.session_url:
                lines.append(f'- Active remote session URL: {connection.session_url}')
        for profile in self.profiles[:10]:
            parts = [profile.name, f'mode={profile.mode}', f'target={profile.target}']
            if profile.workspace_cwd:
                parts.append(f'workspace={profile.workspace_cwd}')
            if profile.session_url:
                parts.append(f'session_url={profile.session_url}')
            lines.append('- ' + '; '.join(parts))
        if self.history:
            lines.append(f'- Runtime history entries: {len(self.history)}')
        return '\n'.join(lines)

    def render_profiles_index(
        self,
        *,
        query: str | None = None,
        mode: str | None = None,
        limit: int = 20,
    ) -> str:
        profiles = self.list_profiles(query=query, mode=mode, limit=limit)
        if not profiles:
            return '# Remote Profiles\n\nNo matching remote profiles discovered.'
        lines = ['# Remote Profiles', '']
        for profile in profiles:
            details = [profile.name, f'mode={profile.mode}', f'target={profile.target}']
            if profile.workspace_cwd:
                details.append(f'workspace={profile.workspace_cwd}')
            if profile.session_url:
                details.append(f'session_url={profile.session_url}')
            if profile.description:
                details.append(f'description={profile.description}')
            lines.append('- ' + '; '.join(details))
        return '\n'.join(lines)

    def render_profile(self, name_or_target: str) -> str:
        profile = self.get_profile(name_or_target)
        if profile is None:
            return f'# Remote Profile\n\nUnknown remote profile: {name_or_target}'
        lines = [
            '# Remote Profile',
            '',
            f'- Name: {profile.name}',
            f'- Mode: {profile.mode}',
            f'- Target: {profile.target}',
            f'- Source manifest: {profile.source_manifest}',
        ]
        if profile.description:
            lines.append(f'- Description: {profile.description}')
        if profile.workspace_cwd:
            lines.append(f'- Workspace: {profile.workspace_cwd}')
        if profile.session_url:
            lines.append(f'- Session URL: {profile.session_url}')
        if profile.env:
            lines.append('- Environment values:')
            lines.extend(f'  - {key}={value}' for key, value in sorted(profile.env.items()))
        if profile.metadata:
            lines.append('- Metadata:')
            lines.extend(f'  - {key}={value}' for key, value in sorted(profile.metadata.items()))
        return '\n'.join(lines)

    def _persist_state(self) -> None:
        payload = {
            'active_connection': (
                asdict(self.active_connection) if self.active_connection is not None else None
            ),
            'history': list(self.history),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding='utf-8',
        )

    def _append_history(self, entry: dict[str, Any]) -> None:
        merged = [*self.history, dict(entry)]
        self.history = tuple(merged[-40:])


def run_remote_mode(
    target: str,
    *,
    cwd: Path | None = None,
    additional_working_directories: tuple[str, ...] = (),
) -> RuntimeModeReport:
    runtime = RemoteRuntime.from_workspace(
        cwd or Path.cwd(),
        additional_working_directories=additional_working_directories,
    )
    return runtime.connect(target, mode='remote')


def run_ssh_mode(
    target: str,
    *,
    cwd: Path | None = None,
    additional_working_directories: tuple[str, ...] = (),
) -> RuntimeModeReport:
    runtime = RemoteRuntime.from_workspace(
        cwd or Path.cwd(),
        additional_working_directories=additional_working_directories,
    )
    return runtime.connect(target, mode='ssh')


def run_teleport_mode(
    target: str,
    *,
    cwd: Path | None = None,
    additional_working_directories: tuple[str, ...] = (),
) -> RuntimeModeReport:
    runtime = RemoteRuntime.from_workspace(
        cwd or Path.cwd(),
        additional_working_directories=additional_working_directories,
    )
    return runtime.connect(target, mode='teleport')


def run_direct_connect_mode(
    target: str,
    *,
    cwd: Path | None = None,
    additional_working_directories: tuple[str, ...] = (),
) -> RuntimeModeReport:
    runtime = RemoteRuntime.from_workspace(
        cwd or Path.cwd(),
        additional_working_directories=additional_working_directories,
    )
    return runtime.connect(target, mode='direct-connect')


def run_deep_link_mode(
    target: str,
    *,
    cwd: Path | None = None,
    additional_working_directories: tuple[str, ...] = (),
) -> RuntimeModeReport:
    runtime = RemoteRuntime.from_workspace(
        cwd or Path.cwd(),
        additional_working_directories=additional_working_directories,
    )
    return runtime.connect(target, mode='deep-link')


def _discover_manifest_paths(
    cwd: Path,
    additional_working_directories: tuple[str, ...],
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    seen: set[Path] = set()

    def remember(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not resolved.exists() or not resolved.is_file():
            return
        seen.add(resolved)
        candidates.append(resolved)

    roots: list[Path] = []
    current = cwd.resolve()
    while True:
        roots.append(current)
        if current.parent == current:
            break
        current = current.parent
    roots.extend(Path(path).resolve() for path in additional_working_directories)

    for root in roots:
        remember(root / '.claw-remote.json')
        remember(root / '.remote.json')
        remember(root / '.codex-remote.json')
        remember(root / 'remote.json')
    return tuple(candidates)


def _load_profiles_from_manifest(path: Path) -> list[RemoteProfile]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    profiles: list[RemoteProfile] = []
    raw_profiles = payload.get('profiles')
    if isinstance(raw_profiles, list):
        profiles.extend(_extract_profiles(raw_profiles, manifest_path=path))
    elif _looks_like_profile(payload):
        profile = _profile_from_item(payload, manifest_path=path)
        if profile is not None:
            profiles.append(profile)
    remotes = payload.get('remotes')
    if isinstance(remotes, list):
        profiles.extend(_extract_profiles(remotes, manifest_path=path))
    return profiles


def _extract_profiles(raw_profiles: list[Any], *, manifest_path: Path) -> list[RemoteProfile]:
    profiles: list[RemoteProfile] = []
    seen_names: set[str] = set()
    for item in raw_profiles:
        profile = _profile_from_item(item, manifest_path=manifest_path)
        if profile is None or profile.name.lower() in seen_names:
            continue
        seen_names.add(profile.name.lower())
        profiles.append(profile)
    return profiles


def _profile_from_item(item: Any, *, manifest_path: Path) -> RemoteProfile | None:
    if not isinstance(item, dict):
        return None
    name = item.get('name')
    target = item.get('target')
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(target, str) or not target.strip():
        return None
    mode = _normalize_mode(str(item.get('mode', 'remote')))
    workspace_cwd = _optional_string(
        item.get('workspaceCwd')
        if item.get('workspaceCwd') is not None
        else item.get('workspace_cwd')
    )
    session_url = _optional_string(
        item.get('sessionUrl')
        if item.get('sessionUrl') is not None
        else item.get('session_url')
    )
    description = _optional_string(item.get('description'))
    env = item.get('env')
    metadata = item.get('metadata')
    return RemoteProfile(
        name=name.strip(),
        mode=mode,
        target=target.strip(),
        source_manifest=str(manifest_path),
        description=description,
        workspace_cwd=workspace_cwd,
        session_url=session_url,
        env=(
            {
                str(key): str(value)
                for key, value in env.items()
                if isinstance(key, str) and isinstance(value, (str, int, float, bool))
            }
            if isinstance(env, dict)
            else {}
        ),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _looks_like_profile(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get('name'), str) and isinstance(payload.get('target'), str)


def _load_state_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _connection_from_payload(payload: Any) -> RemoteConnectionState | None:
    if not isinstance(payload, dict):
        return None
    mode = _optional_string(payload.get('mode'))
    target = _optional_string(payload.get('target'))
    connected_at = _optional_string(payload.get('connected_at'))
    if mode is None or target is None or connected_at is None:
        return None
    metadata = payload.get('metadata')
    return RemoteConnectionState(
        mode=_normalize_mode(mode),
        target=target,
        connected=bool(payload.get('connected', True)),
        connected_at=connected_at,
        profile_name=_optional_string(payload.get('profile_name')),
        workspace_cwd=_optional_string(payload.get('workspace_cwd')),
        session_url=_optional_string(payload.get('session_url')),
        source_manifest=_optional_string(payload.get('source_manifest')),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower().replace('_', '-')
    if normalized == 'direct':
        normalized = 'direct-connect'
    if normalized == 'deeplink':
        normalized = 'deep-link'
    if normalized not in SUPPORTED_REMOTE_MODES:
        return 'remote'
    return normalized


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
