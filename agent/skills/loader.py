"""技能加载器：扫描目录、解析 SKILL.md（YAML frontmatter + Markdown 正文）、缓存。"""
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Skill:
    """技能：清单（frontmatter）+ instructions（正文）。"""
    name: str
    description: str
    instructions: str
    version: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    path: Optional[Path] = None


def _parse_skill_md(content: str) -> tuple[Dict[str, Any], str]:
    """解析 SKILL.md：返回 (frontmatter_dict, body)。"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        return {}, content.strip()
    fm_raw, body = match.group(1), match.group(2)
    frontmatter: Dict[str, Any] = {}
    try:
        import yaml
        frontmatter = yaml.safe_load(fm_raw) or {}
    except Exception:
        # 简单回退：解析 key: value 行
        for line in fm_raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k and v.startswith("[") and v.endswith("]"):
                    frontmatter[k] = [x.strip().strip('"\'') for x in v[1:-1].split(",")]
                else:
                    frontmatter[k] = v
    return frontmatter, body.strip()


class SkillLoader:
    """
    扫描若干技能根目录，解析 SKILL.md，缓存为 name -> Skill。
    提供 get_skill(name)、get_skills_by_tag(tag)、get_skills_by_triggers(query)、list_skills()。
    """

    def __init__(self, roots: Optional[List[Path]] = None):
        if roots is None:
            roots = [Path(__file__).parent.parent.parent / "skills"]
        self._roots = [Path(r) for r in roots]
        self._by_name: Dict[str, Skill] = {}
        self._load_all()

    def _load_all(self) -> None:
        for root in self._roots:
            if not root.exists():
                continue
            for sub in root.iterdir():
                if sub.is_dir():
                    skill_file = sub / "SKILL.md"
                    if skill_file.exists():
                        try:
                            content = skill_file.read_text(encoding="utf-8")
                            fm, body = _parse_skill_md(content)
                            name = fm.get("name") or sub.name
                            desc = fm.get("description") or ""
                            skill = Skill(
                                name=name,
                                description=desc,
                                instructions=body,
                                version=fm.get("version"),
                                author=fm.get("author"),
                                tags=fm.get("tags") or [],
                                triggers=fm.get("triggers") or [],
                                prerequisites=fm.get("prerequisites") or [],
                                path=sub,
                            )
                            self._by_name[name] = skill
                        except Exception:
                            pass

    def get_skill(self, name: str) -> Optional[Skill]:
        return self._by_name.get(name)

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        return [s for s in self._by_name.values() if tag in (s.tags or [])]

    def get_skills_by_triggers(self, query: str) -> List[Skill]:
        """根据 query 是否包含 trigger 关键词匹配；trigger 匹配的技能优先。"""
        q = (query or "").lower()
        with_trigger = []
        with_tag = []
        for s in self._by_name.values():
            for t in s.triggers or []:
                if t.lower() in q:
                    with_trigger.append(s)
                    break
            else:
                for t in s.tags or []:
                    if t.lower() in q:
                        with_tag.append(s)
                        break
        return with_trigger + with_tag

    def list_skills(self) -> List[Skill]:
        return list(self._by_name.values())
