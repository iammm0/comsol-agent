"""Bundled skill definitions — prompt-type skills invocable via the Skill tool.

Mirrors the npm ``src/skills/bundled/`` module.

Bundled skills differ from slash commands:
- They generate AI prompts sent to the model (prompt-type).
- They carry ``when_to_use`` guidance for model auto-invocation.
- They can restrict ``allowed_tools`` during execution.
- They appear in system-reminder skill listings for model discovery.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .agent_runtime import LocalCodingAgent


@dataclass(frozen=True)
class BundledSkill:
    """A bundled skill definition."""

    name: str
    description: str
    when_to_use: str = ''
    aliases: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    user_invocable: bool = True
    get_prompt: Callable[['LocalCodingAgent', str], str] = lambda _a, _args: ''


# ---------------------------------------------------------------------------
# Skill prompt generators
# ---------------------------------------------------------------------------

def _simplify_prompt(agent: 'LocalCodingAgent', args: str) -> str:
    """Generate the simplify review prompt."""
    cwd = str(agent.runtime_config.cwd)
    diff = ''
    try:
        proc = subprocess.run(
            ['git', 'diff', 'HEAD'],
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )
        diff = proc.stdout.strip()
    except Exception:
        pass

    if not diff:
        try:
            proc = subprocess.run(
                ['git', 'diff'],
                cwd=cwd, capture_output=True, text=True, timeout=30,
            )
            diff = proc.stdout.strip()
        except Exception:
            pass

    diff_section = f'```diff\n{diff}\n```' if diff else 'No changes detected — run `git diff` to verify.'

    return f"""Review the changed code for reuse, quality, and efficiency, then fix any issues found.

## Changed Code

{diff_section}

## Review Checklist

### Code Reuse
- Duplicated functions or logic that should be consolidated
- Redundant utilities or helpers
- Patterns that should use existing abstractions

### Code Quality
- Redundant state or unnecessary variables
- Parameter sprawl (too many function arguments)
- Copy-paste code that should be refactored
- Leaky abstractions or wrong abstraction level
- Stringly-typed code that should use enums/types
- Overly nested conditionals

### Efficiency
- N+1 query or call patterns
- Missed concurrency opportunities (parallel I/O)
- Hot-path bloat (unnecessary work in tight loops)
- Memory leaks or unbounded growth

## Instructions

1. Read the full diff above
2. For each category, identify concrete issues with file paths and line numbers
3. Fix each issue directly — do not just report them
4. After fixing, verify the changes compile/run correctly

{f'Additional context: {args}' if args.strip() else ''}"""


def _verify_prompt(agent: 'LocalCodingAgent', args: str) -> str:
    """Generate the verify prompt."""
    return f"""Verify that the recent code changes work correctly.

## Instructions

1. Identify what was changed (check `git diff` and `git status`)
2. Determine the appropriate verification strategy:
   - **Unit tests**: Run existing tests, check for failures
   - **Integration tests**: Run broader test suites if available
   - **Manual verification**: Start the app/server and test the feature
3. Run the verification
4. Report the result clearly:
   - PASS: All checks passed, feature works as expected
   - FAIL: Describe what failed and why
   - PARTIAL: Some checks passed, some need attention

## Verification Strategy

- For CLI tools: Run the command with test inputs
- For servers: Start the server, make test requests
- For libraries: Run the test suite
- For config changes: Validate the config loads correctly

{f'Specific focus: {args}' if args.strip() else 'Verify the most recent changes.'}"""


def _debug_prompt(agent: 'LocalCodingAgent', args: str) -> str:
    """Generate the debug prompt."""
    import os

    lines = ['## Debug Session Info', '']
    lines.append(f'Working directory: {agent.runtime_config.cwd}')
    lines.append(f'Model: {agent.model_config.model}')
    lines.append(f'Base URL: {agent.model_config.base_url}')

    session = agent.last_session
    if session:
        lines.append(f'Messages in session: {len(session.messages)}')
        tool_count = sum(1 for m in session.messages if m.role == 'tool')
        lines.append(f'Tool results: {tool_count}')

    usage = agent.cumulative_usage
    lines.append(f'Total tokens used: {usage.total_tokens:,}')
    lines.append(f'Cost: ${agent.cumulative_cost_usd:.4f}')

    # Check for debug log
    debug_log = os.environ.get('CLAUDE_CODE_DEBUG_LOG', '')
    if debug_log:
        lines.append(f'Debug log: {debug_log}')
    else:
        lines.append('Debug logging: not enabled (set CLAUDE_CODE_DEBUG_LOG to enable)')

    return '\n'.join(lines)


def _update_config_prompt(agent: 'LocalCodingAgent', args: str) -> str:
    """Generate the update-config prompt."""
    return f"""Help configure the agent settings.

## Settings File Locations

- **Global**: `~/.claude/settings.json` — applies to all projects
- **Project**: `.claude/settings.json` — project-specific, committed to git
- **Local**: `.claude/settings.local.json` — project-specific, gitignored

## Configurable Settings

### Hooks
Event-driven shell commands that run on tool use or lifecycle events:
- `PreToolUse` — runs before a tool executes (can block with exit code 2)
- `PostToolUse` — runs after a tool completes
- `PreCompact` — runs before conversation compaction

Hook format:
```json
{{
  "hooks": {{
    "PreToolUse": [
      {{
        "matcher": "Bash",
        "hooks": [
          {{
            "type": "command",
            "command": "echo 'tool: $TOOL_NAME'"
          }}
        ]
      }}
    ]
  }}
}}
```

### Permissions
Tool permission rules:
```json
{{
  "permissions": {{
    "allow": ["Read", "Grep", "Glob"],
    "deny": ["Bash(rm:*)"]
  }}
}}
```

### Environment Variables
```json
{{
  "env": {{
    "MY_VAR": "value"
  }}
}}
```

{f'User request: {args}' if args.strip() else 'What would you like to configure?'}"""


# ---------------------------------------------------------------------------
# Skill registry
# ---------------------------------------------------------------------------

BUNDLED_SKILLS: tuple[BundledSkill, ...] = (
    BundledSkill(
        name='simplify',
        description='Review changed code for reuse, quality, and efficiency, then fix issues.',
        when_to_use='When the user asks to review, simplify, or clean up recent code changes.',
        allowed_tools=('read_file', 'edit_file', 'write_file', 'bash', 'grep_search', 'glob_search'),
        get_prompt=_simplify_prompt,
    ),
    BundledSkill(
        name='verify',
        description='Verify a code change works by running the app and tests.',
        when_to_use='When the user asks to verify, test, or check that recent changes work.',
        allowed_tools=('read_file', 'bash', 'grep_search', 'glob_search'),
        get_prompt=_verify_prompt,
    ),
    BundledSkill(
        name='debug',
        description='Debug the current session — show diagnostics, token usage, and config.',
        when_to_use='When the user asks to debug the agent session or check diagnostics.',
        user_invocable=True,
        get_prompt=_debug_prompt,
    ),
    BundledSkill(
        name='update-config',
        description='Configure settings via settings.json — hooks, permissions, env vars.',
        when_to_use='When the user wants to configure hooks, permissions, or settings.',
        aliases=('config-help',),
        allowed_tools=('read_file',),
        get_prompt=_update_config_prompt,
    ),
)


def get_bundled_skills() -> tuple[BundledSkill, ...]:
    """Return all registered bundled skills."""
    return BUNDLED_SKILLS


def find_bundled_skill(name: str) -> BundledSkill | None:
    """Look up a bundled skill by name or alias."""
    lowered = name.lower()
    for skill in BUNDLED_SKILLS:
        if lowered == skill.name or lowered in skill.aliases:
            return skill
    return None


def format_skills_for_system_prompt(max_chars: int = 8000) -> str:
    """Format bundled skills for inclusion in system-reminder messages.

    The model discovers available skills through this listing.
    """
    lines = ['Available skills (invoke via Skill tool):']
    char_count = len(lines[0])

    for skill in BUNDLED_SKILLS:
        if not skill.user_invocable:
            continue
        entry = f'- {skill.name}: {skill.description}'
        if skill.when_to_use:
            entry += f' When to use: {skill.when_to_use}'
        if len(entry) > 250:
            entry = entry[:247] + '...'
        if char_count + len(entry) + 1 > max_chars:
            break
        lines.append(entry)
        char_count += len(entry) + 1

    return '\n'.join(lines)
