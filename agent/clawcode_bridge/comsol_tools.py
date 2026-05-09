"""把 ``ActionExecutor`` 14 个 handler 包装成 ``agent_tools.AgentTool``。

设计要点：
- 每个工具的输入 JSON Schema 与 ``ActionExecutor`` handler 期待的 ``thought["parameters"]``
  对齐，方便 LocalCodingAgent / function calling 直接产出。
- 工具调用内部仍走 ``ActionExecutor.execute(...)``，保证主流程的 stage 模型路径管理、
  事件总线、错误收集都不被绕过。
- 返回值统一序列化为 JSON 字符串（content）+ metadata，方便 transcript 落盘。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from agent.clawcode.agent_tools import AgentTool, ToolExecutionContext
from agent.clawcode.agent_types import ToolExecutionResult
from agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ComsolToolSession:
    """工具调用所需的 mph-agent 上下文。"""

    plan_factory: Callable[[Dict[str, Any]], Any]
    """根据 LocalCodingAgent 工具调用参数返回一个 ReActTaskPlan-like 对象。"""

    executor_factory: Callable[[], Any]
    """返回一个 ActionExecutor 实例。"""


_ACTION_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "create_geometry": {
        "type": "object",
        "properties": {
            "geometry_input": {"type": "string", "description": "几何描述自然语言"},
            "model_path": {"type": "string", "description": "可选：当前 .mph 路径，不填表示新建"},
        },
        "required": [],
    },
    "define_globals": {
        "type": "object",
        "properties": {
            "global_definitions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "unit": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["name", "value"],
                },
            }
        },
        "required": ["global_definitions"],
    },
    "add_material": {
        "type": "object",
        "properties": {
            "material_input": {"type": "string", "description": "材料描述自然语言"},
        },
        "required": [],
    },
    "update_material_property": {
        "type": "object",
        "properties": {
            "material_name": {"type": "string"},
            "material_names": {"type": "array", "items": {"type": "string"}},
            "properties": {"type": "object"},
            "property_group": {"type": "string"},
            "k": {"type": "number"},
        },
    },
    "add_physics": {
        "type": "object",
        "properties": {
            "physics_input": {"type": "string"},
        },
    },
    "generate_mesh": {
        "type": "object",
        "properties": {
            "mesh": {"type": "object"},
        },
    },
    "configure_study": {
        "type": "object",
        "properties": {
            "study_input": {"type": "string"},
        },
    },
    "solve": {"type": "object", "properties": {}},
    "import_geometry": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "geom_tag": {"type": "string"},
            "feature_tag": {"type": "string"},
        },
        "required": ["file_path"],
    },
    "create_selection": {
        "type": "object",
        "properties": {
            "tag": {"type": "string"},
            "kind": {"type": "string"},
            "geom_tag": {"type": "string"},
            "entity_dim": {"type": "integer"},
            "entities": {"type": "array"},
            "all": {"type": "boolean"},
        },
    },
    "export_results": {
        "type": "object",
        "properties": {
            "out_path": {"type": "string"},
            "export_type": {"type": "string", "enum": ["image", "data", "table"]},
            "plot_group_tag": {"type": "string"},
            "table_tag": {"type": "string"},
            "dataset": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
        "required": ["out_path"],
    },
    "call_official_api": {
        "type": "object",
        "properties": {
            "method": {"type": "string"},
            "wrapper": {"type": "string"},
            "args": {"type": ["array", "object"]},
            "target_path": {"type": "string"},
        },
    },
    "retry": {
        "type": "object",
        "properties": {
            "failed_steps": {"type": "array", "items": {"type": "string"}},
        },
    },
    "skip": {
        "type": "object",
        "properties": {
            "failed_steps": {"type": "array", "items": {"type": "string"}},
        },
    },
}


_ACTION_DESCRIPTIONS: Dict[str, str] = {
    "create_geometry": "调用 mph-agent 几何 Agent，根据自然语言描述创建并保存 _geometry.mph。",
    "define_globals": "向当前 .mph 写入 model.param() 全局参数集合，校验并落盘 _global.mph。",
    "add_material": "调用材料 Agent + Java API 添加材料，写入 _material.mph。",
    "update_material_property": "为已有材料补充属性（例如热导率 k），不重新创建材料节点。",
    "add_physics": "添加物理场与边界条件，落盘 _physics.mph。",
    "generate_mesh": "在当前 .mph 上生成默认网格，落盘 _mesh.mph。",
    "configure_study": "配置研究节点（稳态/瞬态等），落盘 _study.mph。",
    "solve": "运行已配置的研究并求解，落盘 _solve.mph。",
    "import_geometry": "导入外部几何文件（STEP/IGES/STL）。",
    "create_selection": "创建命名选择集，便于后续物理/边界引用。",
    "export_results": "导出结果（图片/数据/表格）。",
    "call_official_api": "直接调用 COMSOL 官方 Java API 包装器或 raw method。",
    "retry": "把指定 failed step 重新置为 pending。",
    "skip": "把指定 failed step 标记为 skipped。",
}


def build_comsol_tool_registry(session: ComsolToolSession) -> Dict[str, AgentTool]:
    """构造工具注册表；每个工具复用 ActionExecutor 的实现。"""

    registry: Dict[str, AgentTool] = {}

    for action, schema in _ACTION_SCHEMAS.items():
        registry[f"comsol.{action}"] = AgentTool(
            name=f"comsol.{action}",
            description=_ACTION_DESCRIPTIONS[action],
            parameters=schema,
            handler=_make_handler(action, session),
        )

    return registry


def _make_handler(
    action: str, session: ComsolToolSession
) -> Callable[[Dict[str, Any], ToolExecutionContext], tuple[str, Dict[str, Any]]]:
    def _handler(arguments: Dict[str, Any], context: ToolExecutionContext) -> tuple[str, Dict[str, Any]]:
        from agent.schemas.task import ExecutionStep

        plan = session.plan_factory(arguments)
        thought: Dict[str, Any] = {
            "action": action,
            "parameters": dict(arguments or {}),
        }
        step = ExecutionStep(
            step_id=f"tool_{action}",
            step_type=_STEP_TYPE_BY_ACTION.get(action, action),
            action=action,
            parameters=dict(arguments or {}),
            status="pending",
        )
        executor = session.executor_factory()
        try:
            result = executor.execute(plan, step, thought)
        except Exception as exc:  # pragma: no cover - 防御
            logger.exception("comsol tool %s 执行异常", action)
            return (
                json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False),
                {"action": action, "exception": type(exc).__name__},
            )
        content = json.dumps(result, ensure_ascii=False, default=str)
        metadata: Dict[str, Any] = {
            "action": action,
            "status": result.get("status") if isinstance(result, dict) else None,
            "model_path": (
                result.get("model_path") or result.get("saved_path")
                if isinstance(result, dict)
                else None
            ),
        }
        return content, metadata

    return _handler


def to_openai_tools(registry: Dict[str, AgentTool]) -> list[dict[str, Any]]:
    return [tool.to_openai_tool() for tool in registry.values()]


def execute_comsol_tool(
    registry: Dict[str, AgentTool],
    name: str,
    arguments: Dict[str, Any],
    context: ToolExecutionContext,
) -> ToolExecutionResult:
    tool = registry.get(name)
    if tool is None:
        return ToolExecutionResult(
            name=name,
            ok=False,
            content=f"Unknown comsol tool: {name}",
        )
    return tool.execute(arguments, context)


_STEP_TYPE_BY_ACTION = {
    "create_geometry": "geometry",
    "define_globals": "global",
    "add_material": "material",
    "update_material_property": "material",
    "add_physics": "physics",
    "generate_mesh": "mesh",
    "configure_study": "study",
    "solve": "solve",
    "import_geometry": "geometry_io",
    "create_selection": "selection",
    "export_results": "postprocess",
    "call_official_api": "java_api",
    "retry": "retry",
    "skip": "skip",
}


def supported_actions() -> tuple[str, ...]:
    return tuple(_ACTION_SCHEMAS.keys())
