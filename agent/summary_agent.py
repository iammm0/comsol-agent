"""Summary Agent：对当轮工具执行结果做摘要，供用户与审计。"""
from typing import Optional, Any

from agent.base import BaseAgent
from agent.utils.llm import LLMClient
from agent.utils.config import get_settings
from agent.utils.logger import get_logger

logger = get_logger(__name__)


class SummaryAgent(BaseAgent):
    """对当轮执行结果做简短摘要。"""

    def _default_system_prompt(self) -> str:
        return (
            "你是 COMSOL 建模助手。根据本轮的建模步骤与执行结果，"
            "用一两句话总结完成了什么、是否有错误或警告。"
        )

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        history: Optional[list] = None,
        backend: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
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
        """
        对「当轮工具执行结果」做摘要。
        user_input 可为执行结果文本或结构化摘要描述；kwargs 可传额外上下文。
        """
        logger.debug("Summary 处理")
        prompt = f"{self.system_prompt}\n\n本轮执行结果:\n{user_input}\n\n摘要:"
        summary = self.llm.call(prompt, temperature=0.3)
        return (summary or "").strip()
