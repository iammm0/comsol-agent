"""技能/插件系统：SKILL.md 加载与按需注入。"""
from agent.skills.loader import SkillLoader, Skill
from agent.skills.injector import SkillInjector

__all__ = ["SkillLoader", "Skill", "SkillInjector"]
