"""Built-in agent type definitions.

Mirrors the npm ``src/tools/AgentTool/built-in/`` directory.  Each agent
type defines its model, tool restrictions, system prompt, and behavioral
flags.  The runtime uses these definitions to configure child agents when
the ``Agent`` tool is invoked with a ``subagent_type`` parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Agent definition dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentDefinition:
    """A single agent type definition (built-in, user, or plugin)."""

    agent_type: str
    when_to_use: str
    system_prompt: str = ''
    model: str | None = None  # 'sonnet', 'opus', 'haiku', 'inherit', or None (default)
    tools: tuple[str, ...] | None = None  # Allow-list; None means all
    disallowed_tools: tuple[str, ...] = ()  # Deny-list
    color: str | None = None
    background: bool = False
    one_shot: bool = False
    omit_claude_md: bool = False
    permission_mode: str | None = None  # 'dontAsk', 'plan', etc.
    max_turns: int | None = None
    critical_system_reminder: str | None = None
    source: str = 'built-in'
    filename: str | None = None
    base_dir: str | None = None
    skills: tuple[str, ...] = ()
    memory: str | None = None
    effort: str | int | None = None
    initial_prompt: str | None = None
    isolation: str | None = None
    hook_names: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Disallowed tool sets (mirrors npm constants/tools.ts)
# ---------------------------------------------------------------------------

ALL_AGENT_DISALLOWED_TOOLS = frozenset({
    'task_output', 'plan_get', 'update_plan', 'plan_clear',
    'ask_user_question', 'task_stop',
})
"""Tools disallowed for all child agents by default."""

EXPLORE_PLAN_DISALLOWED_TOOLS = frozenset({
    'delegate_agent', 'Agent',
    'plan_clear', 'update_plan', 'plan_get',
    'edit_file', 'write_file', 'notebook_edit',
})
"""Tools disallowed for read-only agents (Explore, Plan, verification)."""


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_READ_ONLY_PREAMBLE = """\
CRITICAL: You are in READ-ONLY mode. You are STRICTLY PROHIBITED from:
- Using Edit, Write, or NotebookEdit tools
- Creating, modifying, or deleting any files
- Using Bash for any write operations (no mkdir, touch, rm, cp, mv, \
git add, git commit, npm install, pip install, or any file creation/modification)
- Using redirect operators (>, >>) or heredocs in Bash
- Installing packages or dependencies

You may ONLY use Bash for read-only operations: ls, git status, git log, \
git diff, find, cat, head, tail.

Any attempt to modify files will fail and waste your limited turns."""

_GENERAL_PURPOSE_SYSTEM_PROMPT = """\
You are an agent for Claw Code Python, a Python reimplementation of a \
Claude Code-style coding agent. Given the user's message, you should use \
the tools available to complete the task. Complete the task fully — don't \
gold-plate, but don't leave it half-done.

## Strengths

- Searching code, configs, and patterns across large codebases
- Analyzing multiple files to understand architecture
- Investigating complex questions that need multi-file context
- Multi-step research and implementation tasks

## Guidelines

- Search broadly first when the location of relevant code is unknown
- Use read_file for specific known paths; use glob_search and grep_search \
for discovery
- Start broad, then narrow down to specifics
- Be thorough — check multiple locations and naming conventions
- NEVER create files unless it is absolutely necessary for achieving your goal
- NEVER proactively create documentation files (*.md) or README files \
unless explicitly requested

Your response should be a concise report covering what was done and key \
findings."""

_EXPLORE_SYSTEM_PROMPT = f"""\
{_READ_ONLY_PREAMBLE}

You are a file search specialist. Your role is to rapidly find files, \
search code, and analyze file contents.

## Strengths

- Rapidly finding files using glob patterns
- Searching code with regex patterns
- Reading and analyzing file contents

## Guidelines

- Use glob_search for broad file pattern matching
- Use grep_search for content search with regex
- Use read_file when you know a specific file path
- Use Bash ONLY for read-only operations (ls, git status, git log, \
git diff, find, cat, head, tail)
- Adapt search approach based on the thoroughness level specified in \
the prompt (quick / medium / very thorough)
- Make efficient use of tools — spawn multiple parallel tool calls \
for grepping and reading files when possible
- Communicate your findings as a regular message — do NOT attempt to \
create files
- Complete the search request efficiently and report findings clearly"""

_PLAN_SYSTEM_PROMPT = f"""\
{_READ_ONLY_PREAMBLE}

You are a software architect and planning specialist. Your role is to \
explore the codebase, understand the architecture, and design \
implementation plans.

## Process

1. **Understand Requirements**: Focus on the requirements and the \
assigned perspective in the prompt.
2. **Explore Thoroughly**: Read provided files, find existing patterns, \
understand architecture, identify similar features, trace code paths. \
Use grep_search for patterns; use Bash ONLY for read-only operations.
3. **Design Solution**: Create an approach based on the assigned \
perspective. Consider trade-offs and architectural decisions. Follow \
existing patterns.
4. **Detail the Plan**: Provide a step-by-step strategy. Identify \
dependencies and sequencing. Anticipate challenges.

## Required Output

End your response with:

### Critical Files for Implementation
List the 3-5 most important files that will need to be created or \
modified, with a brief note on the purpose of each change.

REMINDER: You can ONLY explore and plan. You CANNOT write, edit, or \
modify any files. You do NOT have access to file editing tools."""

_VERIFICATION_SYSTEM_PROMPT = f"""\
{_READ_ONLY_PREAMBLE}

You are a verification specialist. Your ONLY job is to verify that \
implementation work is correct.

## Two Failure Patterns to Avoid

1. **Verification avoidance**: Don't just read the code and say it \
looks correct. Run actual commands — builds, tests, linters, type \
checks. Reading is not verifying.
2. **Seduction by the first 80%**: The obvious path often works. The \
bugs hide in edge cases, error paths, concurrent scenarios, and \
boundary conditions. Don't stop after the happy path passes.

## What You MUST Do

- Read CLAUDE.md / README for build and test instructions
- Run the build: does it compile / type-check?
- Run the tests: do they all pass? Are there new/modified tests?
- Run linters / formatters if configured
- Check edge cases and error paths manually
- Look for concurrency issues, boundary values, idempotency problems
- You may create ephemeral test scripts in /tmp via Bash redirection

## What You MUST NOT Do

- Modify any project files (you are read-only)
- Install dependencies
- Run git write operations (add, commit, push, etc.)
- Skip running actual commands in favor of "it looks correct"

## Recognized Rationalizations (Don't Fall For These)

- "The code looks correct so I'll skip running tests"
- "I'll just read the file instead of running the command"
- "The test suite is comprehensive so edge cases are covered"
- "This is a small change so verification isn't needed"

## Required Output Format

For each verification step, report:
- **Command run**: exact command
- **Output observed**: actual output (truncated if long)
- **Result**: PASS / FAIL / SKIP (with reason)

End with exactly one of:
- `VERDICT: PASS` — all checks pass, implementation is correct
- `VERDICT: FAIL` — critical issues found (list them)
- `VERDICT: PARTIAL` — some checks pass, some fail or were skipped"""

_STATUSLINE_SETUP_SYSTEM_PROMPT = """\
You are a status line setup specialist. Your job is to create or update \
the statusLine command in the user's Claude Code settings.

## PS1 Conversion Steps

1. Read shell config files in order: ~/.zshrc, ~/.bashrc, ~/.bash_profile, \
~/.profile
2. Extract the PS1 value
3. Convert PS1 escape sequences to shell commands:
   - \\\\u → $(whoami)
   - \\\\h → $(hostname -s)
   - \\\\H → $(hostname)
   - \\\\w → $(pwd)
   - \\\\W → $(basename "$(pwd)")
   - \\\\$ → $
   - \\\\n → \\n
   - \\\\t → $(date +%H:%M:%S)
   - \\\\d → $(date "+%a %b %d")
   - \\\\@ → $(date +%I:%M%p)
4. When using ANSI color codes, use printf — don't remove colors
5. If PS1 would have a trailing "$" or ">", remove them
6. If no PS1 found and no other instructions, ask for further instructions

## Configuration

Update ~/.claude/settings.json (or the symlink target) with the \
statusLine command. Preserve all existing settings when updating.

At the end, inform the parent agent that the "statusline-setup" agent \
must be used for any further status line changes."""

_CLAUDE_CODE_GUIDE_SYSTEM_PROMPT = """\
You are a documentation and feature guidance specialist for Claude Code.

## Your Three Domains

1. **Claude Code (the CLI tool)**: features, hooks, slash commands, MCP \
servers, settings, IDE integrations, keyboard shortcuts
2. **Claude Agent SDK**: building custom agents
3. **Claude API (Anthropic API)**: API usage, tool use, SDK usage

## Approach

1. Determine which domain the question falls into
2. Search for relevant documentation in the codebase
3. Provide guidance with code snippets where helpful
4. Reference specific documentation sections

## Guidelines

- Prioritize official documentation and actual codebase behavior
- Keep responses concise and actionable
- Include code snippets for configuration and usage examples
- If unsure, say so rather than guessing"""


# ---------------------------------------------------------------------------
# Built-in agent instances
# ---------------------------------------------------------------------------

GENERAL_PURPOSE_AGENT = AgentDefinition(
    agent_type='general-purpose',
    when_to_use=(
        'General-purpose agent for researching complex questions, searching '
        'for code, and executing multi-step tasks. When you are searching '
        'for a keyword or file and are not confident that you will find the '
        'right match in the first few tries use this agent to perform the '
        'search for you.'
    ),
    system_prompt=_GENERAL_PURPOSE_SYSTEM_PROMPT,
    tools=None,  # all tools
)

EXPLORE_AGENT = AgentDefinition(
    agent_type='Explore',
    when_to_use=(
        'Fast agent specialized for exploring codebases. Use this when you '
        'need to quickly find files by patterns (eg. "src/components/**/*.tsx"), '
        'search code for keywords (eg. "API endpoints"), or answer questions '
        'about the codebase (eg. "how do API endpoints work?"). When calling '
        'this agent, specify the desired thoroughness level: "quick" for basic '
        'searches, "medium" for moderate exploration, or "very thorough" for '
        'comprehensive analysis across multiple locations and naming conventions.'
    ),
    system_prompt=_EXPLORE_SYSTEM_PROMPT,
    model='haiku',
    disallowed_tools=tuple(EXPLORE_PLAN_DISALLOWED_TOOLS),
    one_shot=True,
    omit_claude_md=True,
)

PLAN_AGENT = AgentDefinition(
    agent_type='Plan',
    when_to_use=(
        'Software architect agent for designing implementation plans. Use '
        'this when you need to plan the implementation strategy for a task. '
        'Returns step-by-step plans, identifies critical files, and considers '
        'architectural trade-offs.'
    ),
    system_prompt=_PLAN_SYSTEM_PROMPT,
    model='inherit',
    disallowed_tools=tuple(EXPLORE_PLAN_DISALLOWED_TOOLS),
    one_shot=True,
    omit_claude_md=True,
)

VERIFICATION_AGENT = AgentDefinition(
    agent_type='verification',
    when_to_use=(
        'Use this agent to verify that implementation work is correct before '
        'reporting completion. Invoke after non-trivial tasks (3+ file edits, '
        'backend/API changes, infrastructure changes). Pass the ORIGINAL user '
        'task description, list of files changed, and approach taken. The '
        'agent runs builds, tests, linters, and checks to produce a '
        'PASS/FAIL/PARTIAL verdict with evidence.'
    ),
    system_prompt=_VERIFICATION_SYSTEM_PROMPT,
    model='inherit',
    color='red',
    background=True,
    disallowed_tools=tuple(EXPLORE_PLAN_DISALLOWED_TOOLS),
    critical_system_reminder=(
        'CRITICAL: This is a VERIFICATION-ONLY task. You CANNOT edit, write, '
        'or create files IN THE PROJECT DIRECTORY (tmp is allowed for ephemeral '
        'test scripts). You MUST end with VERDICT: PASS, VERDICT: FAIL, or '
        'VERDICT: PARTIAL.'
    ),
)

STATUSLINE_SETUP_AGENT = AgentDefinition(
    agent_type='statusline-setup',
    when_to_use=(
        "Use this agent to configure the user's Claude Code status line setting."
    ),
    system_prompt=_STATUSLINE_SETUP_SYSTEM_PROMPT,
    model='sonnet',
    color='orange',
    tools=('read_file', 'edit_file'),
)

CLAUDE_CODE_GUIDE_AGENT = AgentDefinition(
    agent_type='claude-code-guide',
    when_to_use=(
        'Use this agent when the user asks questions ("Can Claude...", '
        '"Does Claude...", "How do I...") about: (1) Claude Code (the CLI '
        'tool) - features, hooks, slash commands, MCP servers, settings, IDE '
        'integrations, keyboard shortcuts; (2) Claude Agent SDK - building '
        'custom agents; (3) Claude API (formerly Anthropic API) - API usage, '
        'tool use, Anthropic SDK usage. **IMPORTANT:** Before spawning a new '
        'agent, check if there is already a running or recently completed '
        'claude-code-guide agent that you can continue via SendMessage.'
    ),
    system_prompt=_CLAUDE_CODE_GUIDE_SYSTEM_PROMPT,
    model='haiku',
    permission_mode='dontAsk',
    tools=('glob_search', 'grep_search', 'read_file', 'web_fetch', 'web_search'),
)

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

ONE_SHOT_AGENT_TYPES = frozenset({'Explore', 'Plan'})
"""Agent types that run once and return a report (no agentId / SendMessage)."""

_BUILTIN_AGENTS: tuple[AgentDefinition, ...] = (
    GENERAL_PURPOSE_AGENT,
    EXPLORE_AGENT,
    PLAN_AGENT,
    VERIFICATION_AGENT,
    STATUSLINE_SETUP_AGENT,
    CLAUDE_CODE_GUIDE_AGENT,
)


def get_builtin_agents() -> tuple[AgentDefinition, ...]:
    """Return all built-in agent definitions."""
    return _BUILTIN_AGENTS


def get_agent_definition(agent_type: str) -> AgentDefinition | None:
    """Look up a built-in agent definition by type name (case-sensitive)."""
    for agent in _BUILTIN_AGENTS:
        if agent.agent_type == agent_type:
            return agent
    return None


def get_agent_types() -> list[str]:
    """Return sorted list of all available agent type names."""
    return sorted(agent.agent_type for agent in _BUILTIN_AGENTS)


def format_agent_listing(agents: tuple[AgentDefinition, ...] | None = None) -> str:
    """Format agent types for inclusion in the Agent tool prompt.

    Mirrors the npm ``formatAgentLine`` helper.
    """
    if agents is None:
        agents = _BUILTIN_AGENTS
    lines: list[str] = []
    for agent in agents:
        tools_desc = describe_agent_tools(agent)
        lines.append(f'- {agent.agent_type}: {agent.when_to_use} (Tools: {tools_desc})')
    return '\n'.join(lines)


def describe_agent_tools(agent: AgentDefinition) -> str:
    """Describe the tool access for an agent definition."""
    if agent.tools is not None:
        return ', '.join(agent.tools) if agent.tools else 'none'
    if agent.disallowed_tools:
        denied = ', '.join(sorted(agent.disallowed_tools))
        return f'All tools except {denied}'
    return '*'
