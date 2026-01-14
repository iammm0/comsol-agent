"""物理场建模 Planner Agent（预留）"""
from typing import Optional

from agent.utils.llm import LLMClient
from agent.utils.prompt_loader import prompt_loader
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.physics import PhysicsPlan

logger = get_logger(__name__)


class PhysicsAgent:
    """物理场建模 Planner Agent"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化物理场建模 Agent"""
        settings = get_settings()
        self.llm = LLMClient(api_key or settings.dashscope_api_key)
    
    def parse(self, user_input: str) -> PhysicsPlan:
        """解析自然语言输入为物理场计划"""
        # TODO: 实现物理场解析逻辑
        raise NotImplementedError("物理场建模 Agent 尚未实现")
