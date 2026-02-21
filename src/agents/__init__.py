"""
COMSOL 三模块 Agent 命名空间。

- model_developer: 模型开发器（主攻）
- app_developer: App 开发器（次要，占位）
- model_manager: 模型管理器（次要，占位）

模块路由与扩展点见 router 模块。
详见 docs/comsol-modules-and-context.md。
"""
from src.agents.router import COMSOLModuleRoute, route_to_module

__all__ = [
    "COMSOLModuleRoute",
    "route_to_module",
]
