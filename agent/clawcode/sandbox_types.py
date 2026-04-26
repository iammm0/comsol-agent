"""Sandbox configuration types — Python port of entrypoints/sandboxTypes.ts.

The npm version uses Zod schemas with `.passthrough()` to forward unknown
fields. Here we mirror the same fields as dataclasses, with `from_dict`
classmethods that accept and round-trip arbitrary extra keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f'expected list[str], got {type(value).__name__}')
    return [str(item) for item in value]


def _opt_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f'expected bool, got {type(value).__name__}')
    return value


def _opt_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('expected number, got bool')
    if not isinstance(value, (int, float)):
        raise ValueError(f'expected number, got {type(value).__name__}')
    return int(value)


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class SandboxNetworkConfig:
    allowed_domains: list[str] | None = None
    allow_managed_domains_only: bool | None = None
    allow_unix_sockets: list[str] | None = None
    allow_all_unix_sockets: bool | None = None
    allow_local_binding: bool | None = None
    http_proxy_port: int | None = None
    socks_proxy_port: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SandboxNetworkConfig':
        return cls(
            allowed_domains=_str_list(data.get('allowedDomains')),
            allow_managed_domains_only=_opt_bool(data.get('allowManagedDomainsOnly')),
            allow_unix_sockets=_str_list(data.get('allowUnixSockets')),
            allow_all_unix_sockets=_opt_bool(data.get('allowAllUnixSockets')),
            allow_local_binding=_opt_bool(data.get('allowLocalBinding')),
            http_proxy_port=_opt_int(data.get('httpProxyPort')),
            socks_proxy_port=_opt_int(data.get('socksProxyPort')),
        )

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            'allowedDomains': self.allowed_domains,
            'allowManagedDomainsOnly': self.allow_managed_domains_only,
            'allowUnixSockets': self.allow_unix_sockets,
            'allowAllUnixSockets': self.allow_all_unix_sockets,
            'allowLocalBinding': self.allow_local_binding,
            'httpProxyPort': self.http_proxy_port,
            'socksProxyPort': self.socks_proxy_port,
        })


@dataclass(frozen=True)
class SandboxFilesystemConfig:
    allow_write: list[str] | None = None
    deny_write: list[str] | None = None
    deny_read: list[str] | None = None
    allow_read: list[str] | None = None
    allow_managed_read_paths_only: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SandboxFilesystemConfig':
        return cls(
            allow_write=_str_list(data.get('allowWrite')),
            deny_write=_str_list(data.get('denyWrite')),
            deny_read=_str_list(data.get('denyRead')),
            allow_read=_str_list(data.get('allowRead')),
            allow_managed_read_paths_only=_opt_bool(
                data.get('allowManagedReadPathsOnly')
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({
            'allowWrite': self.allow_write,
            'denyWrite': self.deny_write,
            'denyRead': self.deny_read,
            'allowRead': self.allow_read,
            'allowManagedReadPathsOnly': self.allow_managed_read_paths_only,
        })


@dataclass(frozen=True)
class SandboxRipgrepConfig:
    command: str
    args: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SandboxRipgrepConfig':
        command = data.get('command')
        if not isinstance(command, str) or not command:
            raise ValueError('ripgrep.command must be a non-empty string')
        return cls(command=command, args=_str_list(data.get('args')))

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({'command': self.command, 'args': self.args})


@dataclass(frozen=True)
class SandboxSettings:
    enabled: bool | None = None
    fail_if_unavailable: bool | None = None
    auto_allow_bash_if_sandboxed: bool | None = None
    allow_unsandboxed_commands: bool | None = None
    network: SandboxNetworkConfig | None = None
    filesystem: SandboxFilesystemConfig | None = None
    ignore_violations: dict[str, list[str]] | None = None
    enable_weaker_nested_sandbox: bool | None = None
    enable_weaker_network_isolation: bool | None = None
    excluded_commands: list[str] | None = None
    ripgrep: SandboxRipgrepConfig | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    _KNOWN_KEYS = frozenset({
        'enabled', 'failIfUnavailable', 'autoAllowBashIfSandboxed',
        'allowUnsandboxedCommands', 'network', 'filesystem',
        'ignoreViolations', 'enableWeakerNestedSandbox',
        'enableWeakerNetworkIsolation', 'excludedCommands', 'ripgrep',
    })

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'SandboxSettings':
        if not isinstance(data, dict):
            raise ValueError(f'expected mapping, got {type(data).__name__}')
        network_raw = data.get('network')
        filesystem_raw = data.get('filesystem')
        ripgrep_raw = data.get('ripgrep')
        ignore_raw = data.get('ignoreViolations')
        ignore: dict[str, list[str]] | None = None
        if ignore_raw is not None:
            if not isinstance(ignore_raw, dict):
                raise ValueError('ignoreViolations must be a mapping')
            ignore = {}
            for key, value in ignore_raw.items():
                items = _str_list(value)
                ignore[str(key)] = items if items is not None else []
        extra = {k: v for k, v in data.items() if k not in cls._KNOWN_KEYS}
        return cls(
            enabled=_opt_bool(data.get('enabled')),
            fail_if_unavailable=_opt_bool(data.get('failIfUnavailable')),
            auto_allow_bash_if_sandboxed=_opt_bool(
                data.get('autoAllowBashIfSandboxed')
            ),
            allow_unsandboxed_commands=_opt_bool(
                data.get('allowUnsandboxedCommands')
            ),
            network=(
                SandboxNetworkConfig.from_dict(network_raw)
                if isinstance(network_raw, dict) else None
            ),
            filesystem=(
                SandboxFilesystemConfig.from_dict(filesystem_raw)
                if isinstance(filesystem_raw, dict) else None
            ),
            ignore_violations=ignore,
            enable_weaker_nested_sandbox=_opt_bool(
                data.get('enableWeakerNestedSandbox')
            ),
            enable_weaker_network_isolation=_opt_bool(
                data.get('enableWeakerNetworkIsolation')
            ),
            excluded_commands=_str_list(data.get('excludedCommands')),
            ripgrep=(
                SandboxRipgrepConfig.from_dict(ripgrep_raw)
                if isinstance(ripgrep_raw, dict) else None
            ),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = _drop_none({
            'enabled': self.enabled,
            'failIfUnavailable': self.fail_if_unavailable,
            'autoAllowBashIfSandboxed': self.auto_allow_bash_if_sandboxed,
            'allowUnsandboxedCommands': self.allow_unsandboxed_commands,
            'enableWeakerNestedSandbox': self.enable_weaker_nested_sandbox,
            'enableWeakerNetworkIsolation': self.enable_weaker_network_isolation,
            'excludedCommands': self.excluded_commands,
        })
        if self.network is not None:
            out['network'] = self.network.to_dict()
        if self.filesystem is not None:
            out['filesystem'] = self.filesystem.to_dict()
        if self.ignore_violations is not None:
            out['ignoreViolations'] = {
                key: list(value) for key, value in self.ignore_violations.items()
            }
        if self.ripgrep is not None:
            out['ripgrep'] = self.ripgrep.to_dict()
        # passthrough — preserve unknown keys after serialization
        for key, value in self.extra.items():
            out.setdefault(key, value)
        return out


SandboxIgnoreViolations = dict[str, list[str]]


__all__ = [
    'SandboxNetworkConfig',
    'SandboxFilesystemConfig',
    'SandboxRipgrepConfig',
    'SandboxSettings',
    'SandboxIgnoreViolations',
]
