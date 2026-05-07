"""把 mph-agent 的 planner 子 Agent 物化为 ``.claude/agents/*.md``。

这样做的目的：
- ``agent_registry.load_agent_registry`` 能感知到几何/材料/物理/研究/网格各 Agent；
- 桌面端（或 LocalCodingAgent 主控）可以通过 ``@geometry-planner`` 风格触发；
- 文件保留为可编辑的 markdown，便于改 system prompt 不动 Python。

我们不替换原有 Python 实现（``agent/planner/*.py`` 仍然是真正的执行体），
只是把它们的角色描述、提示词加成同步成 .md 描述符。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

from agent.utils.logger import get_logger

logger = get_logger(__name__)


_SUB_AGENT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "agent_type": "comsol-geometry-planner",
        "when_to_use": "需要把自然语言转成 GeometryPlan（矩形/圆/球/拉伸/旋转等）时使用。",
        "tools": ["read_file", "grep_search", "glob_search"],
        "model": "inherit",
        "system_prompt": (
            "你是 mph-agent 的几何规划子 Agent，负责将中文自然语言 COMSOL 几何描述映射到 "
            "schemas.geometry.GeometryPlan。严格遵循 prompts/planner/geometry_planner.txt 中的 "
            "字段约束，输出 JSON。不写任何 Java 代码，也不直接调用 COMSOL，只做计划。"
        ),
    },
    {
        "agent_type": "comsol-material-planner",
        "when_to_use": "需要从需求中提取材料并准备 MaterialPlan（包含 E、nu、k、rho 等）。",
        "tools": ["read_file", "grep_search", "glob_search"],
        "model": "inherit",
        "system_prompt": (
            "你是 mph-agent 的材料规划子 Agent。优先使用快识别表（钢、铝、铜、空气、水等）；"
            "未识别时按上下文推断并显式列出必需属性，遵循 prompts/planner/material_planner.txt。"
        ),
    },
    {
        "agent_type": "comsol-physics-planner",
        "when_to_use": "需要选择物理接口（固体力学、传热、电磁、流动等）并生成 PhysicsPlan。",
        "tools": ["read_file", "grep_search", "glob_search"],
        "model": "inherit",
        "system_prompt": (
            "你是 mph-agent 的物理场规划子 Agent。基于几何与材料生成 PhysicsPlan，包括接口选择、"
            "边界条件、源项、耦合关系。遵循 prompts/planner/physics_planner.txt，输出严格 JSON。"
        ),
    },
    {
        "agent_type": "comsol-mesh-planner",
        "when_to_use": "需要规划网格（自由四面体/扫掠/边界层）时调用。",
        "tools": ["read_file"],
        "model": "inherit",
        "system_prompt": (
            "你是 mph-agent 的网格规划子 Agent，输出适合当前几何/物理场的 MeshPlan。"
            "遵循 prompts/planner/mesh_planner.txt 提供的策略表与默认值。"
        ),
    },
    {
        "agent_type": "comsol-study-planner",
        "when_to_use": "需要选择稳态/瞬态/参数化扫描等研究类型并生成 StudyPlan 时调用。",
        "tools": ["read_file"],
        "model": "inherit",
        "system_prompt": (
            "你是 mph-agent 的研究规划子 Agent。根据物理场与目标输出选择研究类型，"
            "并把扫描参数写成 StudyPlan，遵循 prompts/planner/study_planner.txt。"
        ),
    },
    {
        "agent_type": "comsol-orchestrator",
        "when_to_use": "需要把建模需求拆成串行子任务（geometry/material/physics/study/...）时调用。",
        "tools": ["delegate_agent", "read_file", "grep_search"],
        "model": "inherit",
        "system_prompt": (
            "你是 mph-agent 的编排子 Agent，负责调度上面五个子 planner，"
            "遵循 prompts/planner/orchestrator_decompose.txt，并在最后返回 ReActTaskPlan-ready 计划。"
        ),
    },
]


def ensure_sub_agent_definitions(
    project_root: Path,
    *,
    overwrite: bool = False,
) -> List[Path]:
    """把 ``.claude/agents/*.md`` 写入项目根，返回写入的文件列表。"""

    out_dir = project_root.resolve() / ".claude" / "agents"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for template in _SUB_AGENT_TEMPLATES:
        slug = template["agent_type"]
        target = out_dir / f"{slug}.md"
        if target.exists() and not overwrite:
            written.append(target)
            continue
        target.write_text(_render_agent_markdown(template), encoding="utf-8")
        written.append(target)
    return written


def _render_agent_markdown(template: Dict[str, Any]) -> str:
    frontmatter_lines = [
        "---",
        f"name: {template['agent_type']}",
        f"when_to_use: {template['when_to_use']}",
        f"model: {template.get('model', 'inherit')}",
    ]
    tools = template.get("tools")
    if tools:
        frontmatter_lines.append("tools:")
        for tool in tools:
            frontmatter_lines.append(f"  - {tool}")
    frontmatter_lines.append("---")
    body = template.get("system_prompt", "").rstrip()
    return "\n".join(frontmatter_lines) + "\n\n" + body + "\n"


def list_sub_agent_definitions(project_root: Path) -> List[Dict[str, Any]]:
    out_dir = project_root.resolve() / ".claude" / "agents"
    if not out_dir.exists():
        return []
    items: List[Dict[str, Any]] = []
    for path in sorted(out_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        items.append({"path": str(path), "size": len(text)})
    return items
