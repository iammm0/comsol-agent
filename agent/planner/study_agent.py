"""研究类型 Planner Agent（预留）"""
from typing import Optional

from agent.utils.llm import LLMClient
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.study import StudyPlan

logger = get_logger(__name__)


class StudyAgent:
    """研究类型 Planner Agent"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化研究类型 Agent"""
        settings = get_settings()
        self.llm = LLMClient(api_key or settings.dashscope_api_key)
    
    def parse(self, user_input: str) -> StudyPlan:
        """解析自然语言输入为研究计划"""
        # TODO: 实现研究类型解析逻辑
        raise NotImplementedError("研究类型 Agent 尚未实现")
