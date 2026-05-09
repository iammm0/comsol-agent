"""把 ``ReActTaskPlan`` 的 execution_path 同步到 ``PlanRuntime`` + ``TaskRuntime``。

这样做的好处：
- 计划状态机有一份独立、规范化的落盘（``.port_sessions/plan_runtime.json``、
  ``task_runtime.json``），方便审计/回放/桌面端展示。
- ``PlanRuntime.update_plan(sync_tasks=True)`` 会自动维护 task_runtime，省得我们
  在 IterationController 里手写两份。
- 同步是单向：mph-agent ReActTaskPlan 是 source of truth，本类只负责镜像。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agent.clawcode.plan_runtime import PlanRuntime
from agent.clawcode.task_runtime import TaskRuntime
from agent.utils.logger import get_logger

if TYPE_CHECKING:
    from agent.schemas.task import ExecutionStep, ReActTaskPlan

logger = get_logger(__name__)


_REACT_TO_PLAN_STATUS = {
    "pending": "pending",
    "running": "in_progress",
    "completed": "completed",
    "warning": "completed",
    "skipped": "cancelled",
    "failed": "blocked",
}


class PlanSync:
    """ReActTaskPlan ↔ PlanRuntime / TaskRuntime 单向镜像。"""

    def __init__(self, *, project_root: Path):
        self._project_root = project_root.resolve()
        self._plan_runtime: Optional[PlanRuntime] = None
        self._task_runtime: Optional[TaskRuntime] = None

    @property
    def plan_runtime(self) -> PlanRuntime:
        if self._plan_runtime is None:
            self._plan_runtime = PlanRuntime.from_workspace(self._project_root)
        return self._plan_runtime

    @property
    def task_runtime(self) -> TaskRuntime:
        if self._task_runtime is None:
            self._task_runtime = TaskRuntime.from_workspace(self._project_root)
        return self._task_runtime

    def sync(
        self,
        plan: "ReActTaskPlan",
        *,
        explanation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """把 plan.execution_path 写入 PlanRuntime/TaskRuntime；返回 mutation 摘要。"""

        try:
            items = self._build_plan_items(plan)
            mutation = self.plan_runtime.update_plan(
                items,
                explanation=(
                    explanation
                    or (plan.plan_description or "").strip()
                    or f"task_id={plan.task_id} status={plan.status}"
                ),
                task_runtime=self.task_runtime,
                sync_tasks=True,
            )
            return {
                "store_path": mutation.store_path,
                "after_count": mutation.after_count,
                "before_count": mutation.before_count,
                "synced_tasks": mutation.synced_tasks,
                "sha256": mutation.after_sha256,
            }
        except Exception as exc:  # pragma: no cover - 容错降级
            logger.warning("PlanSync.sync 失败：%s", exc)
            return {"error": str(exc)}

    def clear(self) -> None:
        try:
            self.plan_runtime.clear_plan(task_runtime=self.task_runtime)
        except Exception as exc:  # pragma: no cover
            logger.warning("PlanSync.clear 失败：%s", exc)

    def _build_plan_items(self, plan: "ReActTaskPlan") -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for index, step in enumerate(plan.execution_path, start=1):
            description = self._build_step_description(step)
            items.append(
                {
                    "step": f"{step.action} ({step.step_type})",
                    "status": _REACT_TO_PLAN_STATUS.get(step.status, "pending"),
                    "task_id": step.step_id or f"plan_{index}",
                    "description": description,
                    "active_form": (
                        f"正在执行 {step.action}" if step.status == "running" else None
                    ),
                }
            )
        return items

    @staticmethod
    def _build_step_description(step: "ExecutionStep") -> str:
        parts: List[str] = []
        result = step.result if isinstance(step.result, dict) else None
        if result:
            message = (result.get("message") or "").strip()
            if message:
                parts.append(message[:160])
            saved = result.get("saved_path") or result.get("model_path")
            if saved:
                parts.append(f"saved={saved}")
        params = step.parameters or {}
        if params:
            keys = ",".join(sorted(params.keys())[:6])
            parts.append(f"params={keys}")
        return "; ".join(parts) if parts else step.action
