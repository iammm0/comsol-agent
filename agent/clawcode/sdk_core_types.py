"""Foundational SDK types — Python port of entrypoints/sdk/coreTypes.ts.

Mirrors the public constants and a starter set of dataclasses for the
serializable types defined in `entrypoints/sdk/coreSchemas.ts`. The full
schema set (1800+ lines of Zod) is too large to port wholesale; this file
covers the foundational pieces other modules already reference and gives
later slices a place to extend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Const arrays (HOOK_EVENTS, EXIT_REASONS) — mirror coreTypes.ts top-level
# ---------------------------------------------------------------------------

HOOK_EVENTS: tuple[str, ...] = (
    'PreToolUse',
    'PostToolUse',
    'PostToolUseFailure',
    'Notification',
    'UserPromptSubmit',
    'SessionStart',
    'SessionEnd',
    'Stop',
    'StopFailure',
    'SubagentStart',
    'SubagentStop',
    'PreCompact',
    'PostCompact',
    'PermissionRequest',
    'PermissionDenied',
    'Setup',
    'TeammateIdle',
    'TaskCreated',
    'TaskCompleted',
    'Elicitation',
    'ElicitationResult',
    'ConfigChange',
    'WorktreeCreate',
    'WorktreeRemove',
    'InstructionsLoaded',
    'CwdChanged',
    'FileChanged',
)

EXIT_REASONS: tuple[str, ...] = (
    'clear',
    'resume',
    'logout',
    'prompt_input_exit',
    'other',
    'bypass_permissions_disabled',
)

API_KEY_SOURCES: tuple[str, ...] = ('user', 'project', 'org', 'temporary', 'oauth')
CONFIG_SCOPES: tuple[str, ...] = ('local', 'user', 'project')
SDK_BETAS: tuple[str, ...] = ('context-1m-2025-08-07',)


ApiKeySource = Literal['user', 'project', 'org', 'temporary', 'oauth']
ConfigScope = Literal['local', 'user', 'project']
SdkBeta = Literal['context-1m-2025-08-07']


# ---------------------------------------------------------------------------
# Usage / model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    web_search_requests: int
    cost_usd: float
    context_window: int
    max_output_tokens: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ModelUsage':
        return cls(
            input_tokens=int(data['inputTokens']),
            output_tokens=int(data['outputTokens']),
            cache_read_input_tokens=int(data['cacheReadInputTokens']),
            cache_creation_input_tokens=int(data['cacheCreationInputTokens']),
            web_search_requests=int(data['webSearchRequests']),
            cost_usd=float(data['costUSD']),
            context_window=int(data['contextWindow']),
            max_output_tokens=int(data['maxOutputTokens']),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'inputTokens': self.input_tokens,
            'outputTokens': self.output_tokens,
            'cacheReadInputTokens': self.cache_read_input_tokens,
            'cacheCreationInputTokens': self.cache_creation_input_tokens,
            'webSearchRequests': self.web_search_requests,
            'costUSD': self.cost_usd,
            'contextWindow': self.context_window,
            'maxOutputTokens': self.max_output_tokens,
        }


# ---------------------------------------------------------------------------
# Thinking config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThinkingAdaptive:
    type: Literal['adaptive'] = 'adaptive'

    def to_dict(self) -> dict[str, Any]:
        return {'type': self.type}


@dataclass(frozen=True)
class ThinkingEnabled:
    budget_tokens: int | None = None
    type: Literal['enabled'] = 'enabled'

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {'type': self.type}
        if self.budget_tokens is not None:
            out['budgetTokens'] = self.budget_tokens
        return out


@dataclass(frozen=True)
class ThinkingDisabled:
    type: Literal['disabled'] = 'disabled'

    def to_dict(self) -> dict[str, Any]:
        return {'type': self.type}


ThinkingConfig = ThinkingAdaptive | ThinkingEnabled | ThinkingDisabled


def thinking_config_from_dict(data: dict[str, Any]) -> ThinkingConfig:
    kind = data.get('type')
    if kind == 'adaptive':
        return ThinkingAdaptive()
    if kind == 'enabled':
        budget = data.get('budgetTokens')
        return ThinkingEnabled(
            budget_tokens=int(budget) if budget is not None else None,
        )
    if kind == 'disabled':
        return ThinkingDisabled()
    raise ValueError(f'unknown thinking config type: {kind!r}')


# ---------------------------------------------------------------------------
# MCP server configs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class McpStdioServerConfig:
    command: str
    args: list[str] | None = None
    env: dict[str, str] | None = None
    type: Literal['stdio'] = 'stdio'

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {'type': self.type, 'command': self.command}
        if self.args is not None:
            out['args'] = list(self.args)
        if self.env is not None:
            out['env'] = dict(self.env)
        return out


@dataclass(frozen=True)
class McpSSEServerConfig:
    url: str
    headers: dict[str, str] | None = None
    type: Literal['sse'] = 'sse'

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {'type': self.type, 'url': self.url}
        if self.headers is not None:
            out['headers'] = dict(self.headers)
        return out


@dataclass(frozen=True)
class McpHttpServerConfig:
    url: str
    headers: dict[str, str] | None = None
    type: Literal['http'] = 'http'

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {'type': self.type, 'url': self.url}
        if self.headers is not None:
            out['headers'] = dict(self.headers)
        return out


@dataclass(frozen=True)
class McpSdkServerConfig:
    name: str
    type: Literal['sdk'] = 'sdk'

    def to_dict(self) -> dict[str, Any]:
        return {'type': self.type, 'name': self.name}


@dataclass(frozen=True)
class McpClaudeAIProxyServerConfig:
    url: str
    id: str
    type: Literal['claudeai-proxy'] = 'claudeai-proxy'

    def to_dict(self) -> dict[str, Any]:
        return {'type': self.type, 'url': self.url, 'id': self.id}


McpServerConfigForProcessTransport = (
    McpStdioServerConfig
    | McpSSEServerConfig
    | McpHttpServerConfig
    | McpSdkServerConfig
)
McpServerStatusConfig = (
    McpServerConfigForProcessTransport | McpClaudeAIProxyServerConfig
)


def mcp_server_config_from_dict(data: dict[str, Any]) -> McpServerStatusConfig:
    """Discriminate by `type` and route to the matching dataclass."""
    raw_type = data.get('type')
    if raw_type is None or raw_type == 'stdio':
        command = data.get('command')
        if not isinstance(command, str):
            raise ValueError('stdio server config requires a string command')
        return McpStdioServerConfig(
            command=command,
            args=list(data['args']) if isinstance(data.get('args'), list) else None,
            env=dict(data['env']) if isinstance(data.get('env'), dict) else None,
        )
    if raw_type == 'sse':
        return McpSSEServerConfig(
            url=str(data['url']),
            headers=dict(data['headers']) if isinstance(data.get('headers'), dict) else None,
        )
    if raw_type == 'http':
        return McpHttpServerConfig(
            url=str(data['url']),
            headers=dict(data['headers']) if isinstance(data.get('headers'), dict) else None,
        )
    if raw_type == 'sdk':
        return McpSdkServerConfig(name=str(data['name']))
    if raw_type == 'claudeai-proxy':
        return McpClaudeAIProxyServerConfig(
            url=str(data['url']),
            id=str(data['id']),
        )
    raise ValueError(f'unknown MCP server config type: {raw_type!r}')


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JsonSchemaOutputFormat:
    schema: dict[str, Any] = field(default_factory=dict)
    type: Literal['json_schema'] = 'json_schema'

    def to_dict(self) -> dict[str, Any]:
        return {'type': self.type, 'schema': dict(self.schema)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'JsonSchemaOutputFormat':
        if data.get('type') != 'json_schema':
            raise ValueError(
                f'expected output format type "json_schema", got {data.get("type")!r}'
            )
        schema = data.get('schema')
        if not isinstance(schema, dict):
            raise ValueError('json_schema output format requires a "schema" mapping')
        return cls(schema=dict(schema))


OutputFormat = JsonSchemaOutputFormat


__all__ = [
    'HOOK_EVENTS',
    'EXIT_REASONS',
    'API_KEY_SOURCES',
    'CONFIG_SCOPES',
    'SDK_BETAS',
    'ApiKeySource',
    'ConfigScope',
    'SdkBeta',
    'ModelUsage',
    'ThinkingAdaptive',
    'ThinkingEnabled',
    'ThinkingDisabled',
    'ThinkingConfig',
    'thinking_config_from_dict',
    'McpStdioServerConfig',
    'McpSSEServerConfig',
    'McpHttpServerConfig',
    'McpSdkServerConfig',
    'McpClaudeAIProxyServerConfig',
    'McpServerConfigForProcessTransport',
    'McpServerStatusConfig',
    'mcp_server_config_from_dict',
    'JsonSchemaOutputFormat',
    'OutputFormat',
]
