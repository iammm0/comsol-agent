from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_WORKTREE_STATE_FILE = 'claw_worktree_runtime.json'
DEFAULT_WORKTREE_PARENT_SUFFIX = '-claw-worktrees'
VALID_EXIT_ACTIONS = ('keep', 'remove')
_WORKTREE_SLUG_RE = re.compile(r'^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$')


@dataclass(frozen=True)
class WorktreeSessionState:
    name: str
    repo_root: str
    common_git_dir: str
    worktree_path: str
    worktree_branch: str
    original_cwd: str
    original_head_commit: str | None
    created_at: str


@dataclass(frozen=True)
class WorktreeStatusReport:
    active: bool
    detail: str
    repo_root: str | None = None
    common_git_dir: str | None = None
    current_cwd: str | None = None
    original_cwd: str | None = None
    worktree_path: str | None = None
    worktree_branch: str | None = None
    session_name: str | None = None
    state_path: str | None = None
    history_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        lines = [
            f'active={self.active}',
            f'detail={self.detail}',
            f'history_count={self.history_count}',
        ]
        for key in (
            'repo_root',
            'common_git_dir',
            'current_cwd',
            'original_cwd',
            'worktree_path',
            'worktree_branch',
            'session_name',
            'state_path',
        ):
            value = getattr(self, key)
            if value:
                lines.append(f'{key}={value}')
        for key, value in sorted(self.metadata.items()):
            lines.append(f'metadata.{key}={value}')
        return '\n'.join(lines)


@dataclass
class WorktreeRuntime:
    cwd: Path
    state_path: Path
    repo_root: Path | None = None
    common_git_dir: Path | None = None
    active_session: WorktreeSessionState | None = None
    history: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def from_workspace(cls, cwd: Path) -> 'WorktreeRuntime':
        resolved_cwd = cwd.resolve()
        common_git_dir = _find_git_common_dir(resolved_cwd)
        repo_root = _infer_repo_root(resolved_cwd, common_git_dir)
        state_path = (
            common_git_dir / DEFAULT_WORKTREE_STATE_FILE
            if common_git_dir is not None
            else (resolved_cwd / '.port_sessions' / 'worktree_runtime.json')
        )
        payload = _load_payload(state_path)
        active_payload = payload.get('active_session')
        history_payload = payload.get('history')
        return cls(
            cwd=resolved_cwd,
            state_path=state_path,
            repo_root=repo_root,
            common_git_dir=common_git_dir,
            active_session=_session_from_payload(active_payload),
            history=tuple(
                item for item in history_payload if isinstance(item, dict)
            ) if isinstance(history_payload, list) else (),
        )

    def has_state(self) -> bool:
        return self.active_session is not None or bool(self.history)

    def current_report(self, *, detail: str | None = None) -> WorktreeStatusReport:
        if self.active_session is None:
            return WorktreeStatusReport(
                active=False,
                detail=detail or 'No active managed worktree session.',
                repo_root=str(self.repo_root) if self.repo_root is not None else None,
                common_git_dir=(
                    str(self.common_git_dir) if self.common_git_dir is not None else None
                ),
                current_cwd=str(self.cwd),
                state_path=str(self.state_path),
                history_count=len(self.history),
            )
        active = self.active_session
        return WorktreeStatusReport(
            active=True,
            detail=detail or f'Active worktree session {active.name}',
            repo_root=active.repo_root,
            common_git_dir=active.common_git_dir,
            current_cwd=str(self.cwd),
            original_cwd=active.original_cwd,
            worktree_path=active.worktree_path,
            worktree_branch=active.worktree_branch,
            session_name=active.name,
            state_path=str(self.state_path),
            history_count=len(self.history),
        )

    def render_summary(self) -> str:
        lines = ['# Worktree', '']
        report = self.current_report()
        lines.extend(
            [
                f'- Git repo detected: {self.repo_root is not None}',
                f'- Active managed worktree: {report.active}',
                f'- Current working directory: {self.cwd}',
                f'- Worktree history entries: {len(self.history)}',
            ]
        )
        if self.repo_root is not None:
            lines.append(f'- Repo root: {self.repo_root}')
        if self.common_git_dir is not None:
            lines.append(f'- Common git dir: {self.common_git_dir}')
        if self.active_session is None:
            lines.append('- Active worktree path: none')
            lines.append('- Original working directory: none')
        else:
            active = self.active_session
            lines.append(f'- Active worktree path: {active.worktree_path}')
            lines.append(f'- Active worktree branch: {active.worktree_branch}')
            lines.append(f'- Original working directory: {active.original_cwd}')
        return '\n'.join(lines)

    def render_history(self) -> str:
        lines = ['# Worktree History', '']
        if not self.history:
            lines.append('No worktree history recorded.')
            return '\n'.join(lines)
        for entry in self.history:
            action = entry.get('action', 'unknown')
            timestamp = entry.get('timestamp', 'unknown')
            name = entry.get('name') or entry.get('worktree_name') or 'unknown'
            path = entry.get('worktree_path', 'unknown')
            lines.append(f'- {timestamp} ; {action} ; {name} ; {path}')
        return '\n'.join(lines)

    def enter(self, name: str | None = None) -> WorktreeStatusReport:
        if self.active_session is not None:
            raise RuntimeError('A managed worktree session is already active.')
        if self.repo_root is None or self.common_git_dir is None:
            raise RuntimeError('A git repository is required to create a managed worktree.')
        slug = _normalize_slug(name)
        worktree_parent = self.repo_root.parent / f'{self.repo_root.name}{DEFAULT_WORKTREE_PARENT_SUFFIX}'
        worktree_path = (worktree_parent / slug).resolve()
        branch = f'claw/{slug}'
        if worktree_path.exists():
            raise RuntimeError(f'Worktree path already exists: {worktree_path}')
        if _branch_exists(self.repo_root, branch):
            raise RuntimeError(f'Worktree branch already exists: {branch}')
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        _run_git(
            self.repo_root,
            ['worktree', 'add', '-b', branch, str(worktree_path), 'HEAD'],
        )
        active = WorktreeSessionState(
            name=slug,
            repo_root=str(self.repo_root),
            common_git_dir=str(self.common_git_dir),
            worktree_path=str(worktree_path),
            worktree_branch=branch,
            original_cwd=str(self.cwd),
            original_head_commit=_git_head(self.repo_root),
            created_at=_utc_now(),
        )
        self.active_session = active
        self.cwd = Path(active.worktree_path)
        self._append_history(
            {
                'action': 'enter',
                'timestamp': active.created_at,
                'name': active.name,
                'repo_root': active.repo_root,
                'original_cwd': active.original_cwd,
                'worktree_path': active.worktree_path,
                'worktree_branch': active.worktree_branch,
            }
        )
        self._persist_state()
        return self.current_report(
            detail=(
                f'Created worktree at {active.worktree_path} on branch {active.worktree_branch}. '
                'The session should now work inside the managed worktree.'
            )
        )

    def exit(
        self,
        *,
        action: str = 'keep',
        discard_changes: bool = False,
    ) -> WorktreeStatusReport:
        normalized_action = action.strip().lower()
        if normalized_action not in VALID_EXIT_ACTIONS:
            raise ValueError(f'action must be one of {", ".join(VALID_EXIT_ACTIONS)}')
        active = self.active_session
        if active is None:
            raise RuntimeError('No managed worktree session is currently active.')
        worktree_path = Path(active.worktree_path)
        if normalized_action == 'remove':
            change_summary = _count_worktree_changes(
                worktree_path,
                active.original_head_commit,
            )
            if change_summary is None and not discard_changes:
                raise RuntimeError(
                    'Could not verify worktree cleanliness. Re-run with discard_changes=true to remove it.'
                )
            if change_summary is not None:
                changed_files, commits = change_summary
                if (changed_files > 0 or commits > 0) and not discard_changes:
                    raise RuntimeError(
                        'Worktree has uncommitted files or commits. '
                        'Re-run with discard_changes=true to remove it.'
                    )
            _run_git(Path(active.repo_root), ['worktree', 'remove', '--force', active.worktree_path])
            _run_git(Path(active.repo_root), ['branch', '-D', active.worktree_branch], check=False)
        self._append_history(
            {
                'action': f'exit_{normalized_action}',
                'timestamp': _utc_now(),
                'name': active.name,
                'repo_root': active.repo_root,
                'original_cwd': active.original_cwd,
                'worktree_path': active.worktree_path,
                'worktree_branch': active.worktree_branch,
                'discard_changes': discard_changes,
            }
        )
        self.active_session = None
        self.cwd = Path(active.original_cwd)
        self._persist_state()
        return WorktreeStatusReport(
            active=False,
            detail=(
                f'Exited managed worktree {active.name} and returned to {active.original_cwd}.'
                if normalized_action == 'keep'
                else (
                    f'Removed managed worktree {active.name} and returned to {active.original_cwd}.'
                )
            ),
            repo_root=active.repo_root,
            common_git_dir=active.common_git_dir,
            current_cwd=active.original_cwd,
            original_cwd=active.original_cwd,
            worktree_path=active.worktree_path,
            worktree_branch=active.worktree_branch,
            session_name=active.name,
            state_path=str(self.state_path),
            history_count=len(self.history),
            metadata={
                'action': normalized_action,
                'discard_changes': discard_changes,
            },
        )

    def _append_history(self, entry: dict[str, Any]) -> None:
        self.history = (*self.history, dict(entry))

    def _persist_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'active_session': (
                asdict(self.active_session) if self.active_session is not None else None
            ),
            'history': [dict(entry) for entry in self.history[-64:]],
        }
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding='utf-8',
        )


def _normalize_slug(raw_name: str | None) -> str:
    if raw_name is None or not raw_name.strip():
        return f'worktree-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}'
    candidate = raw_name.strip()
    if len(candidate) > 64 or not _WORKTREE_SLUG_RE.match(candidate):
        raise ValueError(
            'worktree name may contain only letters, digits, dots, underscores, dashes, '
            'and optional "/" separators, with a maximum length of 64 characters'
        )
    return candidate


def _find_git_common_dir(cwd: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ['git', '-C', str(cwd), 'rev-parse', '--git-common-dir'],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    output = completed.stdout.strip()
    if not output:
        return None
    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = (cwd / candidate).resolve()
    return candidate.resolve()


def _infer_repo_root(cwd: Path, common_git_dir: Path | None) -> Path | None:
    if common_git_dir is not None and common_git_dir.name == '.git':
        return common_git_dir.parent.resolve()
    try:
        completed = subprocess.run(
            ['git', '-C', str(cwd), 'rev-parse', '--show-toplevel'],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    output = completed.stdout.strip()
    return Path(output).resolve() if output else None


def _load_payload(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        payload = json.loads(state_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _session_from_payload(payload: Any) -> WorktreeSessionState | None:
    if not isinstance(payload, dict):
        return None
    required_keys = (
        'name',
        'repo_root',
        'common_git_dir',
        'worktree_path',
        'worktree_branch',
        'original_cwd',
        'created_at',
    )
    if not all(isinstance(payload.get(key), str) and payload.get(key) for key in required_keys):
        return None
    return WorktreeSessionState(
        name=str(payload['name']),
        repo_root=str(payload['repo_root']),
        common_git_dir=str(payload['common_git_dir']),
        worktree_path=str(payload['worktree_path']),
        worktree_branch=str(payload['worktree_branch']),
        original_cwd=str(payload['original_cwd']),
        original_head_commit=(
            str(payload['original_head_commit'])
            if isinstance(payload.get('original_head_commit'), str)
            else None
        ),
        created_at=str(payload['created_at']),
    )


def _run_git(repo_root: Path, arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['git', '-C', str(repo_root), *arguments],
        check=check,
        capture_output=True,
        text=True,
    )


def _branch_exists(repo_root: Path, branch: str) -> bool:
    completed = _run_git(
        repo_root,
        ['show-ref', '--verify', '--quiet', f'refs/heads/{branch}'],
        check=False,
    )
    return completed.returncode == 0


def _git_head(repo_root: Path) -> str | None:
    completed = _run_git(repo_root, ['rev-parse', 'HEAD'], check=False)
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _count_worktree_changes(worktree_path: Path, original_head_commit: str | None) -> tuple[int, int] | None:
    status = subprocess.run(
        ['git', '-C', str(worktree_path), 'status', '--porcelain'],
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        return None
    changed_files = len([line for line in status.stdout.splitlines() if line.strip()])
    if not original_head_commit:
        return None
    rev_list = subprocess.run(
        ['git', '-C', str(worktree_path), 'rev-list', '--count', f'{original_head_commit}..HEAD'],
        check=False,
        capture_output=True,
        text=True,
    )
    if rev_list.returncode != 0:
        return None
    try:
        commits = int(rev_list.stdout.strip() or '0')
    except ValueError:
        commits = 0
    return changed_files, commits


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
