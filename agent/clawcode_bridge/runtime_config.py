"""统一构造 ``AgentRuntimeConfig`` / ``ModelConfig``，避免散落在多处。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agent.clawcode.agent_types import (
    AgentPermissions,
    AgentRuntimeConfig,
    ModelConfig,
)
from agent.utils.config import get_project_root, get_settings


def build_default_runtime_config(
    project_root: Optional[Path] = None,
    *,
    allow_file_write: bool = True,
    allow_shell_commands: bool = True,
    allow_destructive_shell_commands: bool = False,
    max_turns: Optional[int] = None,
    command_timeout_seconds: Optional[float] = None,
) -> AgentRuntimeConfig:
    """根据 mph-agent settings 构造 ``AgentRuntimeConfig``。

    - 默认写文件、可执行 shell（与 ``ClawCodeComsolDispatcher`` 行为对齐）。
    - 会话目录、scratchpad 都落到项目根 ``.port_sessions`` 下。
    """

    settings = get_settings()
    root = Path(project_root or get_project_root()).resolve()
    return AgentRuntimeConfig(
        cwd=root,
        max_turns=int(max_turns or settings.claw_code_max_turns),
        command_timeout_seconds=float(
            command_timeout_seconds or settings.claw_code_timeout_seconds
        ),
        permissions=AgentPermissions(
            allow_file_write=allow_file_write,
            allow_shell_commands=allow_shell_commands,
            allow_destructive_shell_commands=allow_destructive_shell_commands,
        ),
        session_directory=root / ".port_sessions" / "agent",
        scratchpad_root=root / ".port_sessions" / "scratchpad",
    )


def build_default_model_config() -> ModelConfig:
    """复用 ``ClawCodeComsolDispatcher`` 的解析逻辑，避免在多处复写。"""

    from agent.executor.clawcode_dispatcher import ClawCodeComsolDispatcher

    return ClawCodeComsolDispatcher()._resolve_model_config()
