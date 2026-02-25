"""几何建模 Planner Agent"""
import json
import re
from typing import Optional, Any

from agent.base import BaseAgent
from agent.utils.llm import LLMClient
from agent.utils.prompt_loader import prompt_loader
from agent.skills import get_skill_injector
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.geometry import GeometryPlan

logger = get_logger(__name__)


class GeometryAgent(BaseAgent):
    """几何建模 Planner Agent：解析意图、产出几何计划。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        backend: Optional[str] = None,
        base_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
    ):
        super().__init__(system_prompt=system_prompt, history=history)
        settings = get_settings()
        backend = backend or settings.llm_backend
        self.llm = LLMClient(
            backend=backend,
            api_key=api_key or settings.get_api_key_for_backend(backend),
            base_url=base_url or settings.get_base_url_for_backend(backend),
            ollama_url=ollama_url or settings.ollama_url,
            model=model or settings.get_model_for_backend(backend),
        )

    def process(self, user_input: str, **kwargs: Any) -> str:
        """BaseAgent 接口：解析并返回简短摘要字符串。"""
        plan = self.parse(user_input, context=kwargs.get("context"))
        return f"解析成功: {len(plan.shapes)} 个形状; model_name={plan.model_name}"
    
    def _extract_json_from_response(self, response_text: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取第一个 { ... } 块
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"无法从响应中提取有效的 JSON: {response_text[:200]}")
    
    def parse(
        self,
        user_input: str,
        max_retries: int = 3,
        context: Optional[str] = None
    ) -> GeometryPlan:
        """
        解析自然语言输入为结构化 JSON
        
        Args:
            user_input: 用户自然语言描述
            max_retries: 最大重试次数
            context: 上下文信息（可选）
        
        Returns:
            GeometryPlan 对象
        
        Raises:
            ValueError: 解析失败
        """
        logger.info(f"解析用户输入: {user_input}")
        
        # 如果有上下文，添加到用户输入中
        if context:
            enhanced_input = f"{context}\n\n用户当前需求: {user_input}"
        else:
            enhanced_input = user_input
        
        # 加载并格式化 Prompt，并注入 skills 隐性知识
        prompt = prompt_loader.format(
            "planner",
            "geometry_planner",
            user_input=enhanced_input
        )
        prompt = get_skill_injector().inject_into_prompt(user_input, prompt)
        # 调用 LLM
        response_text = self.llm.call(prompt, temperature=0.1, max_retries=max_retries)
        
        # 提取 JSON
        json_data = self._extract_json_from_response(response_text)
        
        # 验证并创建 GeometryPlan
        plan = GeometryPlan.from_dict(json_data)
        
        logger.info("解析成功: %s 个形状", len(plan.shapes))
        return plan
