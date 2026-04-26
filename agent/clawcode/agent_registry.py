from __future__ import annotations

import ast
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .builtin_agents import AgentDefinition, describe_agent_tools, get_builtin_agents

_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?(.*)$', re.DOTALL)
_AGENTS_DIR = Path('.claude') / 'agents'
_SOURCE_ORDER = {
    'built-in': 0,
    'userSettings': 1,
    'projectSettings': 2,
}
_MUTABLE_SOURCE_ALIASES = {
    'project': 'projectSettings',
    'projectSettings': 'projectSettings',
    'user': 'userSettings',
    'userSettings': 'userSettings',
}
_UNSET = object()


@dataclass(frozen=True)
class AgentLoadError:
    path: str
    source: str
    error: str


@dataclass(frozen=True)
class AgentRegistrySnapshot:
    all_agents: tuple[AgentDefinition, ...]
    active_agents: tuple[AgentDefinition, ...]
    shadowed_agents: tuple[AgentDefinition, ...]
    failed_files: tuple[AgentLoadError, ...]


@dataclass(frozen=True)
class AgentMutationResult:
    action: str
    agent_type: str
    source: str
    file_path: str
    overwritten: bool = False


def load_agent_registry(cwd: Path) -> AgentRegistrySnapshot:
    builtin_agents = tuple(get_builtin_agents())
    loaded_agents: list[AgentDefinition] = list(builtin_agents)
    failed_files: list[AgentLoadError] = []
    for source, directory in iter_agent_directories(cwd):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob('*.md')):
            try:
                loaded_agents.append(load_agent_markdown(path, source=source))
            except (OSError, ValueError) as exc:
                failed_files.append(
                    AgentLoadError(
                        path=str(path),
                        source=source,
                        error=str(exc),
                    )
                )
    active_agents, shadowed_agents = resolve_active_agents(tuple(loaded_agents))
    return AgentRegistrySnapshot(
        all_agents=tuple(loaded_agents),
        active_agents=active_agents,
        shadowed_agents=shadowed_agents,
        failed_files=tuple(failed_files),
    )


def iter_agent_directories(cwd: Path) -> tuple[tuple[str, Path], ...]:
    return (
        ('userSettings', Path.home() / _AGENTS_DIR),
        ('projectSettings', cwd / _AGENTS_DIR),
    )


def find_agent_definition(
    cwd: Path,
    agent_type: str,
    *,
    active_only: bool = True,
) -> AgentDefinition | None:
    snapshot = load_agent_registry(cwd)
    pool = snapshot.active_agents if active_only else snapshot.all_agents
    for agent in pool:
        if agent.agent_type == agent_type:
            return agent
    return None


def resolve_active_agents(
    all_agents: tuple[AgentDefinition, ...],
) -> tuple[tuple[AgentDefinition, ...], tuple[AgentDefinition, ...]]:
    active_by_name: dict[str, AgentDefinition] = {}
    for agent in all_agents:
        current = active_by_name.get(agent.agent_type)
        if current is None or _source_rank(agent.source) >= _source_rank(current.source):
            active_by_name[agent.agent_type] = agent

    active_agents = tuple(
        sorted(
            active_by_name.values(),
            key=lambda agent: (_source_rank(agent.source), agent.agent_type.lower()),
        )
    )
    shadowed_agents = tuple(
        sorted(
            (
                agent
                for agent in all_agents
                if active_by_name.get(agent.agent_type) is not agent
            ),
            key=lambda agent: (agent.agent_type.lower(), _source_rank(agent.source)),
        )
    )
    return active_agents, shadowed_agents


def load_agent_markdown(path: Path, *, source: str) -> AgentDefinition:
    text = path.read_text(encoding='utf-8')
    metadata, body = _split_frontmatter(text)
    agent_type = str(metadata.get('name') or path.stem).strip()
    if not agent_type:
        raise ValueError(f'Agent file {path} is missing a name')
    when_to_use = str(
        metadata.get('description')
        or metadata.get('whenToUse')
        or metadata.get('when_to_use')
        or ''
    ).strip()
    if not when_to_use:
        raise ValueError(f'Agent file {path} is missing a description')
    system_prompt = body.strip()
    if not system_prompt:
        system_prompt = str(metadata.get('prompt') or '').strip()
    if not system_prompt:
        raise ValueError(f'Agent file {path} is missing a system prompt body')
    tools = _parse_tool_list(metadata.get('tools'))
    disallowed_tools = tuple(_coerce_string_list(metadata.get('disallowedTools')))
    return AgentDefinition(
        agent_type=agent_type,
        when_to_use=when_to_use,
        system_prompt=system_prompt,
        model=_coerce_optional_string(metadata.get('model')),
        tools=tools,
        disallowed_tools=disallowed_tools,
        color=_coerce_optional_string(metadata.get('color')),
        background=_coerce_bool(metadata.get('background')),
        one_shot=_coerce_bool(metadata.get('oneShot')),
        omit_claude_md=_coerce_bool(metadata.get('omitClaudeMd')),
        permission_mode=_coerce_optional_string(
            metadata.get('permissionMode') or metadata.get('permission_mode')
        ),
        max_turns=_coerce_optional_int(metadata.get('maxTurns')),
        critical_system_reminder=_coerce_optional_string(
            metadata.get('criticalSystemReminder')
            or metadata.get('criticalSystemReminder_EXPERIMENTAL')
        ),
        source=source,
        filename=path.stem,
        base_dir=str(path.parent),
        skills=tuple(_coerce_string_list(metadata.get('skills'))),
        memory=_coerce_optional_string(metadata.get('memory')),
        effort=_coerce_effort(metadata.get('effort')),
        initial_prompt=_coerce_optional_string(
            metadata.get('initialPrompt') or metadata.get('initial_prompt')
        ),
        isolation=_coerce_optional_string(metadata.get('isolation')),
        hook_names=tuple(_coerce_hook_names(metadata.get('hooks'))),
    )


def render_agents_report(
    snapshot: AgentRegistrySnapshot,
    *,
    cwd: Path,
    show_all: bool = False,
) -> str:
    lines = [
        '# Agents',
        '',
        f'- Active agent types: {len(snapshot.active_agents)}',
        f'- All discovered definitions: {len(snapshot.all_agents)}',
        f'- Shadowed definitions: {len(snapshot.shadowed_agents)}',
        f'- Failed files: {len(snapshot.failed_files)}',
        '- Source precedence: built-in < userSettings < projectSettings',
        '',
        '## Sources',
        f'- built-in: {_count_source(snapshot.all_agents, "built-in")}',
    ]
    for source, directory in iter_agent_directories(cwd):
        lines.append(
            f'- {source}: {_count_source(snapshot.all_agents, source)} ({directory})'
        )
    lines.extend(['', '## All Agents' if show_all else '## Active Agents'])
    visible_agents = snapshot.all_agents if show_all else snapshot.active_agents
    if not visible_agents:
        lines.append('No agent definitions were discovered.')
    else:
        for agent in visible_agents:
            lines.append(
                f'- {agent.agent_type} [{agent.source}]'
                f' ; tools={describe_agent_tools(agent)}'
                f' ; model={agent.model or "inherit"}'
            )
    if snapshot.shadowed_agents:
        lines.extend(['', '## Shadowed Agents'])
        for agent in snapshot.shadowed_agents:
            winner = _winner_for(snapshot, agent.agent_type)
            winner_desc = winner.source if winner is not None else 'unknown'
            lines.append(
                f'- {agent.agent_type} [{agent.source}] shadowed by {winner_desc}'
            )
    if snapshot.failed_files:
        lines.extend(['', '## Failed Files'])
        for item in snapshot.failed_files:
            lines.append(f'- {item.path}: {item.error}')
    return '\n'.join(lines)


def render_agent_detail(snapshot: AgentRegistrySnapshot, agent_type: str) -> str:
    agent = next(
        (candidate for candidate in snapshot.active_agents if candidate.agent_type == agent_type),
        None,
    )
    if agent is None:
        agent = next(
            (candidate for candidate in snapshot.all_agents if candidate.agent_type == agent_type),
            None,
        )
    if agent is None:
        return f'# Agent\n\nUnknown agent: {agent_type}'

    lines = [
        f'# Agent: {agent.agent_type}',
        '',
        f'- Source: {agent.source}',
        f'- Model: {agent.model or "inherit"}',
        f'- Tools: {describe_agent_tools(agent)}',
        f'- Permission mode: {agent.permission_mode or "(default)"}',
        f'- Max turns: {agent.max_turns if agent.max_turns is not None else "(default)"}',
        f'- Background: {agent.background}',
        f'- One-shot: {agent.one_shot}',
        f'- Omit CLAUDE.md: {agent.omit_claude_md}',
    ]
    if agent.base_dir:
        lines.append(f'- Base directory: {agent.base_dir}')
    if agent.filename:
        lines.append(f'- Definition file: {Path(agent.base_dir or ".") / (agent.filename + ".md")}')
    if agent.color:
        lines.append(f'- Color: {agent.color}')
    if agent.memory:
        lines.append(f'- Memory: {agent.memory}')
    if agent.effort is not None:
        lines.append(f'- Effort: {agent.effort}')
    if agent.isolation:
        lines.append(f'- Isolation: {agent.isolation}')
    if agent.skills:
        lines.append(f'- Skills: {", ".join(agent.skills)}')
    if agent.hook_names:
        lines.append(f'- Hooks: {", ".join(agent.hook_names)}')
    if agent.initial_prompt:
        lines.extend(['', '## Initial Prompt', agent.initial_prompt])
    lines.extend(['', '## When To Use', agent.when_to_use, '', '## System Prompt', agent.system_prompt])
    return '\n'.join(lines)


def normalize_mutable_source(source: str | None, *, allow_auto: bool = False) -> str:
    if source is None:
        return 'auto' if allow_auto else 'projectSettings'
    normalized = source.strip()
    if allow_auto and normalized in {'', 'auto'}:
        return 'auto'
    resolved = _MUTABLE_SOURCE_ALIASES.get(normalized)
    if resolved is None:
        choices = ', '.join(sorted(_MUTABLE_SOURCE_ALIASES))
        if allow_auto:
            choices = 'auto, ' + choices
        raise ValueError(f'Unsupported agent source: {source}. Expected one of: {choices}')
    return resolved


def format_agent_markdown(
    *,
    agent_type: str,
    description: str,
    system_prompt: str,
    tools: tuple[str, ...] | None = None,
    model: str | None = None,
    color: str | None = None,
    permission_mode: str | None = None,
    max_turns: int | None = None,
    initial_prompt: str | None = None,
    background: bool = False,
    one_shot: bool = False,
    omit_claude_md: bool = False,
) -> str:
    lines = [
        '---',
        f'name: {agent_type}',
        f'description: "{_escape_frontmatter_text(description)}"',
    ]
    if tools is not None:
        if tools:
            lines.append(f'tools: {", ".join(tools)}')
        else:
            lines.append('tools: []')
    if model:
        lines.append(f'model: {model}')
    if color:
        lines.append(f'color: {color}')
    if permission_mode:
        lines.append(f'permissionMode: {permission_mode}')
    if max_turns is not None:
        lines.append(f'maxTurns: {max_turns}')
    if initial_prompt:
        lines.append(f'initialPrompt: "{_escape_frontmatter_text(initial_prompt)}"')
    if background:
        lines.append('background: true')
    if one_shot:
        lines.append('oneShot: true')
    if omit_claude_md:
        lines.append('omitClaudeMd: true')
    lines.extend(['---', '', system_prompt.strip(), ''])
    return '\n'.join(lines)


def create_agent_definition(
    cwd: Path,
    *,
    agent_type: str,
    description: str,
    system_prompt: str,
    source: str = 'projectSettings',
    overwrite: bool = False,
    tools: tuple[str, ...] | None = None,
    model: str | None = None,
    color: str | None = None,
    permission_mode: str | None = None,
    max_turns: int | None = None,
    initial_prompt: str | None = None,
    background: bool = False,
    one_shot: bool = False,
    omit_claude_md: bool = False,
) -> AgentMutationResult:
    resolved_source = normalize_mutable_source(source)
    file_path = get_agent_file_path(cwd, resolved_source, agent_type)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existed_before = file_path.exists()
    if existed_before and not overwrite:
        raise ValueError(f'Agent file already exists: {file_path}')
    file_path.write_text(
        format_agent_markdown(
            agent_type=agent_type,
            description=description,
            system_prompt=system_prompt,
            tools=tools,
            model=model,
            color=color,
            permission_mode=permission_mode,
            max_turns=max_turns,
            initial_prompt=initial_prompt,
            background=background,
            one_shot=one_shot,
            omit_claude_md=omit_claude_md,
        ),
        encoding='utf-8',
    )
    return AgentMutationResult(
        action='created',
        agent_type=agent_type,
        source=resolved_source,
        file_path=str(file_path),
        overwritten=existed_before and overwrite,
    )


def update_agent_definition(
    cwd: Path,
    *,
    agent_type: str,
    source: str = 'auto',
    description: str | object = _UNSET,
    system_prompt: str | object = _UNSET,
    tools: tuple[str, ...] | None | object = _UNSET,
    model: str | None | object = _UNSET,
    color: str | None | object = _UNSET,
    permission_mode: str | None | object = _UNSET,
    max_turns: int | None | object = _UNSET,
    initial_prompt: str | None | object = _UNSET,
    background: bool | object = _UNSET,
    one_shot: bool | object = _UNSET,
    omit_claude_md: bool | object = _UNSET,
) -> AgentMutationResult:
    resolved_source = normalize_mutable_source(source, allow_auto=True)
    snapshot = load_agent_registry(cwd)
    target = find_mutable_agent(snapshot, agent_type, source=resolved_source)
    if target is None:
        raise ValueError(f'No editable agent definition found for: {agent_type}')
    file_path = get_agent_file_path(
        cwd,
        target.source,
        target.agent_type,
        filename=target.filename,
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        format_agent_markdown(
            agent_type=target.agent_type,
            description=target.when_to_use if description is _UNSET else str(description),
            system_prompt=target.system_prompt if system_prompt is _UNSET else str(system_prompt),
            tools=target.tools if tools is _UNSET else tools,
            model=target.model if model is _UNSET else model,
            color=target.color if color is _UNSET else color,
            permission_mode=(
                target.permission_mode if permission_mode is _UNSET else permission_mode
            ),
            max_turns=target.max_turns if max_turns is _UNSET else max_turns,
            initial_prompt=target.initial_prompt if initial_prompt is _UNSET else initial_prompt,
            background=target.background if background is _UNSET else bool(background),
            one_shot=target.one_shot if one_shot is _UNSET else bool(one_shot),
            omit_claude_md=(
                target.omit_claude_md if omit_claude_md is _UNSET else bool(omit_claude_md)
            ),
        ),
        encoding='utf-8',
    )
    return AgentMutationResult(
        action='updated',
        agent_type=target.agent_type,
        source=target.source,
        file_path=str(file_path),
    )


def delete_agent_definition(
    cwd: Path,
    *,
    agent_type: str,
    source: str = 'auto',
) -> AgentMutationResult:
    resolved_source = normalize_mutable_source(source, allow_auto=True)
    snapshot = load_agent_registry(cwd)
    target = find_mutable_agent(snapshot, agent_type, source=resolved_source)
    if target is None:
        raise ValueError(f'No editable agent definition found for: {agent_type}')
    file_path = get_agent_file_path(
        cwd,
        target.source,
        target.agent_type,
        filename=target.filename,
    )
    if not file_path.exists():
        raise ValueError(f'Agent file does not exist: {file_path}')
    file_path.unlink()
    return AgentMutationResult(
        action='deleted',
        agent_type=target.agent_type,
        source=target.source,
        file_path=str(file_path),
    )


def scaffold_agent_definition(
    cwd: Path,
    *,
    agent_type: str,
    source: str = 'projectSettings',
    overwrite: bool = False,
    description: str | None = None,
    system_prompt: str | None = None,
) -> AgentMutationResult:
    resolved_description = description or f'Use this agent when the task calls for {agent_type}.'
    resolved_prompt = system_prompt or (
        f'You are the {agent_type} agent.\n'
        'Read the task carefully, use the available tools deliberately, and return a concise result.'
    )
    return create_agent_definition(
        cwd,
        agent_type=agent_type,
        description=resolved_description,
        system_prompt=resolved_prompt,
        source=source,
        overwrite=overwrite,
    )


def find_mutable_agent(
    snapshot: AgentRegistrySnapshot,
    agent_type: str,
    *,
    source: str = 'auto',
) -> AgentDefinition | None:
    if source == 'auto':
        candidates = [
            agent
            for agent in snapshot.all_agents
            if agent.agent_type == agent_type and agent.source in _MUTABLE_SOURCE_ALIASES.values()
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda agent: _source_rank(agent.source))
    for agent in snapshot.all_agents:
        if agent.agent_type == agent_type and agent.source == source:
            return agent
    return None


def get_agent_file_path(
    cwd: Path,
    source: str,
    agent_type: str,
    *,
    filename: str | None = None,
) -> Path:
    resolved_source = normalize_mutable_source(source)
    directories = dict(iter_agent_directories(cwd))
    directory = directories[resolved_source]
    return directory / f'{filename or agent_type}.md'


def render_agent_mutation(result: AgentMutationResult) -> str:
    return '\n'.join(
        [
            '# Agent',
            '',
            f'action={result.action}',
            f'agent_type={result.agent_type}',
            f'source={result.source}',
            f'file_path={result.file_path}',
            f'overwritten={result.overwritten}',
        ]
    )


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace('\r\n', '\n')
    match = _FRONTMATTER_RE.match(normalized)
    if match is None:
        return {}, normalized
    return _parse_frontmatter(match.group(1)), match.group(2)


def _parse_frontmatter(block: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, raw_value = line.split(':', 1)
        metadata[key.strip()] = _parse_frontmatter_value(raw_value.strip())
    return metadata


def _parse_frontmatter_value(value: str) -> Any:
    if not value:
        return ''
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value[1:-1]
    lowered = value.lower()
    if lowered == 'true':
        return True
    if lowered == 'false':
        return False
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        reader = csv.reader([inner], skipinitialspace=True)
        return [item.strip().strip('"').strip("'") for item in next(reader)]
    return value


def _escape_frontmatter_text(value: str) -> str:
    return (
        value.replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('\n', '\\\\n')
    )


def _parse_tool_list(value: Any) -> tuple[str, ...] | None:
    if value is None or value == '':
        return None
    tools = tuple(_coerce_string_list(value))
    if not tools:
        return None
    if tools == ('*',):
        return None
    return tools


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith('[') and stripped.endswith(']'):
            parsed = _parse_frontmatter_value(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in stripped.split(',') if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _coerce_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_optional_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(value)


def _coerce_effort(value: Any) -> str | int | None:
    if value is None or value == '':
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    return text


def _coerce_hook_names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [str(item).strip() for item in value if str(item).strip()]
    return _coerce_string_list(value)


def _count_source(all_agents: tuple[AgentDefinition, ...], source: str) -> int:
    return sum(1 for agent in all_agents if agent.source == source)


def _winner_for(snapshot: AgentRegistrySnapshot, agent_type: str) -> AgentDefinition | None:
    for agent in snapshot.active_agents:
        if agent.agent_type == agent_type:
            return agent
    return None


def _source_rank(source: str) -> int:
    return _SOURCE_ORDER.get(source, -1)
