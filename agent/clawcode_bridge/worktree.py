"""``WorktreeRuntime`` context manager 封装。

``do_run`` 想隔离每次建模执行时，可以包一层这个 context：进入时 ``git worktree add``
出来后默认 ``keep``（不破坏工件），用户可在 settings 里强制 ``remove``。
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Iterator, Optional

from agent.clawcode.worktree_runtime import (
    WorktreeRuntime,
    WorktreeStatusReport,
)
from agent.utils.logger import get_logger

logger = get_logger(__name__)


@contextlib.contextmanager
def worktree_session(
    project_root: Path,
    *,
    name: Optional[str] = None,
    cleanup_action: str = "keep",
    discard_changes: bool = False,
) -> Iterator[WorktreeStatusReport]:
    """进入一个新的 git worktree，退出时按 ``cleanup_action`` 处理。

    - ``cleanup_action="keep"``：保留 worktree（默认，方便用户后续比较）。
    - ``cleanup_action="remove"``：执行 ``git worktree remove`` + ``branch -D``。
    """

    runtime = WorktreeRuntime.from_workspace(project_root.resolve())
    if runtime.repo_root is None:
        # 不是 git 仓库或 git 不可用 → 直接 yield 一个无操作 report
        yield runtime.current_report(detail="Worktree disabled: not a git repository")
        return
    try:
        report = runtime.enter(name)
    except Exception as exc:
        logger.warning("worktree_session.enter 失败：%s", exc)
        yield runtime.current_report(detail=f"Worktree enter failed: {exc}")
        return
    try:
        yield report
    finally:
        try:
            runtime.exit(action=cleanup_action, discard_changes=discard_changes)
        except Exception as exc:  # pragma: no cover
            logger.warning("worktree_session.exit 失败：%s", exc)
