"""
BashTool security validation module.

Ported from npm src/tools/BashTool/bashSecurity.ts and related files.
Provides comprehensive command validation to detect and block dangerous
shell commands, injection patterns, and obfuscation techniques.

The main entry point is `bash_command_is_safe(command)` which returns a
SecurityResult indicating whether the command should be allowed, blocked,
or needs user confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class SecurityBehavior(Enum):
    """Possible outcomes of a security check."""
    ALLOW = 'allow'        # Command is safe, allow without asking
    ASK = 'ask'            # Command needs user confirmation
    DENY = 'deny'          # Command is outright blocked
    PASSTHROUGH = 'passthrough'  # Check has no opinion, continue to next


@dataclass(frozen=True)
class SecurityResult:
    """Result of a security validation check."""
    behavior: SecurityBehavior
    message: str
    is_misparsing: bool = False  # For misparsing-specific concerns


def _allow(message: str = 'Command allowed') -> SecurityResult:
    return SecurityResult(SecurityBehavior.ALLOW, message)


def _ask(message: str, *, misparsing: bool = False) -> SecurityResult:
    return SecurityResult(SecurityBehavior.ASK, message, is_misparsing=misparsing)


def _deny(message: str) -> SecurityResult:
    return SecurityResult(SecurityBehavior.DENY, message)


def _passthrough(message: str = '') -> SecurityResult:
    return SecurityResult(SecurityBehavior.PASSTHROUGH, message)


# ---------------------------------------------------------------------------
# Command substitution patterns (from npm bashSecurity.ts)
# ---------------------------------------------------------------------------

COMMAND_SUBSTITUTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'<\('), 'process substitution <()'),
    (re.compile(r'>\('), 'process substitution >()'),
    (re.compile(r'=\('), 'Zsh process substitution =()'),
    (re.compile(r'(?:^|[\s;&|])=[a-zA-Z_]'), 'Zsh equals expansion (=cmd)'),
    (re.compile(r'\$\('), '$() command substitution'),
    (re.compile(r'\$\{'), '${} parameter substitution'),
    (re.compile(r'\$\['), '$[] legacy arithmetic expansion'),
    (re.compile(r'~\['), 'Zsh-style parameter expansion'),
    (re.compile(r'\(e:'), 'Zsh-style glob qualifiers'),
    (re.compile(r'\(\+'), 'Zsh glob qualifier with command execution'),
    (re.compile(r'\}\s*always\s*\{'), 'Zsh always block (try/always construct)'),
    (re.compile(r'<#'), 'PowerShell comment syntax'),
]

# Zsh dangerous commands that bypass security checks
ZSH_DANGEROUS_COMMANDS = frozenset({
    'zmodload', 'emulate',
    'sysopen', 'sysread', 'syswrite', 'sysseek',
    'zpty', 'ztcp', 'zsocket', 'mapfile',
    'zf_rm', 'zf_mv', 'zf_ln', 'zf_chmod', 'zf_chown',
    'zf_mkdir', 'zf_rmdir', 'zf_chgrp',
})

ZSH_PRECOMMAND_MODIFIERS = frozenset({
    'command', 'builtin', 'noglob', 'nocorrect',
})

# Control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F)
# Excludes tab (0x09), newline (0x0A), carriage return (0x0D)
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# Unicode whitespace that could cause parser differentials
UNICODE_WS_RE = re.compile(
    r'[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]'
)


# ---------------------------------------------------------------------------
# Destructive command patterns (from npm destructiveCommandWarning.ts)
# ---------------------------------------------------------------------------

DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Git - data loss / hard to reverse
    (re.compile(r'\bgit\s+reset\s+--hard\b'),
     'Note: may discard uncommitted changes'),
    (re.compile(r'\bgit\s+push\b[^;&|\n]*[ \t](--force|--force-with-lease|-f)\b'),
     'Note: may overwrite remote history'),
    (re.compile(r'\bgit\s+clean\b(?![^;&|\n]*(?:-[a-zA-Z]*n|--dry-run))[^;&|\n]*-[a-zA-Z]*f'),
     'Note: may permanently delete untracked files'),
    (re.compile(r'\bgit\s+checkout\s+(--\s+)?\.[ \t]*($|[;&|\n])'),
     'Note: may discard all working tree changes'),
    (re.compile(r'\bgit\s+restore\s+(--\s+)?\.[ \t]*($|[;&|\n])'),
     'Note: may discard all working tree changes'),
    (re.compile(r'\bgit\s+stash[ \t]+(drop|clear)\b'),
     'Note: may permanently remove stashed changes'),
    (re.compile(r'\bgit\s+branch\s+(-D[ \t]|--delete\s+--force|--force\s+--delete)\b'),
     'Note: may force-delete a branch'),
    # Git - safety bypass
    (re.compile(r'\bgit\s+(commit|push|merge)\b[^;&|\n]*--no-verify\b'),
     'Note: may skip safety hooks'),
    (re.compile(r'\bgit\s+commit\b[^;&|\n]*--amend\b'),
     'Note: may rewrite the last commit'),
    # File deletion
    (re.compile(r'(^|[;&|\n]\s*)rm\s+-[a-zA-Z]*[rR][a-zA-Z]*f|(^|[;&|\n]\s*)rm\s+-[a-zA-Z]*f[a-zA-Z]*[rR]'),
     'Note: may recursively force-remove files'),
    (re.compile(r'(^|[;&|\n]\s*)rm\s+-[a-zA-Z]*[rR]'),
     'Note: may recursively remove files'),
    (re.compile(r'(^|[;&|\n]\s*)rm\s+-[a-zA-Z]*f'),
     'Note: may force-remove files'),
    # Database
    (re.compile(r'\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b', re.IGNORECASE),
     'Note: may drop or truncate database objects'),
    (re.compile(r'\bDELETE\s+FROM\s+\w+[ \t]*(;|"|\'|\n|$)', re.IGNORECASE),
     'Note: may delete all rows from a database table'),
    # Infrastructure
    (re.compile(r'\bkubectl\s+delete\b'),
     'Note: may delete Kubernetes resources'),
    (re.compile(r'\bterraform\s+destroy\b'),
     'Note: may destroy Terraform infrastructure'),
]


# ---------------------------------------------------------------------------
# Command semantics (from npm commandSemantics.ts)
# ---------------------------------------------------------------------------

CommandSemantic = Callable[[int, str, str], tuple[bool, Optional[str]]]


def _default_semantic(exit_code: int, _stdout: str, _stderr: str) -> tuple[bool, Optional[str]]:
    return (exit_code != 0, f'Command failed with exit code {exit_code}' if exit_code != 0 else None)


def _grep_semantic(exit_code: int, _stdout: str, _stderr: str) -> tuple[bool, Optional[str]]:
    return (exit_code >= 2, 'No matches found' if exit_code == 1 else None)


def _find_semantic(exit_code: int, _stdout: str, _stderr: str) -> tuple[bool, Optional[str]]:
    return (exit_code >= 2, 'Some directories were inaccessible' if exit_code == 1 else None)


def _diff_semantic(exit_code: int, _stdout: str, _stderr: str) -> tuple[bool, Optional[str]]:
    return (exit_code >= 2, 'Files differ' if exit_code == 1 else None)


def _test_semantic(exit_code: int, _stdout: str, _stderr: str) -> tuple[bool, Optional[str]]:
    return (exit_code >= 2, 'Condition is false' if exit_code == 1 else None)


COMMAND_SEMANTICS: dict[str, CommandSemantic] = {
    'grep': _grep_semantic,
    'rg': _grep_semantic,
    'find': _find_semantic,
    'diff': _diff_semantic,
    'test': _test_semantic,
    '[': _test_semantic,
}


def interpret_command_result(
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> tuple[bool, Optional[str]]:
    """
    Interpret command result based on semantic rules.
    Returns (is_error, optional_message).
    """
    # Extract base command (last command in pipeline determines exit code)
    segments = split_command(command)
    last_segment = segments[-1] if segments else command
    base = last_segment.strip().split()[0] if last_segment.strip() else ''
    semantic = COMMAND_SEMANTICS.get(base, _default_semantic)
    return semantic(exit_code, stdout, stderr)


# ---------------------------------------------------------------------------
# Read-only command detection (from npm readOnlyValidation.ts)
# ---------------------------------------------------------------------------

READ_ONLY_COMMANDS = frozenset({
    # File viewing
    'cat', 'head', 'tail', 'less', 'more', 'bat', 'batcat',
    # Searching
    'grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack',
    # File listing
    'ls', 'll', 'la', 'dir', 'tree', 'exa', 'eza',
    # File info
    'stat', 'file', 'wc', 'du', 'df', 'readlink', 'realpath',
    'md5sum', 'sha256sum', 'sha1sum',
    # System info
    'uname', 'hostname', 'whoami', 'id', 'groups', 'date',
    'uptime', 'free', 'lsb_release', 'arch', 'nproc',
    # Process info
    'ps', 'top', 'htop', 'pgrep',
    # Printing
    'echo', 'printf', 'true', 'false',
    # Path tools
    'which', 'whereis', 'type', 'command', 'hash',
    'dirname', 'basename', 'pwd',
    # Text processing (non-destructive)
    'sort', 'uniq', 'cut', 'tr', 'fold', 'fmt', 'nl', 'rev',
    'column', 'paste', 'join', 'comm', 'tee',
    'awk', 'gawk', 'mawk',
    'sed',   # read-only only when no -i flag
    'diff', 'cmp', 'colordiff',
    # Encoding
    'base64', 'xxd', 'od', 'hexdump',
    # Find (read-only without -exec/-delete)
    'find', 'fd', 'fdfind', 'locate', 'mlocate',
    # Version/help
    'man', 'info', 'help',
    # Env inspection
    'env', 'printenv', 'set',
    # Network inspection (read-only)
    'ping', 'dig', 'nslookup', 'host', 'ifconfig', 'ip',
    # Git read-only
    'git',   # only certain subcommands are read-only
    # Python/Node read-only
    'python', 'python3', 'node',  # only with certain flags
})

GIT_READ_ONLY_SUBCOMMANDS = frozenset({
    'status', 'log', 'diff', 'show', 'branch', 'remote', 'tag',
    'describe', 'rev-parse', 'rev-list', 'ls-files', 'ls-tree',
    'ls-remote', 'cat-file', 'name-rev', 'shortlog', 'blame',
    'grep', 'reflog', 'stash list', 'config', 'version',
})

# Flags that make find dangerous (not read-only)
FIND_DANGEROUS_FLAGS = frozenset({
    '-exec', '-execdir', '-ok', '-okdir', '-delete',
})


def is_command_read_only(command: str) -> bool:
    """
    Check if a command is read-only (doesn't modify the filesystem).
    Returns True if the command is safe to auto-approve.
    """
    stripped = command.strip()
    if not stripped:
        return True

    parts = stripped.split()
    base_cmd = parts[0]

    if base_cmd not in READ_ONLY_COMMANDS:
        return False

    # Special handling for git
    if base_cmd == 'git':
        if len(parts) < 2:
            return True  # bare 'git' is safe
        subcmd = parts[1]
        return subcmd in GIT_READ_ONLY_SUBCOMMANDS

    # Special handling for sed (only read-only without -i)
    if base_cmd == 'sed':
        return '-i' not in parts and '--in-place' not in parts

    # Special handling for find (no -exec, -delete, etc.)
    if base_cmd in ('find', 'fd', 'fdfind'):
        return not any(flag in parts for flag in FIND_DANGEROUS_FLAGS)

    # Special handling for python/node (only with -c, --version, --help)
    if base_cmd in ('python', 'python3', 'node'):
        safe_flags = {'-c', '--version', '--help', '-V', '-h'}
        return len(parts) >= 2 and parts[1] in safe_flags

    return True


# ---------------------------------------------------------------------------
# Helper: Quote-aware content extraction (from npm bashSecurity.ts)
# ---------------------------------------------------------------------------

def extract_quoted_content(command: str) -> tuple[str, str, str]:
    """
    Extract content outside different quoting levels.
    Returns (with_double_quotes, fully_unquoted, unquoted_keep_quote_chars).

    - with_double_quotes: content outside single quotes (double-quoted content preserved)
    - fully_unquoted: content outside both single AND double quotes
    - unquoted_keep_quote_chars: like fully_unquoted but preserves ' and " chars
    """
    with_double_quotes = ''
    fully_unquoted = ''
    unquoted_keep_quote_chars = ''
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for i, char in enumerate(command):
        if escaped:
            escaped = False
            if not in_single_quote:
                with_double_quotes += char
            if not in_single_quote and not in_double_quote:
                fully_unquoted += char
                unquoted_keep_quote_chars += char
            continue

        if char == '\\' and not in_single_quote:
            escaped = True
            if not in_single_quote:
                with_double_quotes += char
            if not in_single_quote and not in_double_quote:
                fully_unquoted += char
                unquoted_keep_quote_chars += char
            continue

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            unquoted_keep_quote_chars += char
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            unquoted_keep_quote_chars += char
            continue

        if not in_single_quote:
            with_double_quotes += char
        if not in_single_quote and not in_double_quote:
            fully_unquoted += char
            unquoted_keep_quote_chars += char

    return with_double_quotes, fully_unquoted, unquoted_keep_quote_chars


def strip_safe_redirections(content: str) -> str:
    """Strip safe redirections (>/dev/null, 2>&1, </dev/null) from content."""
    result = content
    result = re.sub(r'\s+2\s*>&\s*1(?=\s|$)', '', result)
    result = re.sub(r'[012]?\s*>\s*/dev/null(?=\s|$)', '', result)
    result = re.sub(r'\s*<\s*/dev/null(?=\s|$)', '', result)
    return result


def has_unescaped_char(content: str, char: str) -> bool:
    """Check if content contains an unescaped occurrence of a single character."""
    assert len(char) == 1, 'has_unescaped_char only works with single characters'
    i = 0
    while i < len(content):
        if content[i] == '\\' and i + 1 < len(content):
            i += 2  # Skip backslash and escaped character
            continue
        if content[i] == char:
            return True
        i += 1
    return False


# ---------------------------------------------------------------------------
# Simple command splitter (for splitting on &&, ||, ;, |)
# ---------------------------------------------------------------------------

def split_command(command: str) -> list[str]:
    """
    Split a compound command on operators (&&, ||, ;, |) while respecting quotes.
    Returns list of individual command strings.
    """
    segments: list[str] = []
    current = ''
    in_single_quote = False
    in_double_quote = False
    escaped = False
    i = 0

    while i < len(command):
        c = command[i]

        if escaped:
            escaped = False
            current += c
            i += 1
            continue

        if c == '\\' and not in_single_quote:
            escaped = True
            current += c
            i += 1
            continue

        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current += c
            i += 1
            continue

        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current += c
            i += 1
            continue

        if in_single_quote or in_double_quote:
            current += c
            i += 1
            continue

        # Check for operators
        if c == ';':
            segments.append(current)
            current = ''
            i += 1
            continue

        if c == '|':
            if i + 1 < len(command) and command[i + 1] == '|':
                segments.append(current)
                current = ''
                i += 2
                continue
            else:
                segments.append(current)
                current = ''
                i += 1
                continue

        if c == '&':
            if i + 1 < len(command) and command[i + 1] == '&':
                segments.append(current)
                current = ''
                i += 2
                continue
            else:
                current += c
                i += 1
                continue

        current += c
        i += 1

    if current:
        segments.append(current)

    return [s.strip() for s in segments if s.strip()]


# ---------------------------------------------------------------------------
# Validation context (matching npm ValidationContext)
# ---------------------------------------------------------------------------

@dataclass
class ValidationContext:
    """Context passed to each validator function."""
    original_command: str
    base_command: str
    unquoted_content: str          # Outside single quotes
    fully_unquoted_content: str    # Outside all quotes, with safe redirections stripped
    fully_unquoted_pre_strip: str  # Outside all quotes, before stripping redirections
    unquoted_keep_quote_chars: str # Like fully_unquoted but preserves quote characters


# ---------------------------------------------------------------------------
# Validators (ported from npm bashSecurity.ts)
# ---------------------------------------------------------------------------

def validate_empty(ctx: ValidationContext) -> SecurityResult:
    """Allow empty commands."""
    if not ctx.original_command.strip():
        return _allow('Empty command is safe')
    return _passthrough('Command is not empty')


def validate_control_characters(ctx: ValidationContext) -> SecurityResult:
    """Block commands with non-printable control characters."""
    if CONTROL_CHAR_RE.search(ctx.original_command):
        return _ask(
            'Command contains non-printable control characters that could bypass security checks',
            misparsing=True,
        )
    return _passthrough()


def validate_incomplete_commands(ctx: ValidationContext) -> SecurityResult:
    """Detect incomplete command fragments."""
    original = ctx.original_command
    trimmed = original.strip()

    if re.match(r'^\s*\t', original):
        return _ask('Command appears to be an incomplete fragment (starts with tab)',
                     misparsing=True)

    if trimmed.startswith('-'):
        return _ask('Command appears to be an incomplete fragment (starts with flags)',
                     misparsing=True)

    if re.match(r'^\s*(&&|\|\||;|>>?|<)', original):
        return _ask('Command appears to be a continuation line (starts with operator)',
                     misparsing=True)

    return _passthrough()


def validate_git_commit(ctx: ValidationContext) -> SecurityResult:
    """
    Early-allow simple git commit -m '...' commands.
    Block git commit messages with command substitution.
    """
    if ctx.base_command != 'git' or not re.match(r'^git\s+commit\s+', ctx.original_command):
        return _passthrough()

    if '\\' in ctx.original_command:
        return _passthrough('Git commit contains backslash, needs full validation')

    msg_match = re.match(
        r'^git[ \t]+commit[ \t]+[^;&|`$<>()\n\r]*?-m[ \t]+(["\'])([\s\S]*?)\1(.*)$',
        ctx.original_command,
    )

    if msg_match:
        quote, message_content, remainder = msg_match.group(1), msg_match.group(2), msg_match.group(3)

        if quote == '"' and message_content and re.search(r'\$\(|`|\$\{', message_content):
            return _ask('Git commit message contains command substitution patterns',
                        misparsing=True)

        if remainder and re.search(r'[;|&()`]|\$\(|\$\{', remainder):
            return _passthrough('Git commit remainder contains shell metacharacters')

        if remainder:
            # Check for unquoted redirect operators
            unquoted = ''
            in_sq = False
            in_dq = False
            for c in remainder:
                if c == "'" and not in_dq:
                    in_sq = not in_sq
                    continue
                if c == '"' and not in_sq:
                    in_dq = not in_dq
                    continue
                if not in_sq and not in_dq:
                    unquoted += c
            if re.search(r'[<>]', unquoted):
                return _passthrough('Git commit remainder contains unquoted redirect operator')

        if message_content and message_content.startswith('-'):
            return _ask('Command contains quoted characters in flag names',
                        misparsing=True)

        return _allow('Git commit with simple quoted message is allowed')

    return _passthrough('Git commit needs validation')


def validate_jq_command(ctx: ValidationContext) -> SecurityResult:
    """Block dangerous jq patterns (system(), -f, --from-file, etc.)."""
    if ctx.base_command != 'jq':
        return _passthrough()

    if re.search(r'\bsystem\s*\(', ctx.original_command):
        return _ask('jq command contains system() function which executes arbitrary commands')

    after_jq = ctx.original_command[3:].strip() if len(ctx.original_command) > 3 else ''
    if re.search(r'(?:^|\s)(?:-f\b|--from-file|--rawfile|--slurpfile|-L\b|--library-path)', after_jq):
        return _ask('jq command contains dangerous flags that could read arbitrary files')

    return _passthrough()


def validate_obfuscated_flags(ctx: ValidationContext) -> SecurityResult:
    """Detect shell quoting bypass patterns used to circumvent security checks."""
    original = ctx.original_command
    base = ctx.base_command

    # Echo is safe for obfuscated flags without shell operators
    if base == 'echo' and not re.search(r'[|&;]', original):
        return _passthrough()

    # Block ANSI-C quoting ($'...')
    if re.search(r"\$'[^']*'", original):
        return _ask('Command contains ANSI-C quoting which can hide characters')

    # Block locale quoting ($"...")
    if re.search(r'\$"[^"]*"', original):
        return _ask('Command contains locale quoting which can hide characters')

    # Block empty ANSI-C or locale quotes followed by dash
    if re.search(r"""\$['"]{2}\s*-""", original):
        return _ask('Command contains empty special quotes before dash (potential bypass)')

    # Block sequence of empty quotes followed by dash
    if re.search(r"""(?:^|\s)(?:''|""){1,}\s*-""", original):
        return _ask('Command contains empty quotes before dash (potential bypass)')

    # Block homogeneous empty quote pairs adjacent to quoted dash
    if re.search(r"""(?:""|''){1,}['"][-]""", original):
        return _ask('Command contains empty quote pair adjacent to quoted dash')

    # Block 3+ consecutive quotes at word start
    if re.search(r"""(?:^|\s)['\"]{3,}""", original):
        return _ask('Command contains consecutive quote characters at word start')

    # Track quote state and detect quoted flags
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for i in range(len(original) - 1):
        c = original[i]
        next_c = original[i + 1]

        if escaped:
            escaped = False
            continue

        if c == '\\' and not in_single_quote:
            escaped = True
            continue

        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue

        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue

        if in_single_quote or in_double_quote:
            continue

        # Look for whitespace followed by quote that contains a dash (obfuscated flag)
        if c and c in ' \t\n' and next_c in "'\"`":
            quote_char = next_c
            j = i + 2
            inside_quote = ''
            while j < len(original) and original[j] != quote_char:
                inside_quote += original[j]
                j += 1

            if j < len(original) and original[j] == quote_char:
                has_flag_chars_inside = bool(re.match(r'^-+[a-zA-Z0-9$`]', inside_quote))
                char_after = original[j + 1] if j + 1 < len(original) else ''
                has_flag_continuing = (
                    bool(re.match(r'^-+$', inside_quote)) and
                    bool(char_after) and
                    bool(re.match(r'[a-zA-Z0-9\\${`\-]', char_after))
                )

                if has_flag_chars_inside or has_flag_continuing:
                    return _ask('Command contains quoted characters in flag names')

        # Look for whitespace followed by dash with quotes mixed in
        if c and c in ' \t\n' and next_c == '-':
            j = i + 1
            flag_content = ''
            while j < len(original):
                fc = original[j]
                if fc in ' \t\n\r=':
                    break
                if fc in "'\"" and base == 'cut' and flag_content == '-d':
                    break
                flag_content += fc
                j += 1

            if '"' in flag_content or "'" in flag_content:
                return _ask('Command contains quoted characters in flag names')

    return _passthrough()


def validate_shell_metacharacters(ctx: ValidationContext) -> SecurityResult:
    """Detect shell metacharacters in quoted arguments."""
    unquoted = ctx.unquoted_content

    if re.search(r'(?:^|\s)["\'][^"\']*[;&][^"\']*["\'](?:\s|$)', unquoted):
        return _ask('Command contains shell metacharacters (;, |, or &) in arguments')

    # Glob patterns with metacharacters
    for pattern in [
        r'-name\s+["\'][^"\']*[;|&][^"\']*["\']',
        r'-path\s+["\'][^"\']*[;|&][^"\']*["\']',
        r'-iname\s+["\'][^"\']*[;|&][^"\']*["\']',
    ]:
        if re.search(pattern, unquoted):
            return _ask('Command contains shell metacharacters (;, |, or &) in arguments')

    return _passthrough()


def validate_dangerous_variables(ctx: ValidationContext) -> SecurityResult:
    """Detect variables in dangerous contexts (redirections or pipes)."""
    fully_unquoted = ctx.fully_unquoted_content

    if (re.search(r'[<>|]\s*\$[A-Za-z_]', fully_unquoted) or
            re.search(r'\$[A-Za-z_][A-Za-z0-9_]*\s*[|<>]', fully_unquoted)):
        return _ask('Command contains variables in dangerous contexts (redirections or pipes)')

    return _passthrough()


def validate_dangerous_patterns(ctx: ValidationContext) -> SecurityResult:
    """Detect backticks, $(), ${}, and other command substitution patterns."""
    unquoted = ctx.unquoted_content

    # Check for unescaped backticks
    if has_unescaped_char(unquoted, '`'):
        return _ask('Command contains backticks (`) for command substitution')

    # Other command substitution patterns
    for pattern, desc in COMMAND_SUBSTITUTION_PATTERNS:
        if pattern.search(unquoted):
            return _ask(f'Command contains {desc}')

    return _passthrough()


def validate_redirections(ctx: ValidationContext) -> SecurityResult:
    """Detect input/output redirection."""
    fully_unquoted = ctx.fully_unquoted_content

    if '<' in fully_unquoted:
        return _ask('Command contains input redirection (<) which could read sensitive files')

    if '>' in fully_unquoted:
        return _ask('Command contains output redirection (>) which could write to arbitrary files')

    return _passthrough()


def validate_newlines(ctx: ValidationContext) -> SecurityResult:
    """Detect newlines that could separate multiple commands."""
    fully_unquoted = ctx.fully_unquoted_pre_strip

    if not re.search(r'[\n\r]', fully_unquoted):
        return _passthrough()

    # Check for newline followed by non-whitespace (potential second command)
    # Allow backslash-newline line continuations at word boundaries
    if re.search(r'(?<![\s]\\)[\n\r]\s*\S', fully_unquoted):
        return _ask('Command contains newlines that could separate multiple commands')

    return _passthrough()


def validate_carriage_return(ctx: ValidationContext) -> SecurityResult:
    """
    Detect carriage returns that cause parser differentials.
    CR is a misparsing concern because shell-quote treats it as a word
    separator but bash does not.
    """
    original = ctx.original_command
    if '\r' not in original:
        return _passthrough()

    # Check if CR appears outside double quotes
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for c in original:
        if escaped:
            escaped = False
            continue
        if c == '\\' and not in_single_quote:
            escaped = True
            continue
        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue
        if c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue
        if c == '\r' and not in_double_quote:
            return _ask(
                'Command contains carriage return (\\r) which may cause parser differentials',
                misparsing=True,
            )

    return _passthrough()


def validate_ifs_injection(ctx: ValidationContext) -> SecurityResult:
    """Detect IFS variable usage which could bypass security validation."""
    if re.search(r'\$IFS|\$\{[^}]*IFS', ctx.original_command):
        return _ask('Command contains IFS variable usage which could bypass security validation')
    return _passthrough()


def validate_proc_environ_access(ctx: ValidationContext) -> SecurityResult:
    """Detect access to /proc/*/environ which could expose sensitive env vars."""
    if re.search(r'/proc/.*/environ', ctx.original_command):
        return _ask('Command accesses /proc/*/environ which could expose sensitive environment variables')
    return _passthrough()


def validate_backslash_escaped_whitespace(ctx: ValidationContext) -> SecurityResult:
    """Detect backslash-escaped whitespace that could alter command parsing."""
    if _has_backslash_escaped_whitespace(ctx.original_command):
        return _ask(
            'Command contains backslash-escaped whitespace that could alter command parsing',
            misparsing=True,
        )
    return _passthrough()


def _has_backslash_escaped_whitespace(command: str) -> bool:
    """Check if command has backslash-escaped whitespace outside quotes."""
    in_single_quote = False
    in_double_quote = False
    i = 0
    while i < len(command):
        c = command[i]

        if c == '\\' and not in_single_quote:
            if i + 1 < len(command):
                next_c = command[i + 1]
                if not in_double_quote and next_c in ' \t':
                    return True
            i += 2
            continue

        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        i += 1
    return False


SHELL_OPERATORS = frozenset(';|&<>')


def validate_backslash_escaped_operators(ctx: ValidationContext) -> SecurityResult:
    """
    Detect backslash before shell operators which can hide command structure.
    E.g., `cat safe.txt \\; echo ~/.ssh/id_rsa`
    """
    if _has_backslash_escaped_operator(ctx.original_command):
        return _ask(
            'Command contains a backslash before a shell operator (;, |, &, <, >) '
            'which can hide command structure',
            misparsing=True,
        )
    return _passthrough()


def _has_backslash_escaped_operator(command: str) -> bool:
    """Check if command has backslash-escaped shell operator outside quotes."""
    in_single_quote = False
    in_double_quote = False
    i = 0
    while i < len(command):
        c = command[i]

        if c == '\\' and not in_single_quote:
            if not in_double_quote and i + 1 < len(command):
                next_c = command[i + 1]
                if next_c in SHELL_OPERATORS:
                    return True
            i += 2
            continue

        if c == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif c == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        i += 1
    return False


def validate_brace_expansion(ctx: ValidationContext) -> SecurityResult:
    """
    Detect unquoted brace expansion syntax ({a,b} or {1..5}).
    Brace expansion can alter command parsing and inject arguments.
    """
    content = ctx.fully_unquoted_pre_strip

    # Count unescaped braces
    open_braces = 0
    close_braces = 0
    for i, c in enumerate(content):
        if c == '{' and not _is_escaped_at_position(content, i):
            open_braces += 1
        elif c == '}' and not _is_escaped_at_position(content, i):
            close_braces += 1

    # Excess closing braces indicate obfuscation
    if open_braces > 0 and close_braces > open_braces:
        return _ask('Command has excess closing braces (possible brace expansion obfuscation)')

    # Check for quoted brace inside brace context
    if open_braces > 0 and re.search(r"""['"][{}]['"]""", ctx.original_command):
        return _ask('Command contains quoted brace character inside brace context')

    # Scan for actual brace expansion patterns ({a,b} or {a..b})
    i = 0
    while i < len(content):
        if content[i] != '{' or _is_escaped_at_position(content, i):
            i += 1
            continue

        # Find matching closing brace with nesting
        depth = 1
        matching_close = -1
        j = i + 1
        while j < len(content):
            if content[j] == '{' and not _is_escaped_at_position(content, j):
                depth += 1
            elif content[j] == '}' and not _is_escaped_at_position(content, j):
                depth -= 1
                if depth == 0:
                    matching_close = j
                    break
            j += 1

        if matching_close == -1:
            i += 1
            continue

        # Check for comma or .. at outermost level
        inner_depth = 0
        for k in range(i + 1, matching_close):
            ch = content[k]
            if ch == '{' and not _is_escaped_at_position(content, k):
                inner_depth += 1
            elif ch == '}' and not _is_escaped_at_position(content, k):
                inner_depth -= 1
            elif inner_depth == 0:
                if ch == ',' or (ch == '.' and k + 1 < matching_close and content[k + 1] == '.'):
                    return _ask('Command contains brace expansion that could alter command parsing')

        i += 1

    return _passthrough()


def _is_escaped_at_position(content: str, pos: int) -> bool:
    """Check if character at position is escaped by counting preceding backslashes."""
    count = 0
    i = pos - 1
    while i >= 0 and content[i] == '\\':
        count += 1
        i -= 1
    return count % 2 == 1


def validate_unicode_whitespace(ctx: ValidationContext) -> SecurityResult:
    """Detect Unicode whitespace that could cause parser differentials."""
    if UNICODE_WS_RE.search(ctx.original_command):
        return _ask('Command contains Unicode whitespace characters that could cause parsing inconsistencies')
    return _passthrough()


def validate_mid_word_hash(ctx: ValidationContext) -> SecurityResult:
    """
    Detect mid-word # which is parsed differently by different shell parsers.
    In bash, mid-word # is literal; in some parsers it starts a comment.
    """
    text = ctx.unquoted_keep_quote_chars
    # Match # preceded by non-whitespace, excluding ${#
    if re.search(r'\S(?<!\$\{)#', text):
        return _ask('Command contains mid-word # which may be parsed differently by different tools')
    return _passthrough()


def validate_comment_quote_desync(ctx: ValidationContext) -> SecurityResult:
    """
    Detect quote characters inside # comments that could desync quote trackers.
    A ' or " after an unquoted # could confuse downstream processing.
    """
    original = ctx.original_command
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for i, char in enumerate(original):
        if escaped:
            escaped = False
            continue
        if in_single_quote:
            if char == "'":
                in_single_quote = False
            continue
        if char == '\\':
            escaped = True
            continue
        if in_double_quote:
            if char == '"':
                in_double_quote = False
            continue
        if char == "'":
            in_single_quote = True
            continue
        if char == '"':
            in_double_quote = True
            continue

        if char == '#':
            line_end = original.find('\n', i)
            comment_text = original[i + 1: line_end if line_end != -1 else len(original)]
            if re.search(r"""['"]""", comment_text):
                return _ask(
                    'Command contains quote characters inside a # comment '
                    'which can desync quote tracking',
                    misparsing=True,
                )
            if line_end == -1:
                break
            # Skip to end of line
            continue

    return _passthrough()


def validate_quoted_newline(ctx: ValidationContext) -> SecurityResult:
    """
    Detect newlines inside quoted strings where the next line starts with #.
    This can hide arguments from line-based permission checks.
    """
    original = ctx.original_command
    if '\n' not in original or '#' not in original:
        return _passthrough()

    in_single_quote = False
    in_double_quote = False
    escaped = False

    for i, char in enumerate(original):
        if escaped:
            escaped = False
            continue
        if char == '\\' and not in_single_quote:
            escaped = True
            continue
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue

        if char == '\n' and (in_single_quote or in_double_quote):
            line_start = i + 1
            next_newline = original.find('\n', line_start)
            line_end = next_newline if next_newline != -1 else len(original)
            next_line = original[line_start:line_end]
            if next_line.strip().startswith('#'):
                return _ask(
                    'Command contains a quoted newline followed by a #-prefixed line, '
                    'which can hide arguments from permission checks',
                    misparsing=True,
                )

    return _passthrough()


def validate_zsh_dangerous_commands(ctx: ValidationContext) -> SecurityResult:
    """Detect Zsh-specific dangerous commands."""
    original = ctx.original_command
    trimmed = original.strip()
    tokens = trimmed.split()

    base_cmd = ''
    for token in tokens:
        if re.match(r'^[A-Za-z_]\w*=', token):
            continue
        if token in ZSH_PRECOMMAND_MODIFIERS:
            continue
        base_cmd = token
        break

    if base_cmd in ZSH_DANGEROUS_COMMANDS:
        return _ask(f"Command uses Zsh-specific '{base_cmd}' which can bypass security checks")

    # Check for fc -e (arbitrary command execution via editor)
    if base_cmd == 'fc' and re.search(r'\s-\S*e', trimmed):
        return _ask("Command uses 'fc -e' which can execute arbitrary commands via editor")

    return _passthrough()


# ---------------------------------------------------------------------------
# Main security check entry point
# ---------------------------------------------------------------------------

# Validators that don't indicate misparsing concerns
_NON_MISPARSING_VALIDATORS = frozenset({
    'validate_newlines',
    'validate_redirections',
})


def bash_command_is_safe(command: str) -> SecurityResult:
    """
    Main entry point: check if a bash command is safe to execute.

    Returns a SecurityResult with behavior:
    - ALLOW: Command is safe, auto-approve
    - ASK: Command needs user confirmation
    - DENY: Command is blocked
    - PASSTHROUGH: All checks passed, proceed with normal permission flow
    """
    # Block control characters first
    result = validate_control_characters(ValidationContext(
        original_command=command, base_command='',
        unquoted_content='', fully_unquoted_content='',
        fully_unquoted_pre_strip='', unquoted_keep_quote_chars='',
    ))
    if result.behavior != SecurityBehavior.PASSTHROUGH:
        return result

    # Build validation context
    base_command = command.split()[0] if command.strip() else ''
    with_double_quotes, fully_unquoted, unquoted_keep_quote_chars = extract_quoted_content(command)

    ctx = ValidationContext(
        original_command=command,
        base_command=base_command,
        unquoted_content=with_double_quotes,
        fully_unquoted_content=strip_safe_redirections(fully_unquoted),
        fully_unquoted_pre_strip=fully_unquoted,
        unquoted_keep_quote_chars=unquoted_keep_quote_chars,
    )

    # Early validators (can allow or block)
    early_validators = [
        validate_empty,
        validate_incomplete_commands,
        validate_git_commit,
    ]

    for validator in early_validators:
        result = validator(ctx)
        if result.behavior == SecurityBehavior.ALLOW:
            return _passthrough(result.message)
        if result.behavior != SecurityBehavior.PASSTHROUGH:
            return result

    # Main validators
    validators: list[tuple[str, Callable[[ValidationContext], SecurityResult]]] = [
        ('validate_jq_command', validate_jq_command),
        ('validate_obfuscated_flags', validate_obfuscated_flags),
        ('validate_shell_metacharacters', validate_shell_metacharacters),
        ('validate_dangerous_variables', validate_dangerous_variables),
        ('validate_comment_quote_desync', validate_comment_quote_desync),
        ('validate_quoted_newline', validate_quoted_newline),
        ('validate_carriage_return', validate_carriage_return),
        ('validate_newlines', validate_newlines),
        ('validate_ifs_injection', validate_ifs_injection),
        ('validate_proc_environ_access', validate_proc_environ_access),
        ('validate_dangerous_patterns', validate_dangerous_patterns),
        ('validate_redirections', validate_redirections),
        ('validate_backslash_escaped_whitespace', validate_backslash_escaped_whitespace),
        ('validate_backslash_escaped_operators', validate_backslash_escaped_operators),
        ('validate_unicode_whitespace', validate_unicode_whitespace),
        ('validate_mid_word_hash', validate_mid_word_hash),
        ('validate_brace_expansion', validate_brace_expansion),
        ('validate_zsh_dangerous_commands', validate_zsh_dangerous_commands),
    ]

    # Defer non-misparsing results to let misparsing validators run
    deferred_non_misparsing: Optional[SecurityResult] = None

    for name, validator in validators:
        result = validator(ctx)
        if result.behavior == SecurityBehavior.ASK:
            if name in _NON_MISPARSING_VALIDATORS:
                if deferred_non_misparsing is None:
                    deferred_non_misparsing = result
                continue
            return SecurityResult(
                SecurityBehavior.ASK, result.message, is_misparsing=True,
            )

    if deferred_non_misparsing is not None:
        return deferred_non_misparsing

    return _passthrough('Command passed all security checks')


# ---------------------------------------------------------------------------
# Destructive command warning (informational, not blocking)
# ---------------------------------------------------------------------------

def get_destructive_command_warning(command: str) -> Optional[str]:
    """
    Check if a command matches known destructive patterns.
    Returns a warning string or None.
    """
    for pattern, warning in DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            return warning
    return None


# ---------------------------------------------------------------------------
# Enhanced shell security check (replaces basic _ensure_shell_allowed)
# ---------------------------------------------------------------------------

def check_shell_security(
    command: str,
    *,
    allow_shell: bool = True,
    allow_destructive: bool = False,
) -> tuple[bool, str]:
    """
    Comprehensive shell security check. Returns (allowed, message).

    This is the main integration point for the agent's tool execution.
    It replaces the basic destructive pattern matching with full security validation.

    Args:
        command: The shell command to validate
        allow_shell: Whether shell commands are enabled at all
        allow_destructive: Whether destructive commands are allowed

    Returns:
        (True, '') if command is allowed
        (False, reason) if command should be blocked
    """
    if not allow_shell:
        return (False, 'Shell commands are disabled. Re-run with --allow-shell to enable bash.')

    # Run full security validation
    result = bash_command_is_safe(command)

    if result.behavior == SecurityBehavior.DENY:
        return (False, result.message)

    if result.behavior == SecurityBehavior.ASK:
        # For misparsing concerns, always block
        if result.is_misparsing:
            return (False, f'Security check: {result.message}')

    # Check destructive patterns if not allowed
    if not allow_destructive:
        warning = get_destructive_command_warning(command)
        if warning:
            return (False, f'Potentially destructive command blocked: {warning}. '
                          'Re-run with --unsafe to allow it.')

    return (True, '')
