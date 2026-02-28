"""Tool 注册表：name/description/parameters，供 ReAct 与 LLM function calling 使用。"""
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass

# 与 LLM 对接时的 parameters 通常为 JSON Schema 字典
ParametersSchema = Dict[str, Any]


@dataclass
class Tool:
    """工具定义：name、description、parameters（schema）、执行函数。"""
    name: str
    description: str
    parameters: ParametersSchema
    handler: Callable[..., Dict[str, Any]]


def _default_tools_list() -> List[Tool]:
    """占位：实际工具由 ActionExecutor 的 handler 字典对应注册。"""
    return []


class ToolRegistry:
    """工具注册表：按 name 查找并执行。"""
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """返回供 LLM 使用的工具描述列表（如 OpenAI function 格式）。"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, plan: Any, step: Any, thought: Dict[str, Any]) -> Dict[str, Any]:
        """按 name 查找工具并执行。"""
        tool = self._tools.get(name)
        if not tool:
            return {"status": "error", "message": f"未知的行动: {name}"}
        return tool.handler(plan, step, thought)
