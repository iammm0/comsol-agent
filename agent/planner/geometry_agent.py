"""几何建模 Planner Agent"""
import json
import re
from typing import Optional

from agent.utils.llm import LLMClient
from agent.utils.prompt_loader import prompt_loader
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.geometry import GeometryPlan

logger = get_logger(__name__)


class GeometryAgent:
    """几何建模 Planner Agent"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        backend: Optional[str] = None,
        base_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化几何建模 Agent
        
        Args:
            api_key: API Key（用于 dashscope、openai、openai-compatible）
            backend: LLM 后端类型，如果为 None 则从配置读取
                - "dashscope": Dashscope (Qwen) 官方 API
                - "openai": OpenAI 官方 API
                - "openai-compatible": 符合 OpenAI API 规范的第三方服务
                - "ollama": Ollama 服务（本地或远程）
            base_url: API 基础 URL
                - 对于 openai: 可选，默认使用官方 API
                - 对于 openai-compatible: 必须提供
            ollama_url: Ollama 服务地址（仅用于 ollama 后端）
            model: 模型名称（可选）
        """
        settings = get_settings()
        backend = backend or settings.llm_backend
        
        if backend == "dashscope":
            self.llm = LLMClient(
                backend="dashscope",
                api_key=api_key or settings.dashscope_api_key,
                model=model
            )
        elif backend == "openai":
            self.llm = LLMClient(
                backend="openai",
                api_key=api_key or settings.openai_api_key,
                base_url=base_url or settings.openai_base_url,
                model=model or settings.openai_model
            )
        elif backend == "openai-compatible":
            self.llm = LLMClient(
                backend="openai-compatible",
                api_key=api_key or settings.openai_compatible_api_key,
                base_url=base_url or settings.openai_compatible_base_url,
                model=model or settings.openai_compatible_model
            )
        elif backend == "ollama":
            self.llm = LLMClient(
                backend="ollama",
                ollama_url=ollama_url or settings.ollama_url,
                model=model or settings.ollama_model
            )
        else:
            raise ValueError(
                f"不支持的后端类型: {backend}，"
                f"支持的后端: dashscope, openai, openai-compatible, ollama"
            )
    
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
        
        # 加载并格式化 Prompt
        prompt = prompt_loader.format(
            "planner",
            "geometry_planner",
            user_input=enhanced_input
        )
        
        # 调用 LLM
        response_text = self.llm.call(prompt, temperature=0.1, max_retries=max_retries)
        
        # 提取 JSON
        json_data = self._extract_json_from_response(response_text)
        
        # 验证并创建 GeometryPlan
        plan = GeometryPlan.from_dict(json_data)
        
        logger.info(f"解析成功: {len(plan.shapes)} 个形状")
        return plan
