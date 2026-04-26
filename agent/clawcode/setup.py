from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .deferred_init import DeferredInitResult, run_deferred_init
from .prefetch import PrefetchResult, start_keychain_prefetch, start_mdm_raw_read, start_project_scan
from .release_notes import check_for_release_notes


MIN_PYTHON_VERSION: tuple[int, int] = (3, 10)


@dataclass(frozen=True)
class RuntimeRequirementCheck:
    name: str
    ok: bool
    detail: str


def check_runtime_requirements() -> tuple[RuntimeRequirementCheck, ...]:
    checks: list[RuntimeRequirementCheck] = []
    py_major, py_minor = sys.version_info[:2]
    py_ok = (py_major, py_minor) >= MIN_PYTHON_VERSION
    checks.append(RuntimeRequirementCheck(
        name='python_version',
        ok=py_ok,
        detail=(
            f'Python {py_major}.{py_minor} >= {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}'
            if py_ok
            else f'Python {py_major}.{py_minor} is below required '
                 f'{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}'
        ),
    ))
    impl = platform.python_implementation()
    checks.append(RuntimeRequirementCheck(
        name='python_implementation',
        ok=True,
        detail=impl,
    ))
    machine = platform.machine() or 'unknown'
    system = platform.system() or 'unknown'
    checks.append(RuntimeRequirementCheck(
        name='platform',
        ok=True,
        detail=f'{system} on {machine}',
    ))
    return tuple(checks)


def _read_package_version() -> str:
    try:
        from importlib.metadata import version

        return version('claw-code-agent')
    except Exception:
        return '0.0.0'


@dataclass(frozen=True)
class WorkspaceSetup:
    python_version: str
    implementation: str
    platform_name: str
    test_command: str = 'python3 -m unittest discover -s tests -v'

    def startup_steps(self) -> tuple[str, ...]:
        return (
            'start top-level prefetch side effects',
            'build workspace context',
            'load mirrored command snapshot',
            'load mirrored tool snapshot',
            'prepare parity audit hooks',
            'apply trust-gated deferred init',
        )


@dataclass(frozen=True)
class SetupReport:
    setup: WorkspaceSetup
    prefetches: tuple[PrefetchResult, ...]
    deferred_init: DeferredInitResult
    trusted: bool
    cwd: Path
    runtime_checks: tuple[RuntimeRequirementCheck, ...] = field(default_factory=tuple)
    release_notes: tuple[str, ...] = field(default_factory=tuple)

    def has_blocking_issues(self) -> bool:
        return any(not check.ok for check in self.runtime_checks)

    def as_markdown(self) -> str:
        lines = [
            '# Setup Report',
            '',
            f'- Python: {self.setup.python_version} ({self.setup.implementation})',
            f'- Platform: {self.setup.platform_name}',
            f'- Trusted mode: {self.trusted}',
            f'- CWD: {self.cwd}',
            '',
            'Runtime checks:',
            *(
                f'- {check.name}: {"ok" if check.ok else "FAIL"} — {check.detail}'
                for check in self.runtime_checks
            ),
            '',
            'Prefetches:',
            *(f'- {prefetch.name}: {prefetch.detail}' for prefetch in self.prefetches),
            '',
            'Deferred init:',
            *self.deferred_init.as_lines(),
        ]
        if self.release_notes:
            lines.extend(['', 'Release notes (newer than last seen):'])
            lines.extend(f'- {note}' for note in self.release_notes)
        return '\n'.join(lines)


def build_workspace_setup() -> WorkspaceSetup:
    return WorkspaceSetup(
        python_version='.'.join(str(part) for part in sys.version_info[:3]),
        implementation=platform.python_implementation(),
        platform_name=platform.platform(),
    )


def run_setup(
    cwd: Path | None = None,
    trusted: bool = True,
    last_seen_version: str | None = None,
) -> SetupReport:
    root = cwd or Path(__file__).resolve().parent.parent
    prefetches = [
        start_mdm_raw_read(),
        start_keychain_prefetch(),
        start_project_scan(root),
    ]
    release_notes_payload = check_for_release_notes(
        current_version=_read_package_version(),
        last_seen_version=last_seen_version,
        cwd=root,
    )
    return SetupReport(
        setup=build_workspace_setup(),
        prefetches=tuple(prefetches),
        deferred_init=run_deferred_init(trusted=trusted),
        trusted=trusted,
        cwd=root,
        runtime_checks=check_runtime_requirements(),
        release_notes=tuple(release_notes_payload['releaseNotes']),
    )
