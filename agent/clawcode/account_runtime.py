from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ACCOUNT_STATE_DIR = Path('.port_sessions')
DEFAULT_ACCOUNT_STATE_FILE = DEFAULT_ACCOUNT_STATE_DIR / 'account_runtime.json'
ACCOUNT_MANIFEST_PATHS = (
    Path('.claw-account.json'),
    Path('.claude/account.json'),
    Path('.claude/auth.json'),
)
CREDENTIAL_ENV_VARS = (
    'OPENAI_API_KEY',
    'ANTHROPIC_API_KEY',
    'OPENROUTER_API_KEY',
    'LITELLM_MASTER_KEY',
)


@dataclass(frozen=True)
class AccountProfile:
    name: str
    provider: str
    identity: str
    source_manifest: str
    description: str | None = None
    org: str | None = None
    auth_mode: str | None = None
    api_base: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccountSessionState:
    provider: str
    identity: str
    logged_in: bool
    logged_in_at: str
    profile_name: str | None = None
    org: str | None = None
    auth_mode: str | None = None
    api_base: str | None = None
    source_manifest: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccountStatusReport:
    logged_in: bool
    detail: str
    provider: str | None = None
    identity: str | None = None
    profile_name: str | None = None
    org: str | None = None
    auth_mode: str | None = None
    api_base: str | None = None
    source_manifest: str | None = None
    manifest_count: int = 0
    profile_count: int = 0
    credential_env_vars: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        lines = [
            f'logged_in={self.logged_in}',
            f'detail={self.detail}',
            f'manifest_count={self.manifest_count}',
            f'profile_count={self.profile_count}',
        ]
        if self.provider:
            lines.append(f'provider={self.provider}')
        if self.identity:
            lines.append(f'identity={self.identity}')
        if self.profile_name:
            lines.append(f'profile={self.profile_name}')
        if self.org:
            lines.append(f'org={self.org}')
        if self.auth_mode:
            lines.append(f'auth_mode={self.auth_mode}')
        if self.api_base:
            lines.append(f'api_base={self.api_base}')
        if self.source_manifest:
            lines.append(f'source_manifest={self.source_manifest}')
        if self.credential_env_vars:
            lines.append('credential_env=' + ','.join(self.credential_env_vars))
        if self.metadata:
            for key, value in sorted(self.metadata.items()):
                lines.append(f'metadata.{key}={value}')
        return '\n'.join(lines)


@dataclass
class AccountRuntime:
    cwd: Path
    profiles: tuple[AccountProfile, ...] = field(default_factory=tuple)
    manifests: tuple[str, ...] = field(default_factory=tuple)
    state_path: Path = field(default_factory=lambda: DEFAULT_ACCOUNT_STATE_FILE.resolve())
    active_session: AccountSessionState | None = None
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    credential_env_vars: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'AccountRuntime':
        manifest_paths = _discover_manifest_paths(cwd, additional_working_directories)
        profiles: list[AccountProfile] = []
        for manifest_path in manifest_paths:
            profiles.extend(_load_profiles_from_manifest(manifest_path))
        state_path = (cwd.resolve() / DEFAULT_ACCOUNT_STATE_FILE).resolve()
        payload = _load_state_payload(state_path)
        active_session = _session_from_payload(payload.get('active_session'))
        history_payload = payload.get('history')
        history = tuple(
            item for item in history_payload if isinstance(item, dict)
        ) if isinstance(history_payload, list) else ()
        return cls(
            cwd=cwd.resolve(),
            profiles=tuple(profiles),
            manifests=tuple(str(path) for path in manifest_paths),
            state_path=state_path,
            active_session=active_session,
            history=history,
            credential_env_vars=_detect_credential_env_vars(),
        )

    def has_account_state(self) -> bool:
        return bool(self.profiles or self.active_session is not None or self.credential_env_vars)

    def list_profiles(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> tuple[AccountProfile, ...]:
        profiles = self.profiles
        if query:
            needle = query.lower()
            profiles = tuple(
                profile
                for profile in profiles
                if needle in profile.name.lower()
                or needle in profile.provider.lower()
                or needle in profile.identity.lower()
                or needle in (profile.org or '').lower()
            )
        if limit is not None and limit >= 0:
            profiles = profiles[:limit]
        return profiles

    def get_profile(self, name_or_identity: str) -> AccountProfile | None:
        needle = name_or_identity.strip().lower()
        if not needle:
            return None
        for profile in self.profiles:
            if profile.name.lower() == needle or profile.identity.lower() == needle:
                return profile
        return None

    def login(
        self,
        target: str,
        *,
        provider: str | None = None,
        auth_mode: str | None = None,
    ) -> AccountStatusReport:
        profile = self.get_profile(target)
        if profile is not None:
            session = AccountSessionState(
                provider=profile.provider,
                identity=profile.identity,
                logged_in=True,
                logged_in_at=_utc_now(),
                profile_name=profile.name,
                org=profile.org,
                auth_mode=profile.auth_mode,
                api_base=profile.api_base,
                source_manifest=profile.source_manifest,
                metadata=dict(profile.metadata),
            )
            detail = f'Activated account profile {profile.name}'
        else:
            session = AccountSessionState(
                provider=(provider or 'custom').strip() or 'custom',
                identity=target.strip(),
                logged_in=True,
                logged_in_at=_utc_now(),
                auth_mode=(auth_mode or 'token').strip() or 'token',
                metadata={'ephemeral': True},
            )
            detail = f'Activated ephemeral account identity {target.strip()}'
        self.active_session = session
        self._append_history(
            {
                'action': 'login',
                'provider': session.provider,
                'identity': session.identity,
                'profile_name': session.profile_name,
                'logged_in_at': session.logged_in_at,
            }
        )
        self._persist_state()
        return self.current_report(detail=detail)

    def logout(self, *, reason: str = 'manual_logout') -> AccountStatusReport:
        previous = self.active_session
        detail = (
            f'Logged out {previous.identity}'
            if previous is not None
            else 'No active account session was present.'
        )
        if previous is not None:
            self._append_history(
                {
                    'action': 'logout',
                    'provider': previous.provider,
                    'identity': previous.identity,
                    'profile_name': previous.profile_name,
                    'reason': reason,
                    'logged_out_at': _utc_now(),
                }
            )
        self.active_session = None
        self._persist_state()
        return AccountStatusReport(
            logged_in=False,
            detail=detail,
            manifest_count=len(self.manifests),
            profile_count=len(self.profiles),
            credential_env_vars=self.credential_env_vars,
        )

    def current_report(self, *, detail: str | None = None) -> AccountStatusReport:
        if self.active_session is None:
            return AccountStatusReport(
                logged_in=False,
                detail=detail or 'No active account session.',
                manifest_count=len(self.manifests),
                profile_count=len(self.profiles),
                credential_env_vars=self.credential_env_vars,
            )
        session = self.active_session
        return AccountStatusReport(
            logged_in=session.logged_in,
            detail=detail or f'Active account session for {session.identity}',
            provider=session.provider,
            identity=session.identity,
            profile_name=session.profile_name,
            org=session.org,
            auth_mode=session.auth_mode,
            api_base=session.api_base,
            source_manifest=session.source_manifest,
            manifest_count=len(self.manifests),
            profile_count=len(self.profiles),
            credential_env_vars=self.credential_env_vars,
            metadata=dict(session.metadata),
        )

    def render_summary(self) -> str:
        lines = [
            f'Local account manifests: {len(self.manifests)}',
            f'Configured account profiles: {len(self.profiles)}',
        ]
        if self.credential_env_vars:
            lines.append('- Credential env vars: ' + ', '.join(self.credential_env_vars))
        for profile in self.profiles[:5]:
            details = [profile.name, profile.provider, profile.identity]
            if profile.org:
                details.append(f'org={profile.org}')
            if profile.auth_mode:
                details.append(f'auth_mode={profile.auth_mode}')
            lines.append('- Profile: ' + ' ; '.join(details))
        if self.active_session is None:
            lines.append('- Active account session: none')
        else:
            session = self.active_session
            lines.append(
                f'- Active account session: {session.provider} / {session.identity}'
            )
            if session.profile_name:
                lines.append(f'  - profile: {session.profile_name}')
            if session.auth_mode:
                lines.append(f'  - auth_mode: {session.auth_mode}')
            if session.org:
                lines.append(f'  - org: {session.org}')
            if session.api_base:
                lines.append(f'  - api_base: {session.api_base}')
        return '\n'.join(lines)

    def render_profile(self, name_or_identity: str) -> str:
        profile = self.get_profile(name_or_identity)
        if profile is None:
            return f'# Account Profile\n\nUnknown account profile: {name_or_identity}'
        lines = [
            '# Account Profile',
            '',
            f'- Name: {profile.name}',
            f'- Provider: {profile.provider}',
            f'- Identity: {profile.identity}',
            f'- Source manifest: {profile.source_manifest}',
        ]
        if profile.org:
            lines.append(f'- Org: {profile.org}')
        if profile.auth_mode:
            lines.append(f'- Auth mode: {profile.auth_mode}')
        if profile.api_base:
            lines.append(f'- API base: {profile.api_base}')
        if profile.description:
            lines.extend(['', profile.description])
        return '\n'.join(lines)

    def render_profiles_index(self, *, query: str | None = None) -> str:
        profiles = self.list_profiles(query=query, limit=100)
        lines = ['# Account Profiles', '']
        if not profiles:
            lines.append('No local account profiles discovered.')
            return '\n'.join(lines)
        for profile in profiles:
            details = [profile.name, profile.provider, profile.identity]
            if profile.org:
                details.append(f'org={profile.org}')
            if profile.auth_mode:
                details.append(f'auth_mode={profile.auth_mode}')
            lines.append('- ' + ' ; '.join(details))
        return '\n'.join(lines)

    def _append_history(self, entry: dict[str, Any]) -> None:
        self.history = (*self.history, entry)

    def _persist_state(self) -> None:
        payload = {
            'active_session': (
                asdict(self.active_session)
                if self.active_session is not None
                else None
            ),
            'history': list(self.history[-100:]),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )


def _discover_manifest_paths(
    cwd: Path,
    additional_working_directories: tuple[str, ...],
) -> tuple[Path, ...]:
    candidate_roots = [cwd.resolve()]
    for raw_path in additional_working_directories:
        path = Path(raw_path).resolve()
        if path not in candidate_roots:
            candidate_roots.append(path)
    discovered: list[Path] = []
    seen: set[Path] = set()
    for root in candidate_roots:
        for relative_path in ACCOUNT_MANIFEST_PATHS:
            path = (root / relative_path).resolve()
            if path in seen or not path.exists() or not path.is_file():
                continue
            seen.add(path)
            discovered.append(path)
    return tuple(discovered)


def _load_profiles_from_manifest(path: Path) -> list[AccountProfile]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        profiles_payload = payload.get('profiles')
        if isinstance(profiles_payload, list):
            return [
                profile
                for item in profiles_payload
                for profile in [_profile_from_payload(item, path)]
                if profile is not None
            ]
        single = _profile_from_payload(payload, path)
        return [single] if single is not None else []
    return []


def _profile_from_payload(payload: Any, path: Path) -> AccountProfile | None:
    if not isinstance(payload, dict):
        return None
    raw_name = payload.get('name') or payload.get('profile')
    provider = payload.get('provider')
    identity = payload.get('identity') or payload.get('email') or payload.get('user')
    if not isinstance(provider, str) or not provider.strip():
        return None
    if not isinstance(identity, str) or not identity.strip():
        return None
    if not isinstance(raw_name, str) or not raw_name.strip():
        raw_name = identity
    metadata = payload.get('metadata')
    return AccountProfile(
        name=str(raw_name).strip(),
        provider=provider.strip(),
        identity=identity.strip(),
        source_manifest=str(path),
        description=_optional_str(payload.get('description')),
        org=_optional_str(payload.get('org')),
        auth_mode=_optional_str(payload.get('authMode') or payload.get('auth_mode')),
        api_base=_optional_str(payload.get('apiBase') or payload.get('api_base')),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _load_state_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _session_from_payload(payload: Any) -> AccountSessionState | None:
    if not isinstance(payload, dict):
        return None
    provider = payload.get('provider')
    identity = payload.get('identity')
    if not isinstance(provider, str) or not provider.strip():
        return None
    if not isinstance(identity, str) or not identity.strip():
        return None
    metadata = payload.get('metadata')
    return AccountSessionState(
        provider=provider.strip(),
        identity=identity.strip(),
        logged_in=bool(payload.get('logged_in', True)),
        logged_in_at=str(payload.get('logged_in_at', _utc_now())),
        profile_name=_optional_str(payload.get('profile_name')),
        org=_optional_str(payload.get('org')),
        auth_mode=_optional_str(payload.get('auth_mode')),
        api_base=_optional_str(payload.get('api_base')),
        source_manifest=_optional_str(payload.get('source_manifest')),
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _detect_credential_env_vars() -> tuple[str, ...]:
    return tuple(
        key
        for key in CREDENTIAL_ENV_VARS
        if isinstance(os.environ.get(key), str) and os.environ.get(key, '').strip()
    )


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
