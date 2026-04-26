"""IDE path conversion — Python port of ``utils/idePathConversion.ts``.

Used when Claude runs under WSL but the IDE (VS Code, JetBrains) is on the
host Windows side. Outgoing paths need to be converted to ``\\\\wsl$\\...``
form for the IDE; incoming paths from the IDE need to be converted back to
``/mnt/c/...`` form for Claude.
"""

from __future__ import annotations

import re
import subprocess
from typing import Protocol


_WSL_UNC_RE = re.compile(r'^\\\\wsl(?:\.localhost|\$)\\([^\\]+)(.*)$')
_DRIVE_RE = re.compile(r'^([A-Za-z]):')


class IDEPathConverter(Protocol):
    """Bidirectional path mapping between IDE-side and Claude-side paths."""

    def to_local_path(self, ide_path: str) -> str: ...

    def to_ide_path(self, local_path: str) -> str: ...


def _run_wslpath(flag: str, path: str) -> str:
    """Invoke ``wslpath`` and return the stripped stdout. Raises on failure."""
    completed = subprocess.run(
        ['wslpath', flag, path],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _manual_windows_to_wsl(windows_path: str) -> str:
    """Fallback when ``wslpath`` is unavailable: ``C:\\foo`` → ``/mnt/c/foo``."""
    converted = windows_path.replace('\\', '/')

    def _replace_drive(match: re.Match[str]) -> str:
        return f'/mnt/{match.group(1).lower()}'

    return _DRIVE_RE.sub(_replace_drive, converted)


class WindowsToWSLConverter:
    """Converter for the Windows IDE + WSL Claude scenario."""

    def __init__(self, wsl_distro_name: str | None) -> None:
        self.wsl_distro_name = wsl_distro_name

    def to_local_path(self, windows_path: str) -> str:
        if not windows_path:
            return windows_path

        if self.wsl_distro_name:
            unc = _WSL_UNC_RE.match(windows_path)
            if unc and unc.group(1) != self.wsl_distro_name:
                # Path belongs to a different distro — wslpath would fail.
                return windows_path

        try:
            return _run_wslpath('-u', windows_path)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return _manual_windows_to_wsl(windows_path)

    def to_ide_path(self, wsl_path: str) -> str:
        if not wsl_path:
            return wsl_path
        try:
            return _run_wslpath('-w', wsl_path)
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return wsl_path


def check_wsl_distro_match(windows_path: str, wsl_distro_name: str) -> bool:
    """True if ``windows_path`` isn't a WSL UNC path or names this distro."""
    unc = _WSL_UNC_RE.match(windows_path)
    if unc:
        return unc.group(1) == wsl_distro_name
    return True


__all__ = [
    'IDEPathConverter',
    'WindowsToWSLConverter',
    'check_wsl_distro_match',
]
