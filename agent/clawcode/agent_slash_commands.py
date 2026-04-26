from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .agent_runtime import LocalCodingAgent


@dataclass(frozen=True)
class ParsedSlashCommand:
    command_name: str
    args: str
    is_mcp: bool


@dataclass(frozen=True)
class SlashCommandResult:
    handled: bool
    should_query: bool
    prompt: str | None = None
    output: str = ''
    transcript: tuple[dict[str, Any], ...] = ()


SlashCommandHandler = Callable[['LocalCodingAgent', str, str], SlashCommandResult]


@dataclass(frozen=True)
class SlashCommandSpec:
    names: tuple[str, ...]
    description: str
    handler: SlashCommandHandler


def parse_slash_command(input_text: str) -> ParsedSlashCommand | None:
    trimmed = input_text.strip()
    if not trimmed.startswith('/'):
        return None

    without_slash = trimmed[1:]
    words = without_slash.split(' ')
    if not words or not words[0]:
        return None

    command_name = words[0]
    is_mcp = False
    args_start_index = 1
    if len(words) > 1 and words[1] == '(MCP)':
        command_name = f'{command_name} (MCP)'
        is_mcp = True
        args_start_index = 2

    return ParsedSlashCommand(
        command_name=command_name,
        args=' '.join(words[args_start_index:]),
        is_mcp=is_mcp,
    )


def looks_like_command(command_name: str) -> bool:
    return re.search(r'[^a-zA-Z0-9:\-_]', command_name) is None


def preprocess_slash_command(
    agent: 'LocalCodingAgent',
    input_text: str,
) -> SlashCommandResult:
    if not input_text.strip().startswith('/'):
        return SlashCommandResult(handled=False, should_query=True, prompt=input_text)

    parsed = parse_slash_command(input_text)
    if parsed is None:
        return _local_result(
            input_text,
            'Commands are in the form `/command [args]`.',
        )

    normalized_name = (
        parsed.command_name[:-6]
        if parsed.is_mcp and parsed.command_name.endswith(' (MCP)')
        else parsed.command_name
    )
    spec = find_slash_command(normalized_name)
    if spec is None:
        if looks_like_command(parsed.command_name):
            label = normalized_name if parsed.is_mcp else parsed.command_name
            return _local_result(input_text, f'Unknown skill: {label}')
        return SlashCommandResult(handled=False, should_query=True, prompt=input_text)

    return spec.handler(agent, parsed.args.strip(), input_text)


def get_slash_command_specs() -> tuple[SlashCommandSpec, ...]:
    return (
        SlashCommandSpec(
            names=('help', 'commands'),
            description='Show the built-in Python slash commands.',
            handler=_handle_help,
        ),
        SlashCommandSpec(
            names=('context', 'usage'),
            description='Show estimated session context usage similar to the npm /context command.',
            handler=_handle_context,
        ),
        SlashCommandSpec(
            names=('context-raw', 'env'),
            description='Show the raw environment, user context, and system context snapshot.',
            handler=_handle_context_raw,
        ),
        SlashCommandSpec(
            names=('token-budget', 'budget'),
            description='Show the current token-budget window, reserves, and prompt-length limits.',
            handler=_handle_token_budget,
        ),
        SlashCommandSpec(
            names=('mcp',),
            description='Show discovered local MCP manifests and resource counts.',
            handler=_handle_mcp,
        ),
        SlashCommandSpec(
            names=('search',),
            description='Show search runtime status, list or activate providers, or run a real web search query.',
            handler=_handle_search,
        ),
        SlashCommandSpec(
            names=('remote',),
            description='Show local remote runtime status or activate a remote target/profile.',
            handler=_handle_remote,
        ),
        SlashCommandSpec(
            names=('worktree',),
            description='Show managed git worktree status or enter/exit the current managed worktree session.',
            handler=_handle_worktree,
        ),
        SlashCommandSpec(
            names=('account',),
            description='Show local account runtime status or configured account profiles.',
            handler=_handle_account,
        ),
        SlashCommandSpec(
            names=('ask',),
            description='Show local ask-user runtime status or ask-user history.',
            handler=_handle_ask,
        ),
        SlashCommandSpec(
            names=('login',),
            description='Activate a local account profile or ephemeral identity.',
            handler=_handle_login,
        ),
        SlashCommandSpec(
            names=('logout',),
            description='Clear the active local account session.',
            handler=_handle_logout,
        ),
        SlashCommandSpec(
            names=('config', 'settings'),
            description='Show local config runtime state, effective config, config sources, or a config value.',
            handler=_handle_config,
        ),
        SlashCommandSpec(
            names=('lsp',),
            description='Show local LSP runtime status or run document symbols, definition, references, hover, call hierarchy, and diagnostics queries.',
            handler=_handle_lsp,
        ),
        SlashCommandSpec(
            names=('remotes',),
            description='List configured local remote profiles.',
            handler=_handle_remotes,
        ),
        SlashCommandSpec(
            names=('ssh',),
            description='Activate a local SSH remote target/profile.',
            handler=_handle_ssh,
        ),
        SlashCommandSpec(
            names=('teleport',),
            description='Activate a local teleport remote target/profile.',
            handler=_handle_teleport,
        ),
        SlashCommandSpec(
            names=('direct-connect',),
            description='Activate a local direct-connect remote target/profile.',
            handler=_handle_direct_connect,
        ),
        SlashCommandSpec(
            names=('deep-link',),
            description='Activate a local deep-link remote target/profile.',
            handler=_handle_deep_link,
        ),
        SlashCommandSpec(
            names=('disconnect', 'remote-disconnect'),
            description='Disconnect the active local remote runtime target.',
            handler=_handle_remote_disconnect,
        ),
        SlashCommandSpec(
            names=('resources',),
            description='List local MCP resources, optionally filtered by a query string.',
            handler=_handle_resources,
        ),
        SlashCommandSpec(
            names=('resource',),
            description='Render a local MCP resource by URI.',
            handler=_handle_resource,
        ),
        SlashCommandSpec(
            names=('tasks', 'todo'),
            description='Show the local runtime task list, optionally filtered by status.',
            handler=_handle_tasks,
        ),
        SlashCommandSpec(
            names=('workflows',),
            description='List local workflows discovered from workflow manifests.',
            handler=_handle_workflows,
        ),
        SlashCommandSpec(
            names=('workflow',),
            description='Show or run one local workflow by name.',
            handler=_handle_workflow,
        ),
        SlashCommandSpec(
            names=('triggers',),
            description='List local remote triggers discovered from remote trigger manifests.',
            handler=_handle_triggers,
        ),
        SlashCommandSpec(
            names=('trigger',),
            description='Show or run one local remote trigger by id.',
            handler=_handle_trigger,
        ),
        SlashCommandSpec(
            names=('teams',),
            description='List the locally configured collaboration teams.',
            handler=_handle_teams,
        ),
        SlashCommandSpec(
            names=('team',),
            description='Show one local collaboration team by name.',
            handler=_handle_team,
        ),
        SlashCommandSpec(
            names=('messages',),
            description='Show recorded collaboration messages for all teams or one team.',
            handler=_handle_messages,
        ),
        SlashCommandSpec(
            names=('task-next', 'next-task'),
            description='Show the next actionable tasks from the local runtime task list.',
            handler=_handle_task_next,
        ),
        SlashCommandSpec(
            names=('plan', 'planner'),
            description='Show the current local runtime plan.',
            handler=_handle_plan,
        ),
        SlashCommandSpec(
            names=('task',),
            description='Show a local runtime task by id.',
            handler=_handle_task,
        ),
        SlashCommandSpec(
            names=('prompt', 'system-prompt'),
            description='Render the effective Python system prompt.',
            handler=_handle_prompt,
        ),
        SlashCommandSpec(
            names=('permissions',),
            description='Show the active tool permission mode.',
            handler=_handle_permissions,
        ),
        SlashCommandSpec(
            names=('hooks', 'policy'),
            description='Show discovered local hook and policy manifests.',
            handler=_handle_hooks,
        ),
        SlashCommandSpec(
            names=('trust',),
            description='Show workspace trust mode, managed settings, and safe environment values.',
            handler=_handle_trust,
        ),
        SlashCommandSpec(
            names=('model',),
            description='Show or update the active model for the current agent instance.',
            handler=_handle_model,
        ),
        SlashCommandSpec(
            names=('tools',),
            description='List the registered tools and whether the current permissions allow them.',
            handler=_handle_tools,
        ),
        SlashCommandSpec(
            names=('agents',),
            description='List active local agent configurations or show one agent definition by name.',
            handler=_handle_agents,
        ),
        SlashCommandSpec(
            names=('memory',),
            description='Show the currently loaded CLAUDE.md memory bundle and discovered files.',
            handler=_handle_memory,
        ),
        SlashCommandSpec(
            names=('status', 'session'),
            description='Show a short runtime/session status summary.',
            handler=_handle_status,
        ),
        SlashCommandSpec(
            names=('clear',),
            description='Clear ephemeral Python runtime state for this process.',
            handler=_handle_clear,
        ),
        SlashCommandSpec(
            names=('compact',),
            description='Summarise and compact the conversation to free context space.',
            handler=_handle_compact,
        ),
        SlashCommandSpec(
            names=('cost',),
            description='Show the total cost and duration of the current session.',
            handler=_handle_cost,
        ),
        SlashCommandSpec(
            names=('exit', 'quit'),
            description='Exit the REPL.',
            handler=_handle_exit,
        ),
        SlashCommandSpec(
            names=('diff',),
            description='View uncommitted changes (git diff) in the working directory.',
            handler=_handle_diff,
        ),
        SlashCommandSpec(
            names=('files',),
            description='List files currently loaded in the session context.',
            handler=_handle_files,
        ),
        SlashCommandSpec(
            names=('copy',),
            description='Copy the last assistant response to a temp file.',
            handler=_handle_copy,
        ),
        SlashCommandSpec(
            names=('export',),
            description='Export the conversation to a text file.',
            handler=_handle_export,
        ),
        SlashCommandSpec(
            names=('stats',),
            description='Show session usage statistics.',
            handler=_handle_stats,
        ),
        SlashCommandSpec(
            names=('tag',),
            description='Add or remove a searchable tag on the current session.',
            handler=_handle_tag,
        ),
        SlashCommandSpec(
            names=('rename',),
            description='Rename the current conversation.',
            handler=_handle_rename,
        ),
        SlashCommandSpec(
            names=('branch',),
            description='Create a fork/branch of the current conversation.',
            handler=_handle_branch,
        ),
        SlashCommandSpec(
            names=('effort',),
            description='Show or set the model effort level (low, medium, high, max, auto).',
            handler=_handle_effort,
        ),
        SlashCommandSpec(
            names=('doctor',),
            description='Diagnose and verify the claw-code installation and settings.',
            handler=_handle_doctor,
        ),
        SlashCommandSpec(
            names=('commit',),
            description='Create a git commit.',
            handler=_handle_commit,
        ),
        SlashCommandSpec(
            names=('pr-comments', 'pr_comments'),
            description='Get comments from a GitHub pull request.',
            handler=_handle_pr_comments,
        ),
        SlashCommandSpec(
            names=('resume', 'continue'),
            description='Resume a previous conversation.',
            handler=_handle_resume,
        ),
        SlashCommandSpec(
            names=('add-dir',),
            description='Add a new working directory.',
            handler=_handle_add_dir,
        ),
        SlashCommandSpec(
            names=('skills',),
            description='List available skills.',
            handler=_handle_skills,
        ),
        SlashCommandSpec(
            names=('fast',),
            description='Toggle fast mode.',
            handler=_handle_fast,
        ),
        SlashCommandSpec(
            names=('vim',),
            description='Toggle between Vim and Normal editing modes.',
            handler=_handle_vim,
        ),
        SlashCommandSpec(
            names=('rewind', 'checkpoint'),
            description='Restore the conversation to a previous point.',
            handler=_handle_rewind,
        ),
        SlashCommandSpec(
            names=('output-style',),
            description='Deprecated: use /config to change your output style.',
            handler=_handle_output_style,
        ),
        SlashCommandSpec(
            names=('release-notes',),
            description='Show local release notes or a link to the changelog.',
            handler=_handle_release_notes,
        ),
        SlashCommandSpec(
            names=('feedback', 'bug'),
            description='Open the Claude Code feedback page in a browser.',
            handler=_handle_feedback,
        ),
        SlashCommandSpec(
            names=('upgrade',),
            description='Open the Claude.ai upgrade page in a browser.',
            handler=_handle_upgrade,
        ),
        SlashCommandSpec(
            names=('stickers',),
            description='Open the Claude Code sticker order page in a browser.',
            handler=_handle_stickers,
        ),
        SlashCommandSpec(
            names=('mobile', 'ios', 'android'),
            description='Show download links for the Claude mobile apps.',
            handler=_handle_mobile,
        ),
        SlashCommandSpec(
            names=('desktop', 'app'),
            description='Show the Claude Desktop handoff page link.',
            handler=_handle_desktop,
        ),
        SlashCommandSpec(
            names=('install-github-app',),
            description='Open the Claude GitHub Actions setup page.',
            handler=_handle_install_github_app,
        ),
        SlashCommandSpec(
            names=('install-slack-app',),
            description='Open the Claude Slack app installation page.',
            handler=_handle_install_slack_app,
        ),
        SlashCommandSpec(
            names=('privacy-settings',),
            description='Open the Claude.ai privacy controls page.',
            handler=_handle_privacy_settings,
        ),
        SlashCommandSpec(
            names=('extra-usage',),
            description='Show extra-usage configuration link.',
            handler=_handle_extra_usage,
        ),
        SlashCommandSpec(
            names=('passes',),
            description='Show Claude Code guest passes information.',
            handler=_handle_passes,
        ),
        SlashCommandSpec(
            names=('rate-limit-options',),
            description='Show options when the active account hits a rate limit.',
            handler=_handle_rate_limit_options,
        ),
        SlashCommandSpec(
            names=('chrome',),
            description='Open the Claude Chrome extension page.',
            handler=_handle_chrome,
        ),
        SlashCommandSpec(
            names=('reload-plugins',),
            description='Reload local plugin manifests and report counts.',
            handler=_handle_reload_plugins,
        ),
        SlashCommandSpec(
            names=('theme',),
            description='List available themes or set the current theme.',
            handler=_handle_theme,
        ),
        SlashCommandSpec(
            names=('voice',),
            description='Toggle voice-mode setting for this workspace.',
            handler=_handle_voice,
        ),
        SlashCommandSpec(
            names=('sandbox-toggle', 'sandbox'),
            description='Show sandbox status or exclude a command pattern.',
            handler=_handle_sandbox_toggle,
        ),
        SlashCommandSpec(
            names=('keybindings',),
            description='Print or create the local keybindings file.',
            handler=_handle_keybindings,
        ),
        SlashCommandSpec(
            names=('btw',),
            description='Ask Claude a quick side question without altering state.',
            handler=_handle_btw,
        ),
        SlashCommandSpec(
            names=('version',),
            description='Print the running version of the agent.',
            handler=_handle_version,
        ),
        SlashCommandSpec(
            names=('init',),
            description='Initialize a CLAUDE.md file with codebase documentation.',
            handler=_handle_init,
        ),
        SlashCommandSpec(
            names=('ide',),
            description='Show detected IDE/terminal integration status.',
            handler=_handle_ide,
        ),
        SlashCommandSpec(
            names=('plugin',),
            description='List installed plugins or show plugin subcommand usage.',
            handler=_handle_plugin,
        ),
        SlashCommandSpec(
            names=('remote-env',),
            description='List remote environments or set the default profile.',
            handler=_handle_remote_env,
        ),
        SlashCommandSpec(
            names=('bridge', 'remote-control', 'rc'),
            description='Report remote-control bridge status (read-only in this runtime).',
            handler=_handle_bridge,
        ),
        SlashCommandSpec(
            names=('remote-setup', 'web-setup'),
            description='Report Claude Code on the web setup readiness (gh + sign-in checks).',
            handler=_handle_remote_setup,
        ),
    )


def find_slash_command(command_name: str) -> SlashCommandSpec | None:
    lowered = command_name.lower()
    for spec in get_slash_command_specs():
        if lowered in spec.names:
            return spec
    return None


def _handle_help(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    lines = ['# Slash Commands', '']
    for spec in get_slash_command_specs():
        primary = f'/{spec.names[0]}'
        aliases = ', '.join(f'/{name}' for name in spec.names[1:])
        label = f'{primary} ({aliases})' if aliases else primary
        lines.append(f'- `{label}`: {spec.description}')
    lines.extend(
        [
            '',
            'These commands are handled locally before the model loop, similar to the npm runtime.',
        ]
    )
    return _local_result(input_text, '\n'.join(lines))


def _handle_context(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    prompt = args or None
    return _local_result(input_text, agent.render_context_report(prompt))


def _handle_context_raw(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_context_snapshot_report())


def _handle_token_budget(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_token_budget_report())


def _handle_mcp(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_mcp_report())
    if command == 'tools':
        return _local_result(input_text, agent.render_mcp_tools_report())
    if command.startswith('tools '):
        query = command.split(' ', 1)[1].strip()
        return _local_result(input_text, agent.render_mcp_tools_report(query or None))
    if command.startswith('tool '):
        tool_name = command.split(' ', 1)[1].strip()
        if not tool_name:
            return _local_result(input_text, 'Usage: /mcp tool <tool-name>')
        return _local_result(input_text, agent.render_mcp_call_tool_report(tool_name))
    return _local_result(input_text, agent.render_mcp_report(command))


def _handle_search(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_search_report())
    if command == 'providers':
        return _local_result(input_text, agent.render_search_providers_report())
    if command.startswith('providers '):
        query = command.split(' ', 1)[1].strip()
        return _local_result(input_text, agent.render_search_providers_report(query or None))
    if command.startswith('provider '):
        provider = command.split(' ', 1)[1].strip()
        if not provider:
            return _local_result(input_text, 'Usage: /search provider <name>')
        return _local_result(input_text, agent.render_search_report(provider=provider))
    if command.startswith('use '):
        provider = command.split(' ', 1)[1].strip()
        if not provider:
            return _local_result(input_text, 'Usage: /search use <name>')
        return _local_result(input_text, agent.render_search_activate_report(provider))
    return _local_result(input_text, agent.render_search_report(command))


def _handle_remote(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    target = args or None
    return _local_result(input_text, agent.render_remote_report(target))


def _handle_worktree(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_worktree_report())
    if command == 'history':
        return _local_result(input_text, agent.render_worktree_history_report())
    if command.startswith('enter'):
        name = command.split(' ', 1)[1].strip() if ' ' in command else None
        return _local_result(input_text, agent.render_worktree_enter_report(name or None))
    if command.startswith('exit'):
        parts = command.split()
        action = parts[1] if len(parts) > 1 else 'keep'
        discard_changes = any(part in {'discard', 'discard_changes=true'} for part in parts[2:])
        return _local_result(
            input_text,
            agent.render_worktree_exit_report(
                action=action,
                discard_changes=discard_changes,
            ),
        )
    return _local_result(
        input_text,
        'Usage: /worktree [history|enter <name>|exit <keep|remove> [discard]]',
    )


def _handle_account(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_account_report())
    if command == 'profiles':
        return _local_result(input_text, agent.render_account_profiles_report())
    if command.startswith('profile '):
        profile = command.split(' ', 1)[1].strip()
        if not profile:
            return _local_result(input_text, 'Usage: /account profile <name>')
        return _local_result(input_text, agent.render_account_report(profile))
    return _local_result(input_text, 'Usage: /account [profiles|profile <name>]')


def _handle_ask(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_ask_user_report())
    if command == 'history':
        return _local_result(input_text, agent.render_ask_user_history_report())
    return _local_result(input_text, 'Usage: /ask [history]')


def _handle_login(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    target = args.strip()
    if not target:
        return _local_result(input_text, 'Usage: /login <profile-or-identity>')
    return _local_result(input_text, agent.render_account_login_report(target))


def _handle_logout(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_account_logout_report())


def _handle_config(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_config_report())
    if command == 'effective':
        return _local_result(input_text, agent.render_config_effective_report())
    if command.startswith('source '):
        source = command.split(' ', 1)[1].strip()
        if not source:
            return _local_result(input_text, 'Usage: /config source <source-name>')
        return _local_result(input_text, agent.render_config_source_report(source))
    if command.startswith('get '):
        key_path = command.split(' ', 1)[1].strip()
        if not key_path:
            return _local_result(input_text, 'Usage: /config get <key-path>')
        return _local_result(input_text, agent.render_config_value_report(key_path))
    return _local_result(
        input_text,
        'Usage: /config [effective|source <name>|get <key-path>]',
    )


def _handle_lsp(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, agent.render_lsp_report())
    if command == 'diagnostics':
        return _local_result(input_text, agent.render_lsp_diagnostics_report())
    if command.startswith('diagnostics '):
        file_path = command.split(' ', 1)[1].strip()
        if not file_path:
            return _local_result(input_text, 'Usage: /lsp diagnostics [file-path]')
        return _local_result(input_text, agent.render_lsp_diagnostics_report(file_path))
    if command.startswith('symbols '):
        file_path = command.split(' ', 1)[1].strip()
        if not file_path:
            return _local_result(input_text, 'Usage: /lsp symbols <file-path>')
        return _local_result(input_text, agent.render_lsp_document_symbols_report(file_path))
    if command.startswith('workspace '):
        query = command.split(' ', 1)[1].strip()
        if not query:
            return _local_result(input_text, 'Usage: /lsp workspace <query>')
        return _local_result(input_text, agent.render_lsp_workspace_symbols_report(query))
    parts = command.split()
    if len(parts) == 4 and parts[0] in {
        'definition',
        'references',
        'hover',
        'hierarchy',
        'incoming',
        'outgoing',
    }:
        subcommand, file_path, line_text, character_text = parts
        try:
            line = int(line_text)
            character = int(character_text)
        except ValueError:
            return _local_result(
                input_text,
                f'Usage: /lsp {subcommand} <file-path> <line> <character>',
            )
        if subcommand == 'definition':
            return _local_result(
                input_text,
                agent.render_lsp_definition_report(file_path, line, character),
            )
        if subcommand == 'references':
            return _local_result(
                input_text,
                agent.render_lsp_references_report(file_path, line, character),
            )
        if subcommand == 'hover':
            return _local_result(
                input_text,
                agent.render_lsp_hover_report(file_path, line, character),
            )
        if subcommand == 'hierarchy':
            return _local_result(
                input_text,
                agent.render_lsp_prepare_call_hierarchy_report(file_path, line, character),
            )
        if subcommand == 'incoming':
            return _local_result(
                input_text,
                agent.render_lsp_incoming_calls_report(file_path, line, character),
            )
        if subcommand == 'outgoing':
            return _local_result(
                input_text,
                agent.render_lsp_outgoing_calls_report(file_path, line, character),
            )
    return _local_result(
        input_text,
        'Usage: /lsp [symbols <file>|workspace <query>|definition <file> <line> <character>|references <file> <line> <character>|hover <file> <line> <character>|hierarchy <file> <line> <character>|incoming <file> <line> <character>|outgoing <file> <line> <character>|diagnostics [file]]',
    )


def _handle_remotes(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    query = args or None
    return _local_result(input_text, agent.render_remote_profiles_report(query))


def _handle_ssh(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, 'Usage: /ssh <target-or-profile>')
    return _local_result(input_text, agent.render_remote_mode_report(args, mode='ssh'))


def _handle_teleport(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, 'Usage: /teleport <target-or-profile>')
    return _local_result(input_text, agent.render_remote_mode_report(args, mode='teleport'))


def _handle_direct_connect(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, 'Usage: /direct-connect <target-or-profile>')
    return _local_result(input_text, agent.render_remote_mode_report(args, mode='direct-connect'))


def _handle_deep_link(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, 'Usage: /deep-link <target-or-profile>')
    return _local_result(input_text, agent.render_remote_mode_report(args, mode='deep-link'))


def _handle_remote_disconnect(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(input_text, agent.render_remote_disconnect_report())


def _handle_resources(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    query = args or None
    return _local_result(input_text, agent.render_mcp_resources_report(query))


def _handle_resource(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, 'Usage: /resource <mcp-resource-uri>')
    return _local_result(input_text, agent.render_mcp_resource_report(args))


def _handle_tasks(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    status = args or None
    return _local_result(input_text, agent.render_tasks_report(status))


def _handle_workflows(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    query = args or None
    return _local_result(input_text, agent.render_workflows_report(query))


def _handle_workflow(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, 'Usage: /workflow <name> | /workflow run <name>')
    if command.startswith('run '):
        workflow_name = command.split(' ', 1)[1].strip()
        if not workflow_name:
            return _local_result(input_text, 'Usage: /workflow run <name>')
        return _local_result(input_text, agent.render_workflow_run_report(workflow_name))
    return _local_result(input_text, agent.render_workflow_report(command))


def _handle_triggers(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    query = args or None
    return _local_result(input_text, agent.render_remote_triggers_report(query))


def _handle_trigger(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    command = args.strip()
    if not command:
        return _local_result(input_text, 'Usage: /trigger <id> | /trigger run <id>')
    if command.startswith('run '):
        trigger_id = command.split(' ', 1)[1].strip()
        if not trigger_id:
            return _local_result(input_text, 'Usage: /trigger run <id>')
        return _local_result(
            input_text,
            agent.render_remote_trigger_action_report('run', trigger_id=trigger_id),
        )
    return _local_result(input_text, agent.render_remote_trigger_report(command))


def _handle_teams(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    query = args or None
    return _local_result(input_text, agent.render_teams_report(query))


def _handle_team(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    team_name = args.strip()
    if not team_name:
        return _local_result(input_text, 'Usage: /team <team-name>')
    return _local_result(input_text, agent.render_team_report(team_name))


def _handle_messages(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    team_name = args.strip() or None
    return _local_result(input_text, agent.render_team_messages_report(team_name))


def _handle_task_next(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_next_tasks_report())


def _handle_plan(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_plan_report())


def _handle_task(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, 'Usage: /task <task-id>')
    return _local_result(input_text, agent.render_task_report(args))


def _handle_prompt(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_system_prompt())


def _handle_permissions(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_permissions_report())


def _handle_hooks(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_hook_policy_report())


def _handle_trust(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_trust_report())


def _handle_model(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    if not args:
        return _local_result(input_text, f'Current model: {agent.model_config.model}')
    agent.set_model(args)
    return _local_result(input_text, f'Set model to {agent.model_config.model}')


def _handle_tools(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_tools_report())


def _handle_agents(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    trimmed = args.strip()
    if not trimmed or trimmed in {'active', 'list'}:
        return _local_result(input_text, agent.render_agents_report())
    if trimmed == 'all':
        return _local_result(input_text, agent.render_agents_report(show_all=True))
    if trimmed.startswith('create '):
        try:
            source, agent_type, description, system_prompt = _parse_agent_mutation_payload(
                trimmed[7:].strip(),
                default_source='projectSettings',
                mode='create',
            )
        except ValueError as exc:
            return _local_result(input_text, str(exc))
        return _local_result(
            input_text,
            agent.render_agent_create_report(
                agent_type,
                source=source,
                description=description,
                system_prompt=system_prompt,
            ),
        )
    if trimmed.startswith('update '):
        try:
            source, agent_type, description, system_prompt = _parse_agent_mutation_payload(
                trimmed[7:].strip(),
                default_source='auto',
                mode='update',
            )
        except ValueError as exc:
            return _local_result(input_text, str(exc))
        if description is None and system_prompt is None:
            return _local_result(
                input_text,
                'Usage: /agents update [user|project] <agent-type> [description] [:: system prompt]',
            )
        return _local_result(
            input_text,
            agent.render_agent_update_report(
                agent_type,
                source=source,
                description=description,
                system_prompt=system_prompt,
            ),
        )
    if trimmed.startswith('delete '):
        try:
            source, agent_type = _parse_agent_target(trimmed[7:].strip(), default_source='auto')
        except ValueError as exc:
            return _local_result(input_text, str(exc))
        return _local_result(
            input_text,
            agent.render_agent_delete_report(agent_type, source=source),
        )
    if trimmed.startswith('show '):
        agent_type = trimmed[5:].strip()
        if not agent_type:
            return _local_result(input_text, _agents_usage())
        return _local_result(input_text, agent.render_agent_detail_report(agent_type))
    return _local_result(input_text, agent.render_agent_detail_report(trimmed))


def _agents_usage() -> str:
    return (
        'Usage: /agents [all|active|show <agent-type>|'
        'create [user|project] <agent-type> [description] [:: system prompt]|'
        'update [user|project] <agent-type> [description] [:: system prompt]|'
        'delete [user|project] <agent-type>]'
    )


def _parse_agent_target(payload: str, *, default_source: str) -> tuple[str, str]:
    tokens = payload.split()
    if not tokens:
        raise ValueError(_agents_usage())
    source = default_source
    if tokens[0] in {'user', 'project', 'userSettings', 'projectSettings', 'auto'}:
        source = tokens.pop(0)
    if not tokens:
        raise ValueError(_agents_usage())
    return source, tokens[0]


def _parse_agent_mutation_payload(
    payload: str,
    *,
    default_source: str,
    mode: str,
) -> tuple[str, str, str | None, str | None]:
    parts = [part.strip() for part in payload.split('::')]
    source, agent_type = _parse_agent_target(parts[0], default_source=default_source)
    head_tokens = parts[0].split()
    if head_tokens and head_tokens[0] in {'user', 'project', 'userSettings', 'projectSettings', 'auto'}:
        head_tokens = head_tokens[1:]
    trailing_description = ' '.join(head_tokens[1:]).strip() if len(head_tokens) > 1 else ''
    description = trailing_description or None
    system_prompt = None
    if mode == 'create':
        if len(parts) >= 2 and parts[1]:
            description = parts[1]
        if len(parts) >= 3 and parts[2]:
            system_prompt = parts[2]
    else:
        if len(parts) >= 2 and parts[1]:
            if trailing_description:
                system_prompt = parts[1]
            else:
                system_prompt = parts[1]
        if len(parts) >= 3:
            description = parts[1] or description
            system_prompt = parts[2] or system_prompt
    return source, agent_type, description, system_prompt


def _handle_memory(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_memory_report())


def _handle_status(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    return _local_result(input_text, agent.render_status_report())


def _handle_clear(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    agent.clear_runtime_state()
    return _local_result(
        input_text,
        'Cleared ephemeral Python agent state for this process.',
    )


def _handle_compact(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    from .compact import compact_conversation

    custom_instructions = args.strip() if args.strip() else None
    result = compact_conversation(agent, custom_instructions)

    if result.error:
        return _local_result(input_text, f'Compact failed: {result.error}')

    lines = ['Conversation compacted.']
    if result.pre_compact_token_count:
        lines.append(
            f'  Tokens before: ~{result.pre_compact_token_count:,}  '
            f'→  after: ~{result.post_compact_token_count:,}'
        )
    return _local_result(input_text, '\n'.join(lines))


def _handle_cost(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    usage = agent.cumulative_usage
    cost = agent.cumulative_cost_usd

    def _fmt_cost(usd: float) -> str:
        if usd < 0.01:
            return f'${usd:.4f}'
        return f'${usd:.2f}'

    lines = [
        f'Total cost:            {_fmt_cost(cost)}',
        f'Total input tokens:    {usage.input_tokens:,}',
        f'Total output tokens:   {usage.output_tokens:,}',
    ]
    if usage.cache_read_input_tokens:
        lines.append(f'Cache read tokens:     {usage.cache_read_input_tokens:,}')
    if usage.cache_creation_input_tokens:
        lines.append(f'Cache creation tokens:  {usage.cache_creation_input_tokens:,}')
    if usage.reasoning_tokens:
        lines.append(f'Reasoning tokens:      {usage.reasoning_tokens:,}')
    lines.append(f'Total tokens:          {usage.total_tokens:,}')
    return _local_result(input_text, '\n'.join(lines))


def _handle_exit(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    import random
    import sys

    messages = ['Goodbye!', 'See ya!', 'Bye!', 'Catch you later!']
    output = random.choice(messages)
    # Build the result first so the transcript is recorded, then exit.
    result = _local_result(input_text, output)
    print(output)
    sys.exit(0)
    return result  # unreachable, but satisfies the type checker


def _handle_diff(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    import subprocess

    cwd = str(agent.runtime_config.cwd)
    try:
        proc = subprocess.run(
            ['git', 'diff'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        diff_output = proc.stdout.strip()
        if not diff_output:
            # Also check staged changes
            proc_staged = subprocess.run(
                ['git', 'diff', '--staged'],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            diff_output = proc_staged.stdout.strip()
            if not diff_output:
                return _local_result(input_text, 'No uncommitted changes.')
            return _local_result(input_text, f'Staged changes:\n{diff_output}')
        return _local_result(input_text, diff_output)
    except FileNotFoundError:
        return _local_result(input_text, 'git is not available.')
    except subprocess.TimeoutExpired:
        return _local_result(input_text, 'git diff timed out.')
    except Exception as exc:
        return _local_result(input_text, f'Error running git diff: {exc}')


def _handle_files(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    """List files loaded in the session context (from readFileState)."""
    session = agent.last_session
    if session is None:
        return _local_result(input_text, 'No active session.')

    # Collect file paths mentioned in tool results
    file_paths: list[str] = []
    for msg in session.messages:
        if msg.role == 'tool' and msg.name in ('Read', 'read_file', 'ReadFile'):
            # Extract path from content or metadata
            path = msg.metadata.get('path')
            if isinstance(path, str):
                file_paths.append(path)
            elif msg.content and msg.content.startswith('/'):
                # First line might be the path
                first_line = msg.content.split('\n', 1)[0].strip()
                if '/' in first_line and len(first_line) < 256:
                    file_paths.append(first_line)

    # Also look at tool_calls in assistant messages
    for msg in session.messages:
        if msg.role == 'assistant' and msg.tool_calls:
            for tc in msg.tool_calls:
                func = tc.get('function', {}) if isinstance(tc, dict) else {}
                if func.get('name') in ('Read', 'read_file', 'ReadFile', 'View'):
                    import json as _json
                    try:
                        args = _json.loads(func.get('arguments', '{}'))
                        path = args.get('file_path') or args.get('path')
                        if isinstance(path, str):
                            file_paths.append(path)
                    except (ValueError, TypeError):
                        pass

    # Deduplicate preserving order
    seen: set[str] = set()
    unique_paths: list[str] = []
    for p in file_paths:
        if p not in seen:
            seen.add(p)
            unique_paths.append(p)

    if not unique_paths:
        return _local_result(input_text, 'No files loaded in context.')

    cwd = str(agent.runtime_config.cwd)
    relative_paths = []
    for p in unique_paths:
        if p.startswith(cwd):
            relative_paths.append(p[len(cwd):].lstrip('/'))
        else:
            relative_paths.append(p)

    lines = [f'Files in context ({len(relative_paths)}):']
    for p in relative_paths:
        lines.append(f'  {p}')
    return _local_result(input_text, '\n'.join(lines))


def _handle_copy(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Copy the last assistant response to a temp file."""
    import tempfile as _tempfile

    session = agent.last_session
    if session is None:
        return _local_result(input_text, 'No active session.')

    # Find the Nth most recent assistant message (default N=0 = latest)
    n = 0
    if args.strip().isdigit():
        n = min(int(args.strip()), 20)

    assistant_messages = [
        msg for msg in session.messages
        if msg.role == 'assistant' and msg.content.strip()
    ]
    if not assistant_messages:
        return _local_result(input_text, 'No assistant responses to copy.')

    index = len(assistant_messages) - 1 - n
    if index < 0:
        return _local_result(
            input_text,
            f'Only {len(assistant_messages)} assistant responses available.',
        )

    content = assistant_messages[index].content

    # Write to temp file
    from pathlib import Path as _Path
    tmp_dir = _Path(_tempfile.gettempdir()) / 'claw-code'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    out_path = tmp_dir / 'response.md'
    out_path.write_text(content, encoding='utf-8')

    char_count = len(content)
    line_count = content.count('\n') + 1
    return _local_result(
        input_text,
        f'Copied {char_count:,} chars ({line_count} lines) to {out_path}',
    )


def _handle_export(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Export the conversation transcript to a text file."""
    from pathlib import Path as _Path
    import time as _time

    session = agent.last_session
    if session is None:
        return _local_result(input_text, 'No active session to export.')

    # Build plain-text transcript
    lines: list[str] = []
    for msg in session.messages:
        label = msg.role.upper()
        if msg.role == 'tool' and msg.name:
            label = f'TOOL:{msg.name}'
        lines.append(f'--- {label} ---')
        lines.append(msg.content)
        lines.append('')
    text = '\n'.join(lines)

    # Determine output path
    filename = args.strip()
    if not filename:
        timestamp = _time.strftime('%Y%m%d_%H%M%S')
        filename = f'conversation_{timestamp}.txt'
    if not filename.endswith('.txt'):
        filename += '.txt'

    out_path = _Path(str(agent.runtime_config.cwd)) / filename
    out_path.write_text(text, encoding='utf-8')
    return _local_result(
        input_text,
        f'Exported {len(session.messages)} messages to {out_path}',
    )


def _handle_stats(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    """Show session usage statistics."""
    usage = agent.cumulative_usage
    cost = agent.cumulative_cost_usd

    session = agent.last_session
    msg_count = len(session.messages) if session else 0
    user_msgs = sum(1 for m in (session.messages if session else []) if m.role == 'user')
    assistant_msgs = sum(1 for m in (session.messages if session else []) if m.role == 'assistant')
    tool_msgs = sum(1 for m in (session.messages if session else []) if m.role == 'tool')

    lines = [
        '## Session Statistics',
        '',
        f'Messages:     {msg_count} total ({user_msgs} user, {assistant_msgs} assistant, {tool_msgs} tool)',
        f'Input tokens:  {usage.input_tokens:,}',
        f'Output tokens: {usage.output_tokens:,}',
        f'Total tokens:  {usage.total_tokens:,}',
        f'Cost:          ${cost:.4f}',
        f'Model:         {agent.model_config.model}',
    ]
    if agent.active_session_id:
        lines.append(f'Session ID:    {agent.active_session_id}')
    return _local_result(input_text, '\n'.join(lines))


def _handle_tag(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Add or remove a tag on the current session."""
    tag = args.strip()
    if not tag:
        # Show current tags
        tags = getattr(agent, '_session_tags', set())
        if tags:
            return _local_result(input_text, f'Session tags: {", ".join(sorted(tags))}')
        return _local_result(input_text, 'No tags set. Usage: /tag <tag-name>')

    # Toggle tag
    if not hasattr(agent, '_session_tags'):
        agent._session_tags = set()

    if tag in agent._session_tags:
        agent._session_tags.discard(tag)
        return _local_result(input_text, f'Removed tag: {tag}')
    agent._session_tags.add(tag)
    return _local_result(input_text, f'Added tag: {tag}')


def _handle_rename(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Rename the current conversation."""
    name = args.strip()
    if not name:
        return _local_result(input_text, 'Usage: /rename <name>')

    if not hasattr(agent, '_session_name'):
        agent._session_name = None
    agent._session_name = name
    return _local_result(input_text, f'Session renamed to: {name}')


def _handle_branch(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Create a fork/branch of the current conversation."""
    import json as _json
    from uuid import uuid4

    session = agent.last_session
    if session is None:
        return _local_result(input_text, 'No active session to branch.')

    branch_name = args.strip() or f'branch-{uuid4().hex[:8]}'
    new_session_id = uuid4().hex

    # Save a copy of the current transcript as a new session file
    session_dir = agent.runtime_config.session_directory
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / f'{new_session_id}.json'

    transcript = [msg.to_transcript_entry() for msg in session.messages]
    branch_data = {
        'session_id': new_session_id,
        'branch_name': branch_name,
        'branched_from': agent.active_session_id,
        'messages': transcript,
        'model': agent.model_config.model,
    }

    try:
        session_path.write_text(_json.dumps(branch_data, indent=2), encoding='utf-8')
        return _local_result(
            input_text,
            f'Created branch "{branch_name}" (session: {new_session_id})\n'
            f'Saved to: {session_path}',
        )
    except Exception as exc:
        return _local_result(input_text, f'Error creating branch: {exc}')


def _handle_effort(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Show or set the model effort level."""
    import os

    valid_levels = ('low', 'medium', 'high', 'max', 'auto')
    current = getattr(agent.runtime_config, 'effort_level', None)
    env_override = os.environ.get('CLAUDE_CODE_EFFORT_LEVEL')

    if not args.strip():
        level = current or env_override or 'auto'
        msg = f'Current effort level: {level}'
        if env_override:
            msg += f' (from CLAUDE_CODE_EFFORT_LEVEL env var)'
        return _local_result(input_text, msg)

    level = args.strip().lower()
    if level not in valid_levels:
        return _local_result(
            input_text,
            f'Invalid effort level: {level}\nValid levels: {", ".join(valid_levels)}',
        )

    if env_override:
        return _local_result(
            input_text,
            f'Cannot change effort level — overridden by '
            f'CLAUDE_CODE_EFFORT_LEVEL={env_override}',
        )

    # Store effort level on the runtime config
    object.__setattr__(agent.runtime_config, 'effort_level', level)
    return _local_result(input_text, f'Set effort level to: {level}')


def _handle_doctor(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    """Diagnose and verify the claw-code installation."""
    import os
    import shutil
    import sys
    from pathlib import Path as _Path

    checks: list[str] = []

    # Python version
    py_ver = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    ok = sys.version_info >= (3, 10)
    checks.append(f'{"✓" if ok else "✗"} Python version: {py_ver} (need ≥3.10)')

    # Git available
    git_ok = shutil.which('git') is not None
    checks.append(f'{"✓" if git_ok else "✗"} git: {"found" if git_ok else "NOT FOUND"}')

    # Model config
    checks.append(f'✓ Model: {agent.model_config.model}')
    checks.append(f'✓ Base URL: {agent.model_config.base_url}')

    # Working directory
    cwd = agent.runtime_config.cwd
    checks.append(f'✓ Working directory: {cwd}')
    checks.append(f'{"✓" if cwd.exists() else "✗"} Working directory exists: {cwd.exists()}')

    # Session directory
    sess_dir = agent.runtime_config.session_directory
    checks.append(f'✓ Session directory: {sess_dir}')
    checks.append(f'{"✓" if sess_dir.exists() else "○"} Session directory exists: {sess_dir.exists()}')

    # API key
    has_key = bool(agent.model_config.api_key)
    checks.append(f'{"✓" if has_key else "✗"} API key: {"set" if has_key else "NOT SET"}')

    # Tools
    tool_count = len(agent.tool_registry) if agent.tool_registry else 0
    checks.append(f'✓ Registered tools: {tool_count}')

    # Memory files (CLAUDE.md)
    claude_md = cwd / 'CLAUDE.md'
    checks.append(
        f'{"✓" if claude_md.exists() else "○"} CLAUDE.md: '
        f'{"found" if claude_md.exists() else "not found (optional)"}'
    )

    output = '## Doctor Report\n\n' + '\n'.join(checks)
    return _local_result(input_text, output)


def _handle_commit(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Create a git commit — prompt-type command injecting git context."""
    import subprocess

    cwd = str(agent.runtime_config.cwd)

    def _git(cmd_args: list[str]) -> str:
        try:
            proc = subprocess.run(
                ['git'] + cmd_args,
                cwd=cwd, capture_output=True, text=True, timeout=15,
            )
            return proc.stdout.strip()
        except Exception:
            return ''

    status = _git(['status', '--short'])
    staged = _git(['diff', '--staged'])
    unstaged = _git(['diff'])
    branch = _git(['branch', '--show-current'])
    recent = _git(['log', '--oneline', '-10'])

    sections: list[str] = []
    if branch:
        sections.append(f'Current branch: {branch}')
    if status:
        sections.append(f'### Status\n```\n{status}\n```')
    if staged:
        sections.append(f'### Staged diff\n```\n{staged}\n```')
    if unstaged:
        sections.append(f'### Unstaged diff\n```\n{unstaged}\n```')
    if recent:
        sections.append(f'### Recent commits\n```\n{recent}\n```')

    git_context = '\n\n'.join(sections) if sections else 'No git changes detected.'

    prompt = f"""Create a git commit for the current changes.

{git_context}

Instructions:
1. Review the changes above
2. Stage appropriate files with `git add <file>` (prefer specific files over `git add -A`)
3. Draft a concise commit message following the repo's conventions
4. Use a HEREDOC for multi-line messages:
   git commit -m "$(cat <<'EOF'
   message here
   EOF
   )"

Safety:
- Always create NEW commits (never --amend)
- Never skip hooks (--no-verify)
- Never commit secrets (.env, credentials, etc.)
- No interactive flags (-i)"""

    if args.strip():
        prompt += f'\n\nAdditional instructions: {args.strip()}'

    return _prompt_result(input_text, prompt)


def _handle_pr_comments(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Fetch PR comments — prompt-type command using gh CLI."""
    pr_ref = args.strip()

    prompt = f"""Fetch and summarize comments from a GitHub pull request.

{f'PR reference: {pr_ref}' if pr_ref else 'Find the current PR for this branch.'}

Steps:
1. Get PR info: `gh pr view {pr_ref or ''} --json number,headRefName,headRepository`
2. Fetch PR-level comments: `gh api /repos/{{owner}}/{{repo}}/issues/{{number}}/comments --jq '.[] | {{body, user: .user.login, created_at}}'`
3. Fetch review comments: `gh api /repos/{{owner}}/{{repo}}/pulls/{{number}}/comments --jq '.[] | {{body, path, line, diff_hunk, user: .user.login}}'`
4. Present all comments with file/line context
5. Do not add explanatory text — just show the comments"""

    return _prompt_result(input_text, prompt)


def _handle_resume(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Resume a previous conversation."""
    import json as _json

    session_dir = agent.runtime_config.session_directory
    if not session_dir.exists():
        return _local_result(input_text, 'No session directory found.')

    search_term = args.strip()

    # If a session ID is provided, show its info
    if search_term:
        session_path = session_dir / f'{search_term}.json'
        if session_path.exists():
            try:
                data = _json.loads(session_path.read_text(encoding='utf-8'))
                msg_count = len(data.get('messages', []))
                return _local_result(
                    input_text,
                    f'Found session `{search_term}` with {msg_count} messages.\n'
                    f'To resume, restart with: `--resume {search_term}`',
                )
            except Exception as exc:
                return _local_result(input_text, f'Error reading session: {exc}')

    # List recent sessions
    session_files = sorted(
        session_dir.glob('*.json'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:20]

    if not session_files:
        return _local_result(input_text, 'No previous sessions found.')

    lines = ['## Recent Sessions', '']
    for sf in session_files:
        try:
            data = _json.loads(sf.read_text(encoding='utf-8'))
            sid = sf.stem
            msg_count = len(data.get('messages', []))
            model = data.get('model', 'unknown')
            first_user = ''
            for msg in data.get('messages', []):
                if msg.get('role') == 'user' and msg.get('content', '').strip():
                    first_user = msg['content'].strip()[:80]
                    if len(msg['content'].strip()) > 80:
                        first_user += '...'
                    break
            line = f'- `{sid}` ({msg_count} msgs, {model})'
            if first_user:
                line += f': {first_user}'
            lines.append(line)
        except Exception:
            lines.append(f'- `{sf.stem}` (error reading)')

    if search_term:
        # Filter by search term
        filtered = [
            l for l in lines
            if search_term.lower() in l.lower() or l.startswith('#')
        ]
        if len(filtered) <= 2:
            filtered.append(f'\nNo sessions matching "{search_term}".')
        lines = filtered

    lines.append('\nTo resume: restart with `--resume <session-id>`')
    return _local_result(input_text, '\n'.join(lines))


def _handle_add_dir(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Add a new working directory."""
    from pathlib import Path as _Path

    path_str = args.strip()
    if not path_str:
        return _local_result(input_text, 'Usage: /add-dir <path>')

    path = _Path(path_str).resolve()

    if not path.exists():
        return _local_result(input_text, f'Path not found: {path}')
    if not path.is_dir():
        return _local_result(input_text, f'Not a directory: {path}')

    cwd = agent.runtime_config.cwd
    if path == cwd or str(path).startswith(str(cwd) + '/'):
        return _local_result(
            input_text,
            f'Path is already within the working directory: {cwd}',
        )

    if not hasattr(agent, '_additional_directories'):
        agent._additional_directories = []
    if path in agent._additional_directories:
        return _local_result(input_text, f'Directory already added: {path}')

    agent._additional_directories.append(path)
    return _local_result(
        input_text,
        f'Added working directory: {path}\n'
        f'Tools can now access files in this directory.',
    )


def _handle_skills(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    """List bundled skills (mirrors npm `/skills` SkillsMenu listing)."""
    from .bundled_skills import get_bundled_skills

    lines = ['## Available Skills', '']
    for skill in get_bundled_skills():
        if not skill.user_invocable:
            continue
        header = f'- `{skill.name}`'
        if skill.aliases:
            header += f' (aliases: {", ".join(skill.aliases)})'
        lines.append(f'{header}: {skill.description}')
        if skill.when_to_use:
            lines.append(f'  - When to use: {skill.when_to_use}')
    lines.extend(['', 'Use the Skill tool to invoke skills programmatically.'])
    return _local_result(input_text, '\n'.join(lines))


def _handle_fast(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Toggle fast mode."""
    arg = args.strip().lower()
    current = getattr(agent, '_fast_mode', False)

    if arg == 'on':
        agent._fast_mode = True
        return _local_result(input_text, 'Fast mode enabled.')
    if arg == 'off':
        agent._fast_mode = False
        return _local_result(input_text, 'Fast mode disabled.')
    if not arg:
        agent._fast_mode = not current
        state = 'enabled' if agent._fast_mode else 'disabled'
        return _local_result(input_text, f'Fast mode {state}.')
    return _local_result(input_text, 'Usage: /fast [on|off]')


def _handle_vim(agent: 'LocalCodingAgent', _args: str, input_text: str) -> SlashCommandResult:
    """Toggle between Vim and Normal editing modes."""
    current = getattr(agent, '_editor_mode', 'normal')
    if current == 'emacs':
        current = 'normal'

    new_mode = 'vim' if current == 'normal' else 'normal'
    agent._editor_mode = new_mode

    if new_mode == 'vim':
        hint = 'Use Escape key to toggle between INSERT and NORMAL modes.'
    else:
        hint = 'Using standard (readline) keyboard bindings.'

    return _local_result(input_text, f'Switched to {new_mode} mode. {hint}')


def _handle_rewind(agent: 'LocalCodingAgent', args: str, input_text: str) -> SlashCommandResult:
    """Rewind conversation to a previous message."""
    session = agent.last_session
    if session is None:
        return _local_result(input_text, 'No active session.')

    n_str = args.strip()

    if not n_str:
        msgs = session.messages
        lines = ['## Conversation History', '']
        for i, msg in enumerate(msgs):
            role = msg.role.upper()
            preview = msg.content[:60].replace('\n', ' ')
            if len(msg.content) > 60:
                preview += '...'
            lines.append(f'  {i}: [{role}] {preview}')
        lines.append('')
        lines.append('Usage: /rewind <message-number> to truncate to that point.')
        return _local_result(input_text, '\n'.join(lines))

    try:
        target = int(n_str)
    except ValueError:
        return _local_result(input_text, 'Usage: /rewind <message-number>')

    if target < 0 or target >= len(session.messages):
        return _local_result(
            input_text,
            f'Invalid message number. Valid range: 0-{len(session.messages) - 1}',
        )

    removed_count = len(session.messages) - target - 1
    session.messages[:] = session.messages[:target + 1]
    return _local_result(
        input_text,
        f'Rewound conversation to message {target}. Removed {removed_count} messages.',
    )


_FEEDBACK_URL = 'https://github.com/anthropics/claude-code/issues'
_UPGRADE_URL = 'https://claude.ai/upgrade/max'
_STICKERS_URL = 'https://www.stickermule.com/claudecode'
_MOBILE_IOS_URL = 'https://apps.apple.com/app/claude-by-anthropic/id6473753684'
_MOBILE_ANDROID_URL = 'https://play.google.com/store/apps/details?id=com.anthropic.claude'
_DESKTOP_URL = 'https://claude.ai/download'
_GITHUB_APP_URL = 'https://github.com/apps/claude'
_SLACK_APP_URL = 'https://slack.com/marketplace/A08SF47R6P4-claude'
_PRIVACY_URL = 'https://claude.ai/settings/data-privacy-controls'
_CHROME_EXTENSION_URL = 'https://claude.ai/chrome'
_CHANGELOG_URL = 'https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md'


def _try_open_browser(url: str) -> bool:
    import os
    import webbrowser

    # Avoid spawning a browser in CI / non-interactive environments.
    if os.environ.get('CLAUDE_CODE_NO_BROWSER') or os.environ.get('CI'):
        return False
    try:
        return webbrowser.open(url, new=2)
    except Exception:
        return False


def _open_or_link(url: str, *, opening_message: str, fallback_message: str) -> str:
    if _try_open_browser(url):
        return f'{opening_message}\n  {url}'
    return f'{fallback_message}\n  {url}'


def _changelog_path(agent: 'LocalCodingAgent') -> 'Path':
    from pathlib import Path

    cwd = Path(agent.runtime_config.cwd)
    for candidate in (cwd / 'CHANGELOG.md', cwd / 'docs' / 'CHANGELOG.md'):
        if candidate.exists():
            return candidate
    return cwd / 'CHANGELOG.md'


def _handle_output_style(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        '/output-style has been deprecated. Use /config to change your output style, '
        'or set it in your settings file. Changes take effect on the next session.',
    )


def _handle_release_notes(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    path = _changelog_path(agent)
    if path.exists():
        try:
            content = path.read_text(encoding='utf-8').strip()
        except OSError as exc:
            return _local_result(input_text, f'Could not read {path}: {exc}')
        # Show only the most recent release block (everything up to the second
        # second-level heading, mirroring how the npm command surfaces a single
        # version chunk by default).
        lines = content.splitlines()
        chunk: list[str] = []
        seen_heading = False
        for line in lines:
            if line.startswith('## '):
                if seen_heading:
                    break
                seen_heading = True
            chunk.append(line)
        return _local_result(input_text, '\n'.join(chunk).strip() or content)
    return _local_result(
        input_text,
        f'No local CHANGELOG.md found. See the full changelog at:\n  {_CHANGELOG_URL}',
    )


def _handle_feedback(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    note = args.strip()
    body = _open_or_link(
        _FEEDBACK_URL,
        opening_message='Opening the Claude Code feedback tracker in your browser…',
        fallback_message='Submit feedback at:',
    )
    if note:
        body += f'\n\nDraft note (copy into the report form):\n{note}'
    return _local_result(input_text, body)


def _handle_upgrade(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        _open_or_link(
            _UPGRADE_URL,
            opening_message='Opening the Claude.ai upgrade page in your browser…',
            fallback_message='Upgrade your account at:',
        ),
    )


def _handle_stickers(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        _open_or_link(
            _STICKERS_URL,
            opening_message='Opening the Claude Code sticker page in your browser…',
            fallback_message='Order Claude Code stickers at:',
        ),
    )


def _handle_mobile(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    lines = [
        'Download the Claude mobile app:',
        f'  iOS:     {_MOBILE_IOS_URL}',
        f'  Android: {_MOBILE_ANDROID_URL}',
    ]
    return _local_result(input_text, '\n'.join(lines))


def _handle_desktop(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    import platform

    system = platform.system()
    if system not in {'Darwin', 'Windows'}:
        return _local_result(
            input_text,
            f'Claude Desktop is currently available on macOS and Windows only '
            f'(detected: {system}). Download:\n  {_DESKTOP_URL}',
        )
    return _local_result(
        input_text,
        _open_or_link(
            _DESKTOP_URL,
            opening_message='Opening the Claude Desktop download page in your browser…',
            fallback_message='Download Claude Desktop at:',
        ),
    )


def _handle_install_github_app(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        _open_or_link(
            _GITHUB_APP_URL,
            opening_message='Opening the Claude GitHub App installation page in your browser…',
            fallback_message='Set up Claude GitHub Actions at:',
        ),
    )


def _handle_install_slack_app(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        _open_or_link(
            _SLACK_APP_URL,
            opening_message='Opening the Claude Slack app marketplace page in your browser…',
            fallback_message="Couldn't open browser. Visit:",
        ),
    )


def _handle_privacy_settings(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        f'Review and manage your privacy settings at:\n  {_PRIVACY_URL}',
    )


def _handle_extra_usage(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        'Configure extra usage on a Claude.ai account at:\n'
        f'  {_UPGRADE_URL}\n'
        'After upgrading, run /login to refresh your local credentials.',
    )


def _handle_passes(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        'Claude Code guest passes are managed in your Claude.ai account.\n'
        '  Visit https://claude.ai to sign in and view remaining passes.',
    )


def _handle_rate_limit_options(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    lines = [
        'When the current account hits a rate limit, you can:',
        '  - Run /upgrade to move to a higher Claude.ai plan.',
        '  - Run /extra-usage to enable per-message billing on a Claude.ai plan.',
        '  - Run /login to switch to an API-key billed account.',
        f'See {_UPGRADE_URL} for plan details.',
    ]
    return _local_result(input_text, '\n'.join(lines))


def _handle_chrome(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _local_result(
        input_text,
        _open_or_link(
            _CHROME_EXTENSION_URL,
            opening_message='Opening the Claude Chrome extension page in your browser…',
            fallback_message='Install the Claude Chrome extension at:',
        ),
    )


def _handle_reload_plugins(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    from pathlib import Path
    from .plugin_runtime import PluginRuntime

    runtime = PluginRuntime.from_workspace(Path(agent.runtime_config.cwd))
    agent.plugin_runtime = runtime
    plugin_count = len(runtime.manifests)
    tool_count = sum(len(manifest.tool_names) for manifest in runtime.manifests)
    hook_count = sum(len(manifest.hook_names) for manifest in runtime.manifests)
    virtual_count = sum(len(manifest.virtual_tools) for manifest in runtime.manifests)
    return _local_result(
        input_text,
        'Reloaded plugins: '
        f'{plugin_count} plugin(s) · {tool_count} tool(s) · {hook_count} hook(s) · '
        f'{virtual_count} virtual tool(s)',
    )


_AVAILABLE_THEMES = (
    'light',
    'dark',
    'light-daltonized',
    'dark-daltonized',
    'light-ansi',
    'dark-ansi',
)


def _config_get(runtime, key_path: str, default=None):
    try:
        return runtime.get_value(key_path)
    except KeyError:
        return default


def _handle_theme(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    runtime = agent.config_runtime
    if runtime is None:
        return _local_result(input_text, 'Config runtime is unavailable.')
    requested = args.strip()
    current = _config_get(runtime, 'theme') or 'light'
    if not requested:
        lines = ['Available themes:']
        for name in _AVAILABLE_THEMES:
            marker = ' (current)' if name == current else ''
            lines.append(f'  - {name}{marker}')
        lines.append('')
        lines.append('Usage: /theme <name>')
        return _local_result(input_text, '\n'.join(lines))
    if requested not in _AVAILABLE_THEMES:
        return _local_result(
            input_text,
            f'Unknown theme "{requested}". Available: {", ".join(_AVAILABLE_THEMES)}.',
        )
    mutation = runtime.set_value('theme', requested, source='local')
    return _local_result(
        input_text,
        f'Theme set to {requested} (saved to {mutation.store_path}).',
    )


def _handle_voice(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    runtime = agent.config_runtime
    if runtime is None:
        return _local_result(input_text, 'Config runtime is unavailable.')
    arg = args.strip().lower()
    current = bool(_config_get(runtime, 'voiceEnabled', False))
    if arg in {'on', 'enable', 'true'}:
        new_value = True
    elif arg in {'off', 'disable', 'false'}:
        new_value = False
    elif not arg:
        new_value = not current
    else:
        return _local_result(input_text, 'Usage: /voice [on|off]')
    mutation = runtime.set_value('voiceEnabled', new_value, source='local')
    state = 'enabled' if new_value else 'disabled'
    extra = ''
    if new_value:
        import platform

        if platform.system() == 'Linux':
            extra = (
                '\nLinux note: confirm microphone access in your audio settings '
                'before holding to talk.'
            )
    return _local_result(
        input_text,
        f'Voice mode {state} (saved to {mutation.store_path}).{extra}',
    )


def _handle_sandbox_toggle(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    runtime = agent.config_runtime
    if runtime is None:
        return _local_result(input_text, 'Config runtime is unavailable.')
    trimmed = args.strip()
    if not trimmed:
        enabled = bool(_config_get(runtime, 'sandbox.enabled', False))
        excluded = _config_get(runtime, 'sandbox.excludedCommands') or []
        lines = [
            f'Sandbox: {"enabled" if enabled else "disabled"}',
            f'Excluded commands ({len(excluded)}):',
        ]
        for pattern in excluded:
            lines.append(f'  - {pattern}')
        lines.append('')
        lines.append(
            'Usage: /sandbox-toggle exclude "<pattern>"  '
            '— append a command pattern to the local sandbox excludes.'
        )
        return _local_result(input_text, '\n'.join(lines))

    parts = trimmed.split(None, 1)
    subcommand = parts[0].lower()
    if subcommand != 'exclude':
        return _local_result(
            input_text,
            f'Unknown subcommand "{subcommand}". Available: exclude.',
        )
    if len(parts) < 2 or not parts[1].strip():
        return _local_result(
            input_text,
            'Usage: /sandbox-toggle exclude "<pattern>" '
            '(e.g., /sandbox-toggle exclude "npm run test:*").',
        )
    pattern = parts[1].strip().strip('"').strip("'")
    existing = list(_config_get(runtime, 'sandbox.excludedCommands') or [])
    if pattern in existing:
        return _local_result(
            input_text,
            f'Pattern "{pattern}" is already in sandbox.excludedCommands.',
        )
    existing.append(pattern)
    mutation = runtime.set_value(
        'sandbox.excludedCommands', existing, source='local',
    )
    return _local_result(
        input_text,
        f'Added "{pattern}" to sandbox.excludedCommands in {mutation.store_path}.',
    )


_KEYBINDINGS_TEMPLATE = (
    '{\n'
    '  "$schema": "https://claude.ai/schemas/keybindings.json",\n'
    '  "bindings": {\n'
    '    // "chat:submit": "ctrl+enter"\n'
    '  }\n'
    '}\n'
)


def _handle_keybindings(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    from pathlib import Path

    cwd = Path(agent.runtime_config.cwd)
    path = cwd / '.claude' / 'keybindings.json'
    created = False
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_KEYBINDINGS_TEMPLATE, encoding='utf-8')
        created = True
    verb = 'Created' if created else 'Found'
    import os

    editor = os.environ.get('EDITOR') or os.environ.get('VISUAL') or '<your editor>'
    return _local_result(
        input_text,
        f'{verb} {path}.\n'
        f'Edit it with: {editor} {path}',
    )


def _handle_btw(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    question = args.strip()
    if not question:
        return _local_result(input_text, 'Usage: /btw <your question>')
    prompt = (
        'Answer the following side question concisely. Do NOT modify any files, '
        "run shell commands, or alter the workspace — just answer in text.\n\n"
        f'Side question: {question}'
    )
    return _prompt_result(input_text, prompt)


def _read_package_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version('claw-code-agent')
    except Exception:
        return 'unknown'


def _handle_version(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    import platform
    import sys

    pkg_version = _read_package_version()
    py_version = platform.python_version()
    impl = sys.implementation.name
    return _local_result(
        input_text,
        f'claw-code-agent {pkg_version} (Python {py_version}, {impl}).',
    )


_INIT_PROMPT = (
    'Please analyze this codebase and create a CLAUDE.md file, which will be '
    'given to future instances of Claude Code to operate in this repository.\n'
    '\n'
    'What to add:\n'
    '1. Commands that will be commonly used, such as how to build, lint, and '
    'run tests. Include the necessary commands to develop in this codebase, '
    'such as how to run a single test.\n'
    '2. High-level code architecture and structure so that future instances '
    'can be productive more quickly. Focus on the "big picture" architecture '
    'that requires reading multiple files to understand.\n'
    '\n'
    'Usage notes:\n'
    "- If there's already a CLAUDE.md, suggest improvements to it.\n"
    '- When you make the initial CLAUDE.md, do not repeat yourself and do not '
    'include obvious instructions like "Provide helpful error messages to '
    'users", "Write unit tests for all new utilities", "Never include '
    'sensitive information (API keys, tokens) in code or commits".\n'
    '- Avoid listing every component or file structure that can be easily '
    'discovered.\n'
    "- Don't include generic development practices.\n"
    '- If there are Cursor rules (in .cursor/rules/ or .cursorrules) or '
    'Copilot rules (in .github/copilot-instructions.md), make sure to include '
    'the important parts.\n'
    '- If there is a README.md, make sure to include the important parts.\n'
    '- Do not make up information such as "Common Development Tasks", "Tips '
    'for Development", "Support and Documentation" unless this is expressly '
    'included in other files that you read.\n'
    '- Be sure to prefix the file with the following text:\n'
    '\n'
    '```\n'
    '# CLAUDE.md\n'
    '\n'
    'This file provides guidance to Claude Code (claude.ai/code) when '
    'working with code in this repository.\n'
    '```'
)


def _handle_init(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    return _prompt_result(input_text, _INIT_PROMPT)


def _detect_ide_environment() -> tuple[str, list[str]]:
    """Return a (label, details) summary of the IDE/terminal integration."""
    import os

    details: list[str] = []
    label = 'No IDE detected'
    term_program = os.environ.get('TERM_PROGRAM')
    if term_program:
        details.append(f'TERM_PROGRAM={term_program}')
    if os.environ.get('VSCODE_INJECTION') or os.environ.get('VSCODE_PID'):
        label = 'Visual Studio Code'
        for key in ('VSCODE_PID', 'VSCODE_IPC_HOOK', 'VSCODE_GIT_IPC_HANDLE'):
            value = os.environ.get(key)
            if value:
                details.append(f'{key}={value}')
    elif os.environ.get('JETBRAINS_IDE') or os.environ.get('TERMINAL_EMULATOR', '').startswith('JetBrains'):
        label = 'JetBrains IDE'
        for key in ('JETBRAINS_IDE', 'TERMINAL_EMULATOR', 'IDEA_INITIAL_DIRECTORY'):
            value = os.environ.get(key)
            if value:
                details.append(f'{key}={value}')
    elif term_program == 'iTerm.app':
        label = 'iTerm2 (no IDE integration)'
    elif term_program == 'Apple_Terminal':
        label = 'Terminal.app (no IDE integration)'
    elif term_program == 'tmux':
        label = 'tmux session (no IDE integration)'
    elif os.environ.get('SSH_CONNECTION'):
        label = 'SSH session (no IDE integration)'
        details.append('SSH_CONNECTION present')
    return label, details


def _handle_ide(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    label, details = _detect_ide_environment()
    lines = [f'IDE/terminal integration: {label}']
    for detail in details:
        lines.append(f'  - {detail}')
    if not details and label.startswith('No IDE'):
        lines.append('  (No relevant TERM_PROGRAM/VSCODE/JETBRAINS env vars found.)')
    lines.append('')
    lines.append(
        'IDE auto-connect dialogs are not implemented in the Python runtime; '
        'launch the agent from inside your IDE terminal to inherit its env.'
    )
    return _local_result(input_text, '\n'.join(lines))


def _handle_plugin(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    runtime = agent.plugin_runtime
    if runtime is None:
        return _local_result(input_text, 'Plugin runtime is unavailable.')
    sub = args.strip().split(None, 1)
    action = sub[0].lower() if sub else 'list'
    if action in {'help', '--help', '-h'}:
        return _local_result(
            input_text,
            'Usage: /plugin [list]\n'
            '  list  Show installed plugin manifests (default).\n'
            '\n'
            'Marketplace install/uninstall/enable/disable flows are not '
            'implemented in the Python runtime — edit plugin manifests on '
            'disk and run /reload-plugins to pick up changes.',
        )
    if action != 'list':
        return _local_result(
            input_text,
            f'Unknown plugin subcommand "{action}". Try /plugin help.',
        )
    manifests = runtime.manifests
    if not manifests:
        return _local_result(
            input_text,
            'No installed plugins.\n'
            'Drop a plugin manifest under .claude/plugins/<name>/manifest.json '
            'and run /reload-plugins.',
        )
    lines = [f'Installed plugins ({len(manifests)}):']
    for manifest in manifests:
        version_str = f' v{manifest.version}' if manifest.version else ''
        lines.append(f'- {manifest.name}{version_str}')
        if manifest.description:
            lines.append(f'    {manifest.description}')
        if manifest.tool_names:
            lines.append(f'    tools: {", ".join(manifest.tool_names)}')
        if manifest.hook_names:
            lines.append(f'    hooks: {", ".join(manifest.hook_names)}')
        if manifest.virtual_tools:
            lines.append(
                f'    virtual tools: '
                f'{", ".join(tool.name for tool in manifest.virtual_tools)}'
            )
    return _local_result(input_text, '\n'.join(lines))


def _handle_remote_env(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    runtime = agent.remote_runtime
    if runtime is None:
        return _local_result(input_text, 'Remote runtime is unavailable.')
    config = agent.config_runtime
    requested = args.strip()
    current_default = (
        _config_get(config, 'defaultRemoteEnvironment') if config else None
    )
    if not requested:
        lines = ['Available remote environments:']
        if not runtime.profiles:
            lines.append('  (no profiles found in .claude/remote.json)')
        for profile in runtime.profiles:
            marker = ' (default)' if profile.name == current_default else ''
            lines.append(
                f'  - {profile.name} [{profile.mode}] -> {profile.target}{marker}'
            )
        if current_default:
            lines.append('')
            lines.append(f'Current default: {current_default}')
        lines.append('')
        lines.append('Usage: /remote-env <name>  — set the default profile')
        lines.append('Usage: /remote-env clear   — unset the default profile')
        return _local_result(input_text, '\n'.join(lines))

    if requested.lower() == 'clear':
        if config is None:
            return _local_result(input_text, 'Config runtime is unavailable.')
        if current_default is None:
            return _local_result(input_text, 'No default remote environment was set.')
        # set_value with None — write null to settings
        mutation = config.set_value('defaultRemoteEnvironment', None, source='local')
        return _local_result(
            input_text,
            f'Cleared default remote environment (saved to {mutation.store_path}).',
        )

    profile = runtime.get_profile(requested)
    if profile is None:
        return _local_result(
            input_text,
            f'Unknown remote environment "{requested}". '
            'Run /remote-env to list available profiles.',
        )
    if config is None:
        return _local_result(input_text, 'Config runtime is unavailable.')
    mutation = config.set_value(
        'defaultRemoteEnvironment', profile.name, source='local',
    )
    return _local_result(
        input_text,
        f'Default remote environment set to {profile.name} '
        f'[{profile.mode}] -> {profile.target} (saved to {mutation.store_path}).',
    )


def _handle_bridge(
    agent: 'LocalCodingAgent',
    args: str,
    input_text: str,
) -> SlashCommandResult:
    runtime = agent.remote_runtime
    requested_name = args.strip() or None
    lines = ['Remote-control bridge: not implemented in the Python runtime.']
    lines.append(
        '  The npm CLI hosts an interactive bridge against claude.ai; this '
        'runtime only inspects the local remote-runtime state.'
    )
    if runtime is None:
        lines.append('  (Remote runtime is unavailable.)')
        return _local_result(input_text, '\n'.join(lines))

    connection = runtime.active_connection
    if connection is not None:
        lines.append('')
        lines.append('Active local remote connection:')
        lines.append(f'  - mode: {connection.mode}')
        lines.append(f'  - target: {connection.target}')
        if connection.profile_name:
            lines.append(f'  - profile: {connection.profile_name}')
        if connection.session_url:
            lines.append(f'  - session URL: {connection.session_url}')
        if connection.workspace_cwd:
            lines.append(f'  - workspace: {connection.workspace_cwd}')
    else:
        lines.append('')
        lines.append('No active local remote connection.')
    if requested_name:
        profile = runtime.get_profile(requested_name)
        lines.append('')
        if profile is None:
            lines.append(
                f'No matching remote profile for "{requested_name}". '
                'Run /remote-env to list available profiles.'
            )
        else:
            lines.append(
                f'Matched remote profile "{profile.name}" '
                f'({profile.mode} -> {profile.target}). '
                'Use the npm CLI bridge to actually connect.'
            )
    return _local_result(input_text, '\n'.join(lines))


def _gh_auth_status() -> tuple[str, str]:
    """Return (status, detail) — status is one of 'not_installed',
    'authenticated', 'not_authenticated', 'unknown'."""
    import shutil
    import subprocess

    if shutil.which('gh') is None:
        return ('not_installed', 'gh CLI not on PATH')
    try:
        result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return ('unknown', f'gh auth status failed: {exc}')
    detail = (result.stderr or result.stdout or '').strip().splitlines()
    summary = detail[0] if detail else ''
    if result.returncode == 0:
        return ('authenticated', summary or 'Authenticated to GitHub')
    return ('not_authenticated', summary or 'Not authenticated to GitHub')


def _handle_remote_setup(
    agent: 'LocalCodingAgent',
    _args: str,
    input_text: str,
) -> SlashCommandResult:
    code_web_url = 'https://claude.ai/code'
    gh_status, gh_detail = _gh_auth_status()
    lines = [
        'Claude Code on the web setup:',
        f'  Visit {code_web_url} to manage your environments.',
        '',
        f'GitHub CLI: {gh_status}',
        f'  {gh_detail}',
    ]
    if gh_status == 'not_installed':
        lines.append('  Install gh from https://cli.github.com to import a GitHub token.')
    elif gh_status == 'not_authenticated':
        lines.append('  Run `gh auth login` to authenticate before importing your token.')
    elif gh_status == 'authenticated':
        lines.append('  You can run `gh auth token` to retrieve the token to import on the web.')
    lines.append('')
    lines.append(
        'Token import / default-environment provisioning is not implemented '
        'in the Python runtime — complete remote setup from the npm CLI or '
        'directly on claude.ai/code.'
    )
    return _local_result(input_text, '\n'.join(lines))


def _prompt_result(input_text: str, prompt: str) -> SlashCommandResult:
    """Return a prompt-type result — the prompt gets sent to the model."""
    return SlashCommandResult(
        handled=True,
        should_query=True,
        prompt=prompt,
        transcript=({'role': 'user', 'content': input_text},),
    )


def _local_result(input_text: str, output: str) -> SlashCommandResult:
    transcript = (
        {'role': 'user', 'content': input_text},
        {'role': 'assistant', 'content': output},
    )
    return SlashCommandResult(
        handled=True,
        should_query=False,
        output=output,
        transcript=transcript,
    )
