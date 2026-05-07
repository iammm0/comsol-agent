"""把 mph-agent 的标准建模管线表达为 ``WorkflowDefinition``。

只在仓库根目录维护一份 ``.claw-workflows.json``：
- ``WorkflowRuntime.from_workspace`` 默认加载它。
- 若用户希望增加自定义管线（例如「热-结构耦合简版」「电磁-传热全套」），
  直接编辑该 JSON 即可，不必动 Python。

本模块只负责"manifest 物化 + 加载"，不直接驱动 ActionExecutor；上层
``do_workflow`` 会根据 manifest 拿到 step 列表，再走现有 ReAct/Action 链路。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.clawcode.workflow_runtime import (
    WorkflowDefinition,
    WorkflowRuntime,
    WORKFLOW_MANIFEST_FILES,
)
from agent.utils.logger import get_logger

logger = get_logger(__name__)


DEFAULT_WORKFLOW_MANIFEST: Dict[str, Any] = {
    "workflows": [
        {
            "name": "comsol_full_pipeline",
            "description": (
                "mph-agent 标准 COMSOL 建模管线：几何 → 全局参数 → 材料 → 物理场 → 网格 → 研究 → 求解 → 结果导出。"
            ),
            "prompt": (
                "请按照下面的步骤执行建模任务，每个步骤都通过 mph-agent 的 ActionExecutor 调度，"
                "保持阶段性 .mph 落盘以便回放：\n"
                "1. create_geometry\n"
                "2. define_globals (可选)\n"
                "3. add_material\n"
                "4. add_physics\n"
                "5. generate_mesh\n"
                "6. configure_study\n"
                "7. solve\n"
                "8. export_results"
            ),
            "steps": [
                {"name": "create_geometry", "detail": "根据 GeometryPlan 创建几何并保存 _geometry.mph"},
                {"name": "define_globals", "detail": "（可选）写入 model.param() 全局参数"},
                {"name": "add_material", "detail": "添加材料并完成域分配"},
                {"name": "add_physics", "detail": "添加物理场接口与边界条件"},
                {"name": "generate_mesh", "detail": "生成默认网格"},
                {"name": "configure_study", "detail": "配置稳态/瞬态/参数化扫描研究"},
                {"name": "solve", "detail": "求解并保存最终模型"},
                {"name": "export_results", "detail": "导出结果图/数据，需要 out_path 参数"},
            ],
            "metadata": {
                "owner": "mph-agent",
                "category": "comsol",
                "stage_outputs": [
                    "_geometry.mph",
                    "_global.mph",
                    "_material.mph",
                    "_physics.mph",
                    "_mesh.mph",
                    "_study.mph",
                    "_solve.mph",
                    "_latest.mph",
                ],
            },
        },
        {
            "name": "comsol_geometry_only",
            "description": "仅创建几何并保存 _geometry.mph（适合「只建几何」场景）",
            "steps": [
                {"name": "create_geometry", "detail": "依赖 GeometryAgent 输出"},
            ],
            "metadata": {"owner": "mph-agent", "category": "comsol"},
        },
        {
            "name": "comsol_material_then_solve",
            "description": "假设几何已存在，跑材料 → 物理 → 网格 → 研究 → 求解。",
            "steps": [
                {"name": "add_material"},
                {"name": "add_physics"},
                {"name": "generate_mesh"},
                {"name": "configure_study"},
                {"name": "solve"},
            ],
            "metadata": {"owner": "mph-agent", "category": "comsol"},
        },
    ]
}


def ensure_default_workflow_manifest(
    project_root: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """确保仓库根有一份默认 manifest；返回写入路径。"""

    target = project_root.resolve() / WORKFLOW_MANIFEST_FILES[0]
    if target.exists() and not overwrite:
        return target
    try:
        target.write_text(
            json.dumps(DEFAULT_WORKFLOW_MANIFEST, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover
        logger.warning("写入默认 workflow manifest 失败：%s", exc)
    return target


def load_workflow_runtime(project_root: Path) -> WorkflowRuntime:
    """加载（必要时先生成默认 manifest）``WorkflowRuntime``。"""

    ensure_default_workflow_manifest(project_root)
    return WorkflowRuntime.from_workspace(project_root.resolve())


def get_workflow_definition(
    project_root: Path,
    name: str,
) -> Optional[WorkflowDefinition]:
    runtime = load_workflow_runtime(project_root)
    return runtime.get_workflow(name)


def list_workflow_definitions(project_root: Path) -> List[Dict[str, Any]]:
    runtime = load_workflow_runtime(project_root)
    return [
        {
            "name": w.name,
            "description": w.description,
            "steps": [dict(step) for step in w.steps],
            "metadata": dict(w.metadata),
        }
        for w in runtime.list_workflows()
    ]
