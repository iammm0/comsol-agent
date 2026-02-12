"""按需注入：根据 query 匹配技能，Top-K 拼接到系统提示词。"""
from typing import List, Optional

from agent.skills.loader import SkillLoader, Skill

MARKER = "=== RELEVANT SKILLS ==="


class SkillInjector:
    """
    根据用户 query 与 triggers/tags 匹配，取 Top-K 技能，
    将 instructions 拼接到系统提示词末尾，并打分隔标记。
    """

    def __init__(self, loader: Optional[SkillLoader] = None, top_k: int = 3):
        self.loader = loader or SkillLoader()
        self.top_k = top_k
        self._last_used: List[str] = []

    def inject(self, query: str, system_prompt: str) -> str:
        """
        在调用 LLM 前调用：返回增强后的 system_prompt。
        """
        skills = self.loader.get_skills_by_triggers(query)
        if not skills:
            skills = self.loader.list_skills()[: self.top_k]
        else:
            skills = skills[: self.top_k]

        if not skills:
            return system_prompt

        self._last_used = [s.name for s in skills]
        block = "\n\n".join(s.instructions for s in skills if s.instructions.strip())
        return f"{system_prompt}\n\n{MARKER}\n{block}"

    def last_used_skills(self) -> List[str]:
        """返回本轮注入使用的技能名，便于日志与统计。"""
        return list(self._last_used)
