"""几何建模 Planner Agent — 支持 2D/3D"""
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

_3D_KEYWORDS = re.compile(
    r"3[dD]|三维|立方体|长方体|block|圆柱|cylinder|球|sphere|锥|cone|圆环|torus"
    r"|拉伸|extrude|旋转体|revolve|深度|depth",
    re.IGNORECASE,
)


class GeometryAgent(BaseAgent):
    """几何建模 Planner Agent：解析意图、产出几何计划（2D/3D）。"""

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
        plan = self.parse(user_input, context=kwargs.get("context"))
        dim_label = "3D" if plan.dimension == 3 else "2D"
        return (
            f"解析成功: {len(plan.shapes)} 个形状, "
            f"{len(plan.operations)} 个操作, {dim_label}; "
            f"model_name={plan.model_name}"
        )

    def _extract_json_from_response(self, response_text: str) -> dict:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从响应中提取有效的 JSON: {response_text[:200]}")

    @staticmethod
    def _infer_dimension(user_input: str) -> int:
        """根据关键词推断用户需要 2D 还是 3D"""
        if _3D_KEYWORDS.search(user_input):
            return 3
        return 2

    def parse(
        self,
        user_input: str,
        max_retries: int = 3,
        context: Optional[str] = None,
    ) -> GeometryPlan:
        logger.info(f"解析用户输入: {user_input}")

        if context:
            enhanced_input = f"{context}\n\n用户当前需求: {user_input}"
        else:
            enhanced_input = user_input

        prompt = prompt_loader.format(
            "planner",
            "geometry_planner",
            user_input=enhanced_input,
        )
        prompt = get_skill_injector().inject_into_prompt(user_input, prompt)

        response_text = self.llm.call(prompt, temperature=0.1, max_retries=max_retries)
        json_data = self._extract_json_from_response(response_text)

        # 若 LLM 未输出 dimension，根据关键词自动推断
        if "dimension" not in json_data:
            json_data["dimension"] = self._infer_dimension(user_input)

        plan = GeometryPlan.from_dict(json_data)
        logger.info(
            "解析成功: %s 个形状, %s 个操作, %sD",
            len(plan.shapes), len(plan.operations), plan.dimension,
        )
        return plan
