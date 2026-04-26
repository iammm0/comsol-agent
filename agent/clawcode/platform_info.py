"""Platform detection and system directories — Python ports of
``utils/platform.ts`` and ``utils/systemDirectories.ts``.

The npm functions are memoized via lodash; here a module-level cache plus
``_reset_cache`` (test-only) provides equivalent behavior. Detection is
cheap enough that callers can also bypass the cache by passing explicit
overrides to ``get_system_directories``.
"""

from __future__ import annotations

import os
import platform as _stdlib_platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Platform = Literal['macos', 'windows', 'wsl', 'linux', 'unknown']

SUPPORTED_PLATFORMS: tuple[Platform, ...] = ('macos', 'wsl')


_UNSET = object()
_platform_cache: Platform | None = None
_wsl_version_cache: object = _UNSET  # sentinel until first computation


def _reset_cache() -> None:
    """Clear cached platform detection — only used by tests."""
    global _platform_cache, _wsl_version_cache
    _platform_cache = None
    _wsl_version_cache = _UNSET


def _read_proc_version() -> str:
    return Path('/proc/version').read_text(encoding='utf-8')


def get_platform() -> Platform:
    """Return the current platform identifier (memoized)."""
    global _platform_cache
    if _platform_cache is not None:
        return _platform_cache

    if sys.platform == 'darwin':
        _platform_cache = 'macos'
    elif sys.platform.startswith('win'):
        _platform_cache = 'windows'
    elif sys.platform.startswith('linux'):
        try:
            proc_version = _read_proc_version().lower()
            if 'microsoft' in proc_version or 'wsl' in proc_version:
                _platform_cache = 'wsl'
            else:
                _platform_cache = 'linux'
        except OSError:
            _platform_cache = 'linux'
    else:
        _platform_cache = 'unknown'
    return _platform_cache


def get_wsl_version() -> str | None:
    """Return the WSL major version (`'1'`/`'2'`/...), or None if not WSL."""
    global _wsl_version_cache
    if _wsl_version_cache is not _UNSET:
        return _wsl_version_cache  # type: ignore[return-value]

    result: str | None = None
    if sys.platform.startswith('linux'):
        try:
            proc_version = _read_proc_version()
        except OSError:
            proc_version = ''
        if proc_version:
            import re
            match = re.search(r'WSL(\d+)', proc_version, re.IGNORECASE)
            if match:
                result = match.group(1)
            elif 'microsoft' in proc_version.lower():
                result = '1'
    _wsl_version_cache = result
    return result


@dataclass(frozen=True)
class LinuxDistroInfo:
    linux_distro_id: str | None = None
    linux_distro_version: str | None = None
    linux_kernel: str | None = None

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.linux_distro_id is not None:
            out['linuxDistroId'] = self.linux_distro_id
        if self.linux_distro_version is not None:
            out['linuxDistroVersion'] = self.linux_distro_version
        if self.linux_kernel is not None:
            out['linuxKernel'] = self.linux_kernel
        return out


def get_linux_distro_info() -> LinuxDistroInfo | None:
    """Return distro id/version/kernel on Linux, or None on other platforms."""
    if not sys.platform.startswith('linux'):
        return None

    distro_id: str | None = None
    distro_version: str | None = None
    try:
        content = Path('/etc/os-release').read_text(encoding='utf-8')
    except OSError:
        content = ''
    for line in content.splitlines():
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        value = value.strip().strip('"')
        if key == 'ID':
            distro_id = value
        elif key == 'VERSION_ID':
            distro_version = value

    return LinuxDistroInfo(
        linux_distro_id=distro_id,
        linux_distro_version=distro_version,
        linux_kernel=_stdlib_platform.release() or None,
    )


_VCS_MARKERS: tuple[tuple[str, str], ...] = (
    ('.git', 'git'),
    ('.hg', 'mercurial'),
    ('.svn', 'svn'),
    ('.p4config', 'perforce'),
    ('$tf', 'tfs'),
    ('.tfvc', 'tfs'),
    ('.jj', 'jujutsu'),
    ('.sl', 'sapling'),
)


def detect_vcs(directory: str | os.PathLike[str] | None = None) -> list[str]:
    """Detect VCS systems by marker files in ``directory`` (defaults to cwd)."""
    detected: set[str] = set()
    if os.environ.get('P4PORT'):
        detected.add('perforce')

    target = Path(directory) if directory is not None else Path.cwd()
    try:
        entries = {entry.name for entry in target.iterdir()}
    except OSError:
        entries = set()

    for marker, vcs in _VCS_MARKERS:
        if marker in entries:
            detected.add(vcs)

    return sorted(detected)


# ---------------------------------------------------------------------------
# systemDirectories.ts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SystemDirectories:
    HOME: str
    DESKTOP: str
    DOCUMENTS: str
    DOWNLOADS: str

    def to_dict(self) -> dict[str, str]:
        return {
            'HOME': self.HOME,
            'DESKTOP': self.DESKTOP,
            'DOCUMENTS': self.DOCUMENTS,
            'DOWNLOADS': self.DOWNLOADS,
        }


def get_system_directories(
    *,
    env: dict[str, str] | None = None,
    home_dir: str | None = None,
    platform: Platform | None = None,
) -> SystemDirectories:
    """Cross-platform system directories matching ``getSystemDirectories``."""
    chosen_platform: Platform = platform if platform is not None else get_platform()
    chosen_home = home_dir if home_dir is not None else str(Path.home())
    chosen_env = env if env is not None else dict(os.environ)

    defaults = SystemDirectories(
        HOME=chosen_home,
        DESKTOP=str(Path(chosen_home) / 'Desktop'),
        DOCUMENTS=str(Path(chosen_home) / 'Documents'),
        DOWNLOADS=str(Path(chosen_home) / 'Downloads'),
    )

    if chosen_platform == 'windows':
        user_profile = chosen_env.get('USERPROFILE') or chosen_home
        return SystemDirectories(
            HOME=chosen_home,
            DESKTOP=str(Path(user_profile) / 'Desktop'),
            DOCUMENTS=str(Path(user_profile) / 'Documents'),
            DOWNLOADS=str(Path(user_profile) / 'Downloads'),
        )

    if chosen_platform in ('linux', 'wsl'):
        return SystemDirectories(
            HOME=chosen_home,
            DESKTOP=chosen_env.get('XDG_DESKTOP_DIR') or defaults.DESKTOP,
            DOCUMENTS=chosen_env.get('XDG_DOCUMENTS_DIR') or defaults.DOCUMENTS,
            DOWNLOADS=chosen_env.get('XDG_DOWNLOAD_DIR') or defaults.DOWNLOADS,
        )

    # macOS and unknown both use the defaults.
    return defaults


__all__ = [
    'Platform',
    'SUPPORTED_PLATFORMS',
    'get_platform',
    'get_wsl_version',
    'LinuxDistroInfo',
    'get_linux_distro_info',
    'detect_vcs',
    'SystemDirectories',
    'get_system_directories',
]
