"""Prompt 模板加载器（委托给 PromptManager，保持向后兼容）。"""
from pathlib import Path
from typing import Dict, Any

from agent.utils.prompt_manager import get_prompt_manager


class PromptLoader:
    """
    兼容旧接口的 Prompt 加载器，内部委托给 PromptManager。
    推荐直接使用 get_prompt_manager() 或 PromptManager。
    """

    def __init__(self, prompts_dir: str = "prompts"):
        # 相对路径转为绝对路径（项目根下的 prompts）
        root = Path(__file__).parent.parent.parent
        self._mgr = get_prompt_manager(root / prompts_dir)

    @property
    def prompts_dir(self) -> Path:
        return self._mgr.prompts_dir

    @property
    def _cache(self) -> Dict[str, str]:
        return self._mgr._cache

    def load(self, category: str, name: str) -> str:
        return self._mgr.load(category, name)

    def format(self, category: str, name: str, **kwargs: Any) -> str:
        return self._mgr.format(category, name, **kwargs)


# 全局实例：使用默认 prompts 目录
prompt_loader = get_prompt_manager()
