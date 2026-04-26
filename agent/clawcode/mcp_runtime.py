from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MCP_PROTOCOL_VERSION = '2025-11-25'


@dataclass(frozen=True)
class MCPResource:
    uri: str
    server_name: str
    source_manifest: str
    name: str | None = None
    description: str | None = None
    mime_type: str | None = None
    resolved_path: str | None = None
    inline_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPTool:
    name: str
    server_name: str
    source_manifest: str
    description: str | None = None
    input_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPServerProfile:
    name: str
    source_manifest: str
    transport: str
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPRuntime:
    resources: tuple[MCPResource, ...] = field(default_factory=tuple)
    servers: tuple[MCPServerProfile, ...] = field(default_factory=tuple)

    @classmethod
    def from_workspace(
        cls,
        cwd: Path,
        additional_working_directories: tuple[str, ...] = (),
    ) -> 'MCPRuntime':
        resources: list[MCPResource] = []
        servers: list[MCPServerProfile] = []
        for path in _discover_manifest_paths(cwd, additional_working_directories):
            manifest_resources, manifest_servers = _load_manifest(path)
            resources.extend(manifest_resources)
            servers.extend(manifest_servers)
        return cls(
            resources=tuple(resources),
            servers=tuple(_dedupe_servers(servers)),
        )

    @property
    def manifests(self) -> tuple[str, ...]:
        seen: list[str] = []
        for entry in [*self.resources, *self.servers]:
            source_manifest = entry.source_manifest
            if source_manifest not in seen:
                seen.append(source_manifest)
        return tuple(seen)

    def has_transport_servers(self) -> bool:
        return any(server.transport == 'stdio' for server in self.servers)

    def list_resources(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
    ) -> tuple[MCPResource, ...]:
        resources = list(self.resources)
        resources.extend(self._list_remote_resources())
        filtered = _filter_resources(tuple(resources), query=query)
        if limit is not None and limit >= 0:
            filtered = filtered[:limit]
        return filtered

    def get_resource(self, uri: str) -> MCPResource | None:
        for resource in self.resources:
            if resource.uri == uri:
                return resource
        for resource in self._list_remote_resources():
            if resource.uri == uri:
                return resource
        return None

    def read_resource(self, uri: str, *, max_chars: int = 12000) -> str:
        for resource in self.resources:
            if resource.uri != uri:
                continue
            if resource.inline_text is not None:
                return _truncate(resource.inline_text, max_chars)
            if resource.resolved_path is not None:
                path = Path(resource.resolved_path)
                if not path.exists() or not path.is_file():
                    raise FileNotFoundError(f'MCP resource file not found: {path}')
                text = path.read_text(encoding='utf-8', errors='replace')
                return _truncate(text, max_chars)
        last_error: Exception | None = None
        candidate_servers: list[MCPServerProfile] = []
        discovered = self.get_resource(uri)
        if discovered is not None:
            server = self.get_server(discovered.server_name)
            if server is not None:
                candidate_servers.append(server)
        for server in self.servers:
            if server.transport != 'stdio':
                continue
            if all(existing.name != server.name for existing in candidate_servers):
                candidate_servers.append(server)
        for server in candidate_servers:
            try:
                result = _request_stdio(server, 'resources/read', {'uri': uri})
            except Exception as exc:
                last_error = exc
                continue
            rendered = _render_resource_contents(result.get('contents'))
            if rendered:
                return _truncate(rendered, max_chars)
        if last_error is not None:
            raise FileNotFoundError(f'Unable to read MCP resource {uri}: {last_error}') from last_error
        raise FileNotFoundError(f'Unknown MCP resource: {uri}')

    def list_tools(
        self,
        *,
        query: str | None = None,
        server_name: str | None = None,
        limit: int | None = None,
    ) -> tuple[MCPTool, ...]:
        tools = self._list_remote_tools(server_name=server_name)
        if query:
            needle = query.lower()
            tools = tuple(
                tool
                for tool in tools
                if needle in tool.name.lower()
                or needle in (tool.description or '').lower()
                or needle in tool.server_name.lower()
            )
        if limit is not None and limit >= 0:
            tools = tools[:limit]
        return tools

    def call_tool(
        self,
        tool_name: str,
        *,
        arguments: dict[str, Any] | None = None,
        server_name: str | None = None,
        max_chars: int = 12000,
    ) -> tuple[str, dict[str, Any]]:
        tool = self._resolve_tool(tool_name, server_name=server_name)
        server = self.get_server(tool.server_name)
        if server is None:
            raise FileNotFoundError(f'Unknown MCP server: {tool.server_name}')
        payload = {
            'name': tool.name,
            'arguments': dict(arguments or {}),
        }
        result = _request_stdio(server, 'tools/call', payload)
        rendered = _truncate(_render_tool_call_result(result), max_chars)
        metadata = {
            'server_name': tool.server_name,
            'tool_name': tool.name,
            'is_error': bool(result.get('isError')),
        }
        return rendered, metadata

    def get_server(self, name: str) -> MCPServerProfile | None:
        needle = name.strip().lower()
        if not needle:
            return None
        for server in self.servers:
            if server.name.lower() == needle:
                return server
        return None

    def render_summary(self) -> str:
        if not self.resources and not self.servers:
            return 'No local MCP manifests, servers, or resources discovered.'
        lines = [
            f'Local MCP manifests: {len(self.manifests)}',
            f'Local MCP resources: {len(self.resources)}',
            f'Configured MCP servers: {len(self.servers)}',
        ]
        transport_counts: dict[str, int] = {}
        for server in self.servers:
            transport_counts[server.transport] = transport_counts.get(server.transport, 0) + 1
        for transport, count in sorted(transport_counts.items()):
            lines.append(f'- {transport}: {count} server(s)')
        by_server: dict[str, int] = {}
        for resource in self.resources:
            by_server[resource.server_name] = by_server.get(resource.server_name, 0) + 1
        for server_name, count in sorted(by_server.items()):
            lines.append(f'- local resources for {server_name}: {count}')
        for server in self.servers[:10]:
            details = [server.name, server.transport]
            if server.command:
                details.append(server.command)
            lines.append('- Server: ' + ' ; '.join(details))
        return '\n'.join(lines)

    def render_resource_index(
        self,
        *,
        query: str | None = None,
        limit: int = 20,
    ) -> str:
        resources = self.list_resources(query=query, limit=limit)
        if not resources:
            return '# MCP Resources\n\nNo matching MCP resources discovered.'
        lines = ['# MCP Resources', '']
        for resource in resources:
            details = [resource.uri]
            details.append(f'server={resource.server_name}')
            if resource.name:
                details.append(f'name={resource.name}')
            if resource.mime_type:
                details.append(f'mime={resource.mime_type}')
            if resource.resolved_path:
                details.append(f'path={resource.resolved_path}')
            elif resource.inline_text is not None:
                details.append('source=inline')
            else:
                details.append('source=transport')
            lines.append('- ' + '; '.join(details))
        return '\n'.join(lines)

    def render_resource(self, uri: str, *, max_chars: int = 12000) -> str:
        resource = self.get_resource(uri)
        if resource is None:
            return f'# MCP Resource\n\nUnknown MCP resource: {uri}'
        lines = [
            '# MCP Resource',
            '',
            f'- URI: {resource.uri}',
            f'- Server: {resource.server_name}',
        ]
        if resource.name:
            lines.append(f'- Name: {resource.name}')
        if resource.mime_type:
            lines.append(f'- MIME Type: {resource.mime_type}')
        if resource.resolved_path:
            lines.append(f'- Path: {resource.resolved_path}')
        lines.extend(['', self.read_resource(uri, max_chars=max_chars)])
        return '\n'.join(lines)

    def render_tool_index(
        self,
        *,
        query: str | None = None,
        server_name: str | None = None,
        limit: int = 50,
    ) -> str:
        tools = self.list_tools(query=query, server_name=server_name, limit=limit)
        if not tools:
            return '# MCP Tools\n\nNo matching MCP tools discovered.'
        lines = ['# MCP Tools', '']
        for tool in tools:
            details = [tool.name, f'server={tool.server_name}']
            if tool.description:
                details.append(tool.description)
            lines.append('- ' + ' ; '.join(details))
        return '\n'.join(lines)

    def render_tool_call(
        self,
        tool_name: str,
        *,
        arguments: dict[str, Any] | None = None,
        server_name: str | None = None,
        max_chars: int = 12000,
    ) -> str:
        content, metadata = self.call_tool(
            tool_name,
            arguments=arguments,
            server_name=server_name,
            max_chars=max_chars,
        )
        lines = [
            '# MCP Tool Result',
            '',
            f'- Tool: {tool_name}',
            f'- Server: {metadata["server_name"]}',
            f'- is_error: {metadata["is_error"]}',
            '',
            content,
        ]
        return '\n'.join(lines)

    def _list_remote_resources(self) -> tuple[MCPResource, ...]:
        discovered: list[MCPResource] = []
        for server in self.servers:
            if server.transport != 'stdio':
                continue
            try:
                result = _request_stdio(server, 'resources/list', {})
            except OSError:
                continue
            for item in _extract_remote_resources(server, result):
                discovered.append(item)
        return tuple(discovered)

    def _list_remote_tools(self, *, server_name: str | None = None) -> tuple[MCPTool, ...]:
        discovered: list[MCPTool] = []
        candidate_servers = (
            [self.get_server(server_name)] if server_name else list(self.servers)
        )
        for server in candidate_servers:
            if server is None or server.transport != 'stdio':
                continue
            try:
                result = _request_stdio(server, 'tools/list', {})
            except OSError:
                continue
            for item in _extract_remote_tools(server, result):
                discovered.append(item)
        return tuple(discovered)

    def _resolve_tool(self, tool_name: str, server_name: str | None = None) -> MCPTool:
        tools = self.list_tools(server_name=server_name)
        matches = [tool for tool in tools if tool.name == tool_name]
        if server_name:
            if not matches:
                raise FileNotFoundError(f'Unknown MCP tool: {tool_name} on server {server_name}')
            return matches[0]
        if not matches:
            raise FileNotFoundError(f'Unknown MCP tool: {tool_name}')
        if len(matches) > 1:
            raise FileNotFoundError(
                f'MCP tool {tool_name} exists on multiple servers. Pass server_name to disambiguate.'
            )
        return matches[0]


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
        remember(root / '.claw-mcp.json')
        remember(root / '.mcp.json')
        remember(root / '.codex-mcp.json')
        remember(root / 'mcp.json')
    return tuple(candidates)


def _load_manifest(path: Path) -> tuple[list[MCPResource], list[MCPServerProfile]]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return [], []
    if not isinstance(payload, dict):
        return [], []

    resources: list[MCPResource] = []
    servers: list[MCPServerProfile] = []

    if isinstance(payload.get('resources'), list):
        resources.extend(
            _extract_resources(
                payload.get('name') if isinstance(payload.get('name'), str) else 'local',
                payload['resources'],
                manifest_path=path,
            )
        )

    raw_servers = payload.get('servers')
    if isinstance(raw_servers, list):
        for item in raw_servers:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            if not isinstance(name, str) or not name.strip():
                continue
            server_name = name.strip()
            raw_resources = item.get('resources')
            if isinstance(raw_resources, list):
                resources.extend(
                    _extract_resources(server_name, raw_resources, manifest_path=path)
                )
            server = _extract_server_profile(server_name, item, manifest_path=path)
            if server is not None:
                servers.append(server)

    raw_mcp_servers = payload.get('mcpServers')
    if isinstance(raw_mcp_servers, dict):
        for server_name, item in raw_mcp_servers.items():
            if not isinstance(server_name, str) or not server_name.strip():
                continue
            if not isinstance(item, dict):
                continue
            server = _extract_server_profile(server_name.strip(), item, manifest_path=path)
            if server is not None:
                servers.append(server)

    return resources, servers


def _extract_server_profile(
    server_name: str,
    payload: dict[str, Any],
    *,
    manifest_path: Path,
) -> MCPServerProfile | None:
    command = payload.get('command')
    if not isinstance(command, str) or not command.strip():
        return None
    args = payload.get('args', ())
    if not isinstance(args, list):
        args = ()
    normalized_args = tuple(
        item for item in args if isinstance(item, str)
    )
    env = payload.get('env')
    normalized_env = {
        key: value
        for key, value in (env.items() if isinstance(env, dict) else [])
        if isinstance(key, str) and isinstance(value, str)
    }
    cwd = payload.get('cwd')
    resolved_cwd: str | None = None
    if isinstance(cwd, str) and cwd.strip():
        candidate = Path(cwd).expanduser()
        if not candidate.is_absolute():
            candidate = manifest_path.parent / candidate
        resolved_cwd = str(candidate.resolve())
    description = payload.get('description') if isinstance(payload.get('description'), str) else None
    transport = payload.get('transport')
    if not isinstance(transport, str) or not transport.strip():
        transport = 'stdio'
    transport = transport.strip().lower()
    if transport != 'stdio':
        return None
    metadata = payload.get('metadata')
    return MCPServerProfile(
        name=server_name,
        source_manifest=str(manifest_path),
        transport=transport,
        command=command.strip(),
        args=normalized_args,
        env=normalized_env,
        cwd=resolved_cwd,
        description=description,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _extract_resources(
    server_name: str,
    raw_resources: list[Any],
    *,
    manifest_path: Path,
) -> list[MCPResource]:
    resources: list[MCPResource] = []
    seen_uris: set[str] = set()
    for item in raw_resources:
        if not isinstance(item, dict):
            continue
        uri = item.get('uri')
        if not isinstance(uri, str) or not uri.strip():
            continue
        uri = uri.strip()
        if uri in seen_uris:
            continue
        seen_uris.add(uri)
        raw_path = item.get('path')
        if raw_path is None:
            raw_path = item.get('file')
        resolved_path: str | None = None
        if isinstance(raw_path, str) and raw_path.strip():
            candidate = Path(raw_path).expanduser()
            if not candidate.is_absolute():
                candidate = manifest_path.parent / candidate
            resolved_path = str(candidate.resolve())
        inline_text = item.get('text')
        if not isinstance(inline_text, str):
            inline_text = None
        metadata = item.get('metadata')
        resources.append(
            MCPResource(
                uri=uri,
                server_name=server_name,
                source_manifest=str(manifest_path),
                name=item.get('name') if isinstance(item.get('name'), str) else None,
                description=(
                    item.get('description')
                    if isinstance(item.get('description'), str)
                    else None
                ),
                mime_type=(
                    item.get('mimeType')
                    if isinstance(item.get('mimeType'), str)
                    else item.get('mime_type')
                    if isinstance(item.get('mime_type'), str)
                    else None
                ),
                resolved_path=resolved_path,
                inline_text=inline_text,
                metadata=dict(metadata) if isinstance(metadata, dict) else {},
            )
        )
    return resources


def _extract_remote_resources(
    server: MCPServerProfile,
    payload: dict[str, Any],
) -> tuple[MCPResource, ...]:
    raw_resources = payload.get('resources')
    if not isinstance(raw_resources, list):
        return ()
    resources: list[MCPResource] = []
    for item in raw_resources:
        if not isinstance(item, dict):
            continue
        uri = item.get('uri')
        if not isinstance(uri, str) or not uri.strip():
            continue
        resources.append(
            MCPResource(
                uri=uri.strip(),
                server_name=server.name,
                source_manifest=server.source_manifest,
                name=item.get('name') if isinstance(item.get('name'), str) else None,
                description=(
                    item.get('description')
                    if isinstance(item.get('description'), str)
                    else None
                ),
                mime_type=(
                    item.get('mimeType')
                    if isinstance(item.get('mimeType'), str)
                    else item.get('mime_type')
                    if isinstance(item.get('mime_type'), str)
                    else None
                ),
                metadata={
                    'transport': server.transport,
                    'server_command': server.command,
                },
            )
        )
    return tuple(resources)


def _extract_remote_tools(
    server: MCPServerProfile,
    payload: dict[str, Any],
) -> tuple[MCPTool, ...]:
    raw_tools = payload.get('tools')
    if not isinstance(raw_tools, list):
        return ()
    tools: list[MCPTool] = []
    for item in raw_tools:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        if not isinstance(name, str) or not name.strip():
            continue
        input_schema = item.get('inputSchema')
        if not isinstance(input_schema, dict):
            input_schema = item.get('input_schema')
        tools.append(
            MCPTool(
                name=name.strip(),
                server_name=server.name,
                source_manifest=server.source_manifest,
                description=(
                    item.get('description')
                    if isinstance(item.get('description'), str)
                    else None
                ),
                input_schema=dict(input_schema) if isinstance(input_schema, dict) else {},
                metadata={
                    'transport': server.transport,
                    'server_command': server.command,
                },
            )
        )
    return tuple(tools)


def _filter_resources(
    resources: tuple[MCPResource, ...],
    *,
    query: str | None = None,
) -> tuple[MCPResource, ...]:
    if not query:
        return resources
    needle = query.lower()
    return tuple(
        resource
        for resource in resources
        if needle in resource.uri.lower()
        or needle in resource.server_name.lower()
        or needle in (resource.name or '').lower()
        or needle in (resource.description or '').lower()
    )


def _dedupe_servers(servers: list[MCPServerProfile]) -> list[MCPServerProfile]:
    seen: set[tuple[str, str, str | None, tuple[str, ...]]] = set()
    deduped: list[MCPServerProfile] = []
    for server in servers:
        key = (server.name.lower(), server.transport, server.command, server.args)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(server)
    return deduped


def _request_stdio(
    server: MCPServerProfile,
    method: str,
    params: dict[str, Any],
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    with _StdioMCPConnection(server, timeout_seconds=timeout_seconds) as connection:
        return connection.request(method, params)


class _StdioMCPConnection:
    def __init__(self, server: MCPServerProfile, *, timeout_seconds: float = 10.0) -> None:
        self.server = server
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self.selector: selectors.BaseSelector | None = None
        self.stderr_lines: list[str] = []
        self._request_id = 0

    def __enter__(self) -> '_StdioMCPConnection':
        try:
            command = [self.server.command or '', *self.server.args]
            if not command[0]:
                raise OSError(f'MCP server {self.server.name} has no executable command')
            env = os.environ.copy()
            env.update(self.server.env)
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self.server.cwd or None,
                env=env,
            )
            self.selector = selectors.DefaultSelector()
            assert self.process.stdout is not None
            assert self.process.stderr is not None
            self.selector.register(self.process.stdout, selectors.EVENT_READ, data='stdout')
            self.selector.register(self.process.stderr, selectors.EVENT_READ, data='stderr')
            self._initialize()
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        process = self.process
        if self.selector is not None:
            try:
                self.selector.close()
            except Exception:
                pass
            self.selector = None
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
        except Exception:
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
        for stream_name in ('stdout', 'stderr'):
            stream = getattr(process, stream_name, None)
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
        self.process = None

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._send(
            {
                'jsonrpc': '2.0',
                'id': request_id,
                'method': method,
                'params': params,
            }
        )
        response = self._await_response(request_id)
        error = response.get('error')
        if isinstance(error, dict):
            message = error.get('message')
            raise OSError(
                f'MCP {method} failed for server {self.server.name}: {message or error}'
            )
        result = response.get('result')
        if not isinstance(result, dict):
            return {}
        return result

    def _initialize(self) -> None:
        self._request_id += 1
        request_id = self._request_id
        self._send(
            {
                'jsonrpc': '2.0',
                'id': request_id,
                'method': 'initialize',
                'params': {
                    'protocolVersion': MCP_PROTOCOL_VERSION,
                    'capabilities': {},
                    'clientInfo': {
                        'name': 'claw-code-agent',
                        'version': '0.1.0',
                    },
                },
            }
        )
        response = self._await_response(request_id)
        error = response.get('error')
        if isinstance(error, dict):
            raise OSError(
                f'MCP initialize failed for server {self.server.name}: {error.get("message") or error}'
            )
        self._send(
            {
                'jsonrpc': '2.0',
                'method': 'notifications/initialized',
                'params': {},
            }
        )

    def _send(self, payload: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise OSError(f'MCP server {self.server.name} is not running')
        self.process.stdin.write(json.dumps(payload, ensure_ascii=True) + '\n')
        self.process.stdin.flush()

    def _await_response(self, request_id: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stderr = '\n'.join(self.stderr_lines[-5:])
                raise TimeoutError(
                    f'Timed out waiting for MCP response from {self.server.name}'
                    + (f' stderr={stderr}' if stderr else '')
                )
            if self.selector is None:
                raise OSError(f'MCP selector is not available for {self.server.name}')
            events = self.selector.select(timeout=remaining)
            if not events:
                continue
            for key, _mask in events:
                stream_name = key.data
                line = key.fileobj.readline()
                if not line:
                    continue
                if stream_name == 'stderr':
                    self.stderr_lines.append(line.rstrip())
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get('id') == request_id:
                    return payload


def _render_resource_contents(contents: Any) -> str:
    if not isinstance(contents, list):
        return ''
    parts: list[str] = []
    for item in contents:
        if not isinstance(item, dict):
            continue
        text = item.get('text')
        if isinstance(text, str):
            parts.append(text)
            continue
        blob = item.get('blob')
        if isinstance(blob, str):
            mime_type = item.get('mimeType') if isinstance(item.get('mimeType'), str) else 'application/octet-stream'
            parts.append(f'[blob:{mime_type}] {blob}')
            continue
        parts.append(json.dumps(item, ensure_ascii=True, indent=2))
    return '\n\n'.join(parts).strip()


def _render_tool_call_result(result: dict[str, Any]) -> str:
    parts: list[str] = []
    content = result.get('content')
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get('text')
            if isinstance(text, str):
                parts.append(text)
                continue
            structured = item.get('structuredContent')
            if structured is not None:
                parts.append(json.dumps(structured, ensure_ascii=True, indent=2))
                continue
            parts.append(json.dumps(item, ensure_ascii=True, indent=2))
    structured_content = result.get('structuredContent')
    if structured_content is not None:
        parts.append(json.dumps(structured_content, ensure_ascii=True, indent=2))
    if not parts:
        parts.append(json.dumps(result, ensure_ascii=True, indent=2))
    return '\n\n'.join(part for part in parts if part).strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    return f'{head}\n...[truncated]...\n{tail}'
