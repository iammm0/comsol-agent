"""
模型开发器 Agent 模块（Model Builder）。

职责：几何、物理场、网格、研究、求解、结果分析。
当前实现由 src.planner、src.executor、src.comsol 组成，此处做命名空间汇聚与重导出，
便于从 src.agents.model_developer 统一访问；现有代码仍可直接使用 src.planner / src.comsol 等。
"""
# 重导出，便于 from src.agents.model_developer import PlannerAgent, COMSOLWrapper, GeometryPlan 等
from src.planner.agent import PlannerAgent
from src.planner.schema import GeometryPlan, GeometryShape
from src.executor.agent import ExecutorAgent
from src.comsol.api_wrapper import COMSOLWrapper
from src.comsol.config import comsol_config
from src.comsol.templates import COMSOLTemplate

__all__ = [
    "PlannerAgent",
    "ExecutorAgent",
    "GeometryPlan",
    "GeometryShape",
    "COMSOLWrapper",
    "comsol_config",
    "COMSOLTemplate",
]
