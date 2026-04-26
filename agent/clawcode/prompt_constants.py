"""Prompt constants ported from npm src/constants/.

Covers: product metadata, API limits, tool limits, spinner verbs,
turn-completion verbs, figures/symbols, XML tags, message constants,
date utilities, system prompt section caching, output-style configs,
and cyber-risk instruction.

npm sources:
  src/constants/product.ts
  src/constants/apiLimits.ts
  src/constants/toolLimits.ts
  src/constants/spinnerVerbs.ts
  src/constants/turnCompletionVerbs.ts
  src/constants/figures.ts
  src/constants/xml.ts
  src/constants/messages.ts
  src/constants/common.ts
  src/constants/systemPromptSections.ts
  src/constants/outputStyles.ts
  src/constants/cyberRiskInstruction.ts
  src/constants/system.ts
  src/constants/prompts.ts (selected sections)
"""

from __future__ import annotations

import os
import platform
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Product metadata  (product.ts)
# ---------------------------------------------------------------------------

PRODUCT_URL = "https://claude.com/claude-code"
CLAUDE_AI_BASE_URL = "https://claude.ai"

# ---------------------------------------------------------------------------
# System prompt prefixes  (system.ts)
# ---------------------------------------------------------------------------

DEFAULT_SYSPROMPT_PREFIX = (
    "You are Claude Code, Anthropic's official CLI for Claude."
)
AGENT_SDK_CLAUDE_CODE_PRESET_PREFIX = (
    "You are Claude Code, Anthropic's official CLI for Claude, "
    "running within the Claude Agent SDK."
)
AGENT_SDK_PREFIX = (
    "You are a Claude agent, built on Anthropic's Claude Agent SDK."
)
CLI_SYSPROMPT_PREFIXES = frozenset(
    {
        DEFAULT_SYSPROMPT_PREFIX,
        AGENT_SDK_CLAUDE_CODE_PRESET_PREFIX,
        AGENT_SDK_PREFIX,
    }
)

# ---------------------------------------------------------------------------
# Cyber-risk instruction  (cyberRiskInstruction.ts)
# ---------------------------------------------------------------------------

CYBER_RISK_INSTRUCTION = (
    "IMPORTANT: Assist with authorized security testing, defensive security, "
    "CTF challenges, and educational contexts. Refuse requests for destructive "
    "techniques, DoS attacks, mass targeting, supply chain compromise, or "
    "detection evasion for malicious purposes. Dual-use security tools (C2 "
    "frameworks, credential testing, exploit development) require clear "
    "authorization context: pentesting engagements, CTF competitions, security "
    "research, or defensive use cases."
)

# ---------------------------------------------------------------------------
# API limits  (apiLimits.ts)
# ---------------------------------------------------------------------------

# Image limits
API_IMAGE_MAX_BASE64_SIZE = 5 * 1024 * 1024          # 5 MB base64
IMAGE_TARGET_RAW_SIZE = (API_IMAGE_MAX_BASE64_SIZE * 3) // 4  # ~3.75 MB
IMAGE_MAX_WIDTH = 2000
IMAGE_MAX_HEIGHT = 2000

# PDF limits
PDF_TARGET_RAW_SIZE = 20 * 1024 * 1024               # 20 MB
API_PDF_MAX_PAGES = 100
PDF_EXTRACT_SIZE_THRESHOLD = 3 * 1024 * 1024          # 3 MB
PDF_MAX_EXTRACT_SIZE = 100 * 1024 * 1024               # 100 MB
PDF_MAX_PAGES_PER_READ = 20
PDF_AT_MENTION_INLINE_THRESHOLD = 10

# Media limits
API_MAX_MEDIA_PER_REQUEST = 100

# ---------------------------------------------------------------------------
# Tool limits  (toolLimits.ts)
# ---------------------------------------------------------------------------

DEFAULT_MAX_RESULT_SIZE_CHARS = 50_000
MAX_TOOL_RESULT_TOKENS = 100_000
BYTES_PER_TOKEN = 4
MAX_TOOL_RESULT_BYTES = MAX_TOOL_RESULT_TOKENS * BYTES_PER_TOKEN  # 400 KB
MAX_TOOL_RESULTS_PER_MESSAGE_CHARS = 200_000
TOOL_SUMMARY_MAX_LENGTH = 50

# ---------------------------------------------------------------------------
# Spinner verbs  (spinnerVerbs.ts)  —  204 whimsical gerunds
# ---------------------------------------------------------------------------

SPINNER_VERBS: tuple[str, ...] = (
    "Accomplishing",
    "Actioning",
    "Actualizing",
    "Architecting",
    "Baking",
    "Beaming",
    "Beboppin'",
    "Befuddling",
    "Billowing",
    "Blanching",
    "Bloviating",
    "Boogieing",
    "Boondoggling",
    "Booping",
    "Bootstrapping",
    "Brewing",
    "Bunning",
    "Burrowing",
    "Calculating",
    "Canoodling",
    "Caramelizing",
    "Cascading",
    "Catapulting",
    "Cerebrating",
    "Channeling",
    "Channelling",
    "Choreographing",
    "Churning",
    "Clauding",
    "Coalescing",
    "Cogitating",
    "Combobulating",
    "Composing",
    "Computing",
    "Concocting",
    "Considering",
    "Contemplating",
    "Cooking",
    "Crafting",
    "Creating",
    "Crunching",
    "Crystallizing",
    "Cultivating",
    "Deciphering",
    "Deliberating",
    "Determining",
    "Dilly-dallying",
    "Discombobulating",
    "Doing",
    "Doodling",
    "Drizzling",
    "Ebbing",
    "Effecting",
    "Elucidating",
    "Embellishing",
    "Enchanting",
    "Envisioning",
    "Evaporating",
    "Fermenting",
    "Fiddle-faddling",
    "Finagling",
    "Flambéing",
    "Flibbertigibbeting",
    "Flowing",
    "Flummoxing",
    "Fluttering",
    "Forging",
    "Forming",
    "Frolicking",
    "Frosting",
    "Gallivanting",
    "Galloping",
    "Garnishing",
    "Generating",
    "Gesticulating",
    "Germinating",
    "Gitifying",
    "Grooving",
    "Gusting",
    "Harmonizing",
    "Hashing",
    "Hatching",
    "Herding",
    "Honking",
    "Hullaballooing",
    "Hyperspacing",
    "Ideating",
    "Imagining",
    "Improvising",
    "Incubating",
    "Inferring",
    "Infusing",
    "Ionizing",
    "Jitterbugging",
    "Julienning",
    "Kneading",
    "Leavening",
    "Levitating",
    "Lollygagging",
    "Manifesting",
    "Marinating",
    "Meandering",
    "Metamorphosing",
    "Misting",
    "Moonwalking",
    "Moseying",
    "Mulling",
    "Mustering",
    "Musing",
    "Nebulizing",
    "Nesting",
    "Newspapering",
    "Noodling",
    "Nucleating",
    "Orbiting",
    "Orchestrating",
    "Osmosing",
    "Perambulating",
    "Percolating",
    "Perusing",
    "Philosophising",
    "Photosynthesizing",
    "Pollinating",
    "Pondering",
    "Pontificating",
    "Pouncing",
    "Precipitating",
    "Prestidigitating",
    "Processing",
    "Proofing",
    "Propagating",
    "Puttering",
    "Puzzling",
    "Quantumizing",
    "Razzle-dazzling",
    "Razzmatazzing",
    "Recombobulating",
    "Reticulating",
    "Roosting",
    "Ruminating",
    "Sautéing",
    "Scampering",
    "Schlepping",
    "Scurrying",
    "Seasoning",
    "Shenaniganing",
    "Shimmying",
    "Simmering",
    "Skedaddling",
    "Sketching",
    "Slithering",
    "Smooshing",
    "Sock-hopping",
    "Spelunking",
    "Spinning",
    "Sprouting",
    "Stewing",
    "Sublimating",
    "Swirling",
    "Swooping",
    "Symbioting",
    "Synthesizing",
    "Tempering",
    "Thinking",
    "Thundering",
    "Tinkering",
    "Tomfoolering",
    "Topsy-turvying",
    "Transfiguring",
    "Transmuting",
    "Twisting",
    "Undulating",
    "Unfurling",
    "Unravelling",
    "Vibing",
    "Waddling",
    "Wandering",
    "Warping",
    "Whatchamacalliting",
    "Whirlpooling",
    "Whirring",
    "Whisking",
    "Wibbling",
    "Working",
    "Wrangling",
    "Zesting",
    "Zigzagging",
)

# ---------------------------------------------------------------------------
# Turn-completion verbs  (turnCompletionVerbs.ts)  —  8 past-tense verbs
# ---------------------------------------------------------------------------

TURN_COMPLETION_VERBS: tuple[str, ...] = (
    "Baked",
    "Brewed",
    "Churned",
    "Cogitated",
    "Cooked",
    "Crunched",
    "Sautéed",
    "Worked",
)

# ---------------------------------------------------------------------------
# Figures / UI symbols  (figures.ts)
# ---------------------------------------------------------------------------

BLACK_CIRCLE = "\u23fa" if platform.system() == "Darwin" else "\u25cf"  # ⏺ / ●
BULLET_OPERATOR = "\u2219"          # ∙
TEARDROP_ASTERISK = "\u273b"        # ✻
UP_ARROW = "\u2191"                 # ↑
DOWN_ARROW = "\u2193"               # ↓
LIGHTNING_BOLT = "\u21af"           # ↯
EFFORT_LOW = "\u25cb"               # ○
EFFORT_MEDIUM = "\u25d0"            # ◐
EFFORT_HIGH = "\u25cf"              # ●
EFFORT_MAX = "\u25c9"               # ◉

PLAY_ICON = "\u25b6"               # ▶
PAUSE_ICON = "\u23f8"              # ⏸

REFRESH_ARROW = "\u21bb"           # ↻
CHANNEL_ARROW = "\u2190"           # ←
INJECTED_ARROW = "\u2192"          # →
FORK_GLYPH = "\u2442"             # ⑂

DIAMOND_OPEN = "\u25c7"            # ◇
DIAMOND_FILLED = "\u25c6"          # ◆
REFERENCE_MARK = "\u203b"          # ※

FLAG_ICON = "\u2691"               # ⚑
BLOCKQUOTE_BAR = "\u258e"          # ▎
HEAVY_HORIZONTAL = "\u2501"        # ━

BRIDGE_SPINNER_FRAMES: tuple[str, ...] = (
    "\u00b7|\u00b7",
    "\u00b7/\u00b7",
    "\u00b7\u2014\u00b7",
    "\u00b7\\\u00b7",
)
BRIDGE_READY_INDICATOR = "\u00b7\u2714\ufe0e\u00b7"
BRIDGE_FAILED_INDICATOR = "\u00d7"

# ---------------------------------------------------------------------------
# XML tag constants  (xml.ts)
# ---------------------------------------------------------------------------

COMMAND_NAME_TAG = "command-name"
COMMAND_MESSAGE_TAG = "command-message"
COMMAND_ARGS_TAG = "command-args"

BASH_INPUT_TAG = "bash-input"
BASH_STDOUT_TAG = "bash-stdout"
BASH_STDERR_TAG = "bash-stderr"
LOCAL_COMMAND_STDOUT_TAG = "local-command-stdout"
LOCAL_COMMAND_STDERR_TAG = "local-command-stderr"
LOCAL_COMMAND_CAVEAT_TAG = "local-command-caveat"

TERMINAL_OUTPUT_TAGS: tuple[str, ...] = (
    BASH_INPUT_TAG,
    BASH_STDOUT_TAG,
    BASH_STDERR_TAG,
    LOCAL_COMMAND_STDOUT_TAG,
    LOCAL_COMMAND_STDERR_TAG,
    LOCAL_COMMAND_CAVEAT_TAG,
)

TICK_TAG = "tick"

TASK_NOTIFICATION_TAG = "task-notification"
TASK_ID_TAG = "task-id"
TOOL_USE_ID_TAG = "tool-use-id"
TASK_TYPE_TAG = "task-type"
OUTPUT_FILE_TAG = "output-file"
STATUS_TAG = "status"
SUMMARY_TAG = "summary"
REASON_TAG = "reason"
WORKTREE_TAG = "worktree"
WORKTREE_PATH_TAG = "worktreePath"
WORKTREE_BRANCH_TAG = "worktreeBranch"

ULTRAPLAN_TAG = "ultraplan"
REMOTE_REVIEW_TAG = "remote-review"
REMOTE_REVIEW_PROGRESS_TAG = "remote-review-progress"
TEAMMATE_MESSAGE_TAG = "teammate-message"
CHANNEL_MESSAGE_TAG = "channel-message"
CHANNEL_TAG = "channel"
CROSS_SESSION_MESSAGE_TAG = "cross-session-message"

FORK_BOILERPLATE_TAG = "fork-boilerplate"
FORK_DIRECTIVE_PREFIX = "Your directive: "

COMMON_HELP_ARGS: tuple[str, ...] = ("help", "-h", "--help")
COMMON_INFO_ARGS: tuple[str, ...] = (
    "list",
    "show",
    "display",
    "current",
    "view",
    "get",
    "check",
    "describe",
    "print",
    "version",
    "about",
    "status",
    "?",
)

# ---------------------------------------------------------------------------
# Message constants  (messages.ts)
# ---------------------------------------------------------------------------

NO_CONTENT_MESSAGE = "(no content)"

# ---------------------------------------------------------------------------
# Date utilities  (common.ts)
# ---------------------------------------------------------------------------


def get_local_iso_date() -> str:
    """Return the local date in YYYY-MM-DD format.

    Respects ``CLAUDE_CODE_OVERRIDE_DATE`` env var.
    """
    override = os.environ.get("CLAUDE_CODE_OVERRIDE_DATE")
    if override:
        return override
    return date.today().isoformat()


_session_start_date_lock = threading.Lock()
_session_start_date: str | None = None


def get_session_start_date() -> str:
    """Memoised local date — captured once per session."""
    global _session_start_date
    if _session_start_date is not None:
        return _session_start_date
    with _session_start_date_lock:
        if _session_start_date is None:
            _session_start_date = get_local_iso_date()
    return _session_start_date


def reset_session_start_date() -> None:
    """Reset the memoised date (for tests)."""
    global _session_start_date
    _session_start_date = None


def get_local_month_year() -> str:
    """Return ``"Month YYYY"`` (e.g. ``"February 2026"``)."""
    override = os.environ.get("CLAUDE_CODE_OVERRIDE_DATE")
    if override:
        d = datetime.fromisoformat(override)
    else:
        d = datetime.now()
    return d.strftime("%B %Y")

# ---------------------------------------------------------------------------
# System prompt section caching  (systemPromptSections.ts)
# ---------------------------------------------------------------------------

ComputeFn = Callable[[], str | None]


@dataclass
class SystemPromptSection:
    """A named section of the system prompt with lazy compute."""
    name: str
    compute: ComputeFn
    cache_break: bool = False


def system_prompt_section(name: str, compute: ComputeFn) -> SystemPromptSection:
    """Create a memoised prompt section (cached until /clear or /compact)."""
    return SystemPromptSection(name=name, compute=compute, cache_break=False)


def dangerous_uncached_system_prompt_section(
    name: str,
    compute: ComputeFn,
    _reason: str = "",
) -> SystemPromptSection:
    """Prompt section that recomputes every turn (breaks prompt cache)."""
    return SystemPromptSection(name=name, compute=compute, cache_break=True)


_section_cache: dict[str, str | None] = {}


def resolve_system_prompt_sections(
    sections: list[SystemPromptSection],
) -> list[str | None]:
    """Resolve sections, caching non-volatile ones."""
    results: list[str | None] = []
    for section in sections:
        if not section.cache_break and section.name in _section_cache:
            results.append(_section_cache[section.name])
            continue
        value = section.compute()
        _section_cache[section.name] = value
        results.append(value)
    return results


def clear_system_prompt_sections() -> None:
    """Clear cached prompt sections (called on /clear and /compact)."""
    _section_cache.clear()

# ---------------------------------------------------------------------------
# Output style configuration  (outputStyles.ts)
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_STYLE_NAME = "default"


@dataclass(frozen=True)
class OutputStyleConfig:
    name: str
    description: str
    prompt: str
    source: str = "built-in"
    keep_coding_instructions: bool = True
    force_for_plugin: bool = False


# Built-in output styles matching npm
OUTPUT_STYLE_CONFIGS: dict[str, OutputStyleConfig | None] = {
    DEFAULT_OUTPUT_STYLE_NAME: None,
    "Explanatory": OutputStyleConfig(
        name="Explanatory",
        description="Claude explains its implementation choices and codebase patterns",
        prompt=(
            "You are an interactive CLI tool that helps users with software "
            "engineering tasks. In addition to software engineering tasks, you "
            "should provide educational insights about the codebase along the way.\n\n"
            "You should be clear and educational, providing helpful explanations "
            "while remaining focused on the task. Balance educational content "
            "with task completion."
        ),
    ),
    "Learning": OutputStyleConfig(
        name="Learning",
        description="Claude pauses and asks you to write small pieces of code for hands-on practice",
        prompt=(
            "You are an interactive CLI tool that helps users with software "
            "engineering tasks. In addition to software engineering tasks, you "
            "should help users learn more about the codebase through hands-on "
            "practice and educational insights.\n\n"
            "You should be collaborative and encouraging. Balance task completion "
            "with learning by requesting user input for meaningful design "
            "decisions while handling routine implementation yourself."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Knowledge cutoff  (prompts.ts)
# ---------------------------------------------------------------------------

FRONTIER_MODEL_NAME = "Claude Opus 4.6"

_KNOWLEDGE_CUTOFFS: dict[str, str] = {
    "claude-sonnet-4-6": "August 2025",
    "claude-opus-4-6": "May 2025",
    "claude-opus-4-5": "May 2025",
    "claude-haiku-4": "February 2025",
    "claude-opus-4": "January 2025",
    "claude-sonnet-4": "January 2025",
}


def get_knowledge_cutoff(model_id: str) -> str | None:
    """Return knowledge cutoff date for a model, or None."""
    canonical = model_id.lower()
    for pattern, cutoff in _KNOWLEDGE_CUTOFFS.items():
        if pattern in canonical:
            return cutoff
    return None

# ---------------------------------------------------------------------------
# Model family IDs  (prompts.ts)
# ---------------------------------------------------------------------------

CLAUDE_MODEL_IDS = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# ---------------------------------------------------------------------------
# Hooks section  (prompts.ts)
# ---------------------------------------------------------------------------

HOOKS_SECTION = (
    "Users may configure 'hooks', shell commands that execute in response to "
    "events like tool calls, in settings. Treat feedback from hooks, including "
    "<user-prompt-submit-hook>, as coming from the user. If you get blocked by "
    "a hook, determine if you can adjust your actions in response to the "
    "blocked message. If not, ask the user to check their hooks configuration."
)

# ---------------------------------------------------------------------------
# System reminders section  (prompts.ts)
# ---------------------------------------------------------------------------

SYSTEM_REMINDERS_SECTION = (
    "- Tool results and user messages may include <system-reminder> tags. "
    "<system-reminder> tags contain useful information and reminders. They are "
    "automatically added by the system, and bear no direct relation to the "
    "specific tool results or user messages in which they appear.\n"
    "- The conversation has unlimited context through automatic summarization."
)

# ---------------------------------------------------------------------------
# Summarize tool results  (prompts.ts)
# ---------------------------------------------------------------------------

SUMMARIZE_TOOL_RESULTS_SECTION = (
    "When working with tool results, write down any important information you "
    "might need later in your response, as the original tool result may be "
    "cleared later."
)

# ---------------------------------------------------------------------------
# Default agent prompt  (prompts.ts)
# ---------------------------------------------------------------------------

DEFAULT_AGENT_PROMPT = (
    "You are an agent for Claude Code, Anthropic's official CLI for Claude. "
    "Given the user's message, you should use the tools available to complete "
    "the task. Complete the task fully\u2014don't gold-plate, but don't leave "
    "it half-done. When you complete the task, respond with a concise report "
    "covering what was done and any key findings \u2014 the caller will relay "
    "this to the user, so it only needs the essentials."
)

# ---------------------------------------------------------------------------
# Error IDs  (errorIds.ts)
# ---------------------------------------------------------------------------

E_TOOL_USE_SUMMARY_GENERATION_FAILED = 344

# ---------------------------------------------------------------------------
# Dynamic boundary marker  (prompts.ts)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_DYNAMIC_BOUNDARY = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"

# ---------------------------------------------------------------------------
# Convenience helpers for use in prompt building
# ---------------------------------------------------------------------------


def get_language_section(language_preference: str | None) -> str | None:
    """Return the language preference prompt section, or None."""
    if not language_preference:
        return None
    return (
        f"# Language\n"
        f"Always respond in {language_preference}. Use {language_preference} "
        f"for all explanations, comments, and communications with the user. "
        f"Technical terms and code identifiers should remain in their original form."
    )


def get_output_style_section(config: OutputStyleConfig | None) -> str | None:
    """Return the output-style prompt section, or None."""
    if config is None:
        return None
    return f"# Output Style: {config.name}\n{config.prompt}"


def get_scratchpad_instructions(scratchpad_dir: str | None) -> str | None:
    """Return scratchpad instructions, or None if no scratchpad is configured."""
    if not scratchpad_dir:
        return None
    return (
        f"# Scratchpad Directory\n\n"
        f"IMPORTANT: Always use this scratchpad directory for temporary files "
        f"instead of `/tmp` or other system temp directories:\n"
        f"`{scratchpad_dir}`\n\n"
        f"Use this directory for ALL temporary file needs:\n"
        f"- Storing intermediate results or data during multi-step tasks\n"
        f"- Writing temporary scripts or configuration files\n"
        f"- Saving outputs that don't belong in the user's project\n"
        f"- Creating working files during analysis or processing\n"
        f"- Any file that would otherwise go to `/tmp`\n\n"
        f"Only use `/tmp` if the user explicitly requests it.\n\n"
        f"The scratchpad directory is session-specific, isolated from the "
        f"user's project, and can be used freely without permission prompts."
    )
