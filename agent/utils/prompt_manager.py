"""PromptManager：模板目录扫描、get_template/get_chain、变量替换（{{name}} 与 .format 兼容）。"""
from pathlib import Path
from typing import Dict, List, Optional, Any

# 内联默认模板（无外部文件时也可运行）；文件模板覆盖同名项；占位符与 prompts/*.txt 一致
DEFAULT_TEMPLATES: Dict[str, str] = {
    "planner/geometry_planner": """几何建模助手。将用户描述转为 JSON。支持 rectangle/circle/ellipse，position 含 x,y，单位默认 m。用户输入：{user_input} 请只输出 JSON。""",
    "planner/physics_planner": """物理场助手。将用户描述转为 JSON。支持 heat/electromagnetic/structural/fluid。用户输入：{user_input} 请只输出 JSON。""",
    "planner/study_planner": """研究类型助手。将用户描述转为 JSON。支持 stationary/time_dependent/eigenvalue/frequency。用户输入：{user_input} 请只输出 JSON。""",
    "react/reasoning": """COMSOL 建模助手。分析用户需求并规划步骤。用户需求：{user_input} 以 JSON 返回：task_type, required_steps, parameters, reasoning。""",
    "react/planning": """根据当前状态规划下一步。模型：{model_name} 需求：{user_input} 已完成：{completed_steps} 当前步骤：{current_step} 观察：{observations} 以 JSON 返回 action, reasoning, parameters, expected_result。""",
    "react/validation": """验证建模计划。计划 JSON：{plan_json} 以 JSON 返回 valid, errors, warnings, suggestions。""",
    "executor/java_codegen": """根据计划生成 COMSOL Java API 代码。计划 JSON：{plan_json} 只输出可执行 Java 源码。""",
}


class PromptManager:
    """
    统一模板与链式提示词管理。
    - get_template(name): name 为 "category/name"，从目录或内联默认加载
    - get_chain(name): 多段链拼接（内存配置），可选
    - 变量替换：format 使用 .format(**kwargs)，模板中 {{ 表示字面量 {
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent.parent / "prompts"
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, str] = {}
        self._chains: Dict[str, List[str]] = {}  # chain_name -> list of template names
        self._scan_templates()

    def _scan_templates(self) -> None:
        """扫描 prompts 子目录，注册 category/name -> 内容。"""
        if not self.prompts_dir.exists():
            return
        for sub in self.prompts_dir.iterdir():
            if sub.is_dir():
                category = sub.name
                for f in sub.glob("*.txt"):
                    name = f.stem
                    key = f"{category}/{name}"
                    try:
                        self._cache[key] = f.read_text(encoding="utf-8")
                    except Exception:
                        pass

    def get_template(self, name: str) -> str:
        """
        获取模板正文。name 格式为 "category/name"（如 "planner/geometry_planner"）。
        先查文件缓存，再查内联默认。
        """
        if name in self._cache:
            return self._cache[name]
        if name in DEFAULT_TEMPLATES:
            return DEFAULT_TEMPLATES[name]
        raise FileNotFoundError(f"Prompt 模板不存在: {name}")

    def load(self, category: str, name: str) -> str:
        """兼容旧接口：按 category 与 name 加载，等价于 get_template(f\"{category}/{name}\")。"""
        return self.get_template(f"{category}/{name}")

    def format(self, category: str, name: str, **kwargs: Any) -> str:
        """加载并格式化：先 get_template(category/name)，再 .format(**kwargs)。"""
        template = self.load(category, name)
        return template.format(**kwargs)

    def format_template(self, name: str, **kwargs: Any) -> str:
        """按全名 name 加载并格式化。"""
        template = self.get_template(name)
        return template.format(**kwargs)

    def register_chain(self, chain_name: str, template_names: List[str]) -> None:
        """注册一条链：多段模板按顺序拼接。"""
        self._chains[chain_name] = list(template_names)

    def get_chain(self, chain_name: str, **kwargs: Any) -> str:
        """
        获取链式提示词：多段模板用双换行拼接，每段做变量替换。
        若未注册该链，则退化为 get_template(chain_name)。
        """
        if chain_name in self._chains:
            parts = [
                self.get_template(tn).format(**kwargs)
                for tn in self._chains[chain_name]
            ]
            return "\n\n".join(parts)
        return self.get_template(chain_name).format(**kwargs)

    def list_templates(self) -> List[str]:
        """列出已加载的模板名（含内联默认）。"""
        keys = set(DEFAULT_TEMPLATES) | set(self._cache)
        return sorted(keys)


# 单例，与 prompt_loader 对齐：由 prompts_dir 相对于项目根解析
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager(prompts_dir: Optional[Path] = None) -> PromptManager:
    """获取 PromptManager 单例。"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(prompts_dir=prompts_dir)
    return _prompt_manager
