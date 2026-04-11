"""Helpers for managing local and online skill-library metadata."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from agent.skills.loader import SkillLoader, _parse_skill_md
from agent.utils.config import get_project_root

ONLINE_SKILL_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "comsol-3d",
        "name": "COMSOL 3D Modeling",
        "description": "3D geometry setup, dimension strategy, and model decomposition patterns.",
        "tags": ["comsol", "3d", "geometry"],
        "provider": "GitHub",
        "source_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-3d",
        "homepage_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-3d",
    },
    {
        "id": "comsol-basics",
        "name": "COMSOL Basics",
        "description": "Units, naming, primitive geometry, and base modeling conventions.",
        "tags": ["comsol", "basics", "units"],
        "provider": "GitHub",
        "source_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-basics",
        "homepage_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-basics",
    },
    {
        "id": "comsol-exceptions",
        "name": "COMSOL Exceptions",
        "description": "Troubleshooting patterns for common COMSOL runtime and workflow failures.",
        "tags": ["comsol", "diagnostics", "exceptions"],
        "provider": "GitHub",
        "source_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-exceptions",
        "homepage_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-exceptions",
    },
    {
        "id": "comsol-materials",
        "name": "COMSOL Materials",
        "description": "Material selection, parameterization, and property completeness guidance.",
        "tags": ["comsol", "materials", "properties"],
        "provider": "GitHub",
        "source_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-materials",
        "homepage_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-materials",
    },
    {
        "id": "comsol-physics",
        "name": "COMSOL Physics",
        "description": "Physics interface choice, coupling strategy, and boundary-condition guidance.",
        "tags": ["comsol", "physics", "multiphysics"],
        "provider": "GitHub",
        "source_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-physics",
        "homepage_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-physics",
    },
    {
        "id": "comsol-workflow",
        "name": "COMSOL Workflow",
        "description": "End-to-end modeling workflow patterns from planning to solve and export.",
        "tags": ["comsol", "workflow", "study"],
        "provider": "GitHub",
        "source_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-workflow",
        "homepage_url": "https://github.com/iammm0/mph-agent/tree/main/skills/comsol-workflow",
    },
]


def get_skills_root() -> Path:
    """Return the repo-local skill library root."""

    return get_project_root() / "skills"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _slugify(value: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", (value or "").strip(), flags=re.UNICODE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-_")
    return slug.lower() or "skill"


def _split_csv(values: Optional[Iterable[str] | str]) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = re.split(r"[,\n;，；]+", values)
    else:
        raw = list(values)
    seen: set[str] = set()
    cleaned: List[str] = []
    for item in raw:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def _skill_preview(text: str, limit: int = 180) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _skill_record_from_loader_skill(root: Path, skill: Any) -> Dict[str, Any]:
    skill_path = Path(skill.path).resolve() if skill.path else root / skill.name
    skill_file = skill_path / "SKILL.md"
    updated_at = None
    if skill_file.exists():
        updated_at = datetime.fromtimestamp(
            skill_file.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return {
        "id": skill_path.name,
        "name": skill.name,
        "slug": skill_path.name,
        "description": skill.description or "",
        "preview": _skill_preview(skill.instructions),
        "tags": list(skill.tags or []),
        "triggers": list(skill.triggers or []),
        "author": skill.author or "",
        "version": skill.version or "",
        "path": str(skill_path),
        "skill_file": str(skill_file),
        "updated_at": updated_at,
    }


def _skill_record_from_dir(root: Path, skill_dir: Path) -> Dict[str, Any]:
    resolved_dir = Path(skill_dir).resolve()
    loader = SkillLoader(roots=[root])
    for skill in loader.list_skills():
        if skill.path and Path(skill.path).resolve() == resolved_dir:
            return _skill_record_from_loader_skill(root, skill)

    skill_file = resolved_dir / "SKILL.md"
    fm: Dict[str, Any] = {}
    body = ""
    if skill_file.exists():
        fm, body = _parse_skill_md(skill_file.read_text(encoding="utf-8"))
    updated_at = None
    if skill_file.exists():
        updated_at = datetime.fromtimestamp(
            skill_file.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return {
        "id": resolved_dir.name,
        "name": str(fm.get("name") or resolved_dir.name),
        "slug": resolved_dir.name,
        "description": str(fm.get("description") or ""),
        "preview": _skill_preview(body),
        "tags": list(fm.get("tags") or []),
        "triggers": list(fm.get("triggers") or []),
        "author": str(fm.get("author") or ""),
        "version": str(fm.get("version") or ""),
        "path": str(resolved_dir),
        "skill_file": str(skill_file),
        "updated_at": updated_at,
    }


def list_local_skill_libraries(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return repo-local skill libraries."""

    skills_root = Path(root or get_skills_root()).resolve()
    if not skills_root.exists():
        return []
    loader = SkillLoader(roots=[skills_root])
    items = [
        _skill_record_from_loader_skill(skills_root, skill)
        for skill in loader.list_skills()
    ]
    items.sort(
        key=lambda item: (
            item.get("updated_at") or "",
            item.get("name") or "",
        ),
        reverse=True,
    )
    return items


def _ensure_unique_dir(parent: Path, preferred_name: str) -> Path:
    base_slug = _slugify(preferred_name)
    candidate = parent / base_slug
    index = 2
    while candidate.exists():
        candidate = parent / f"{base_slug}-{index}"
        index += 1
    return candidate


def _build_skill_markdown(
    *,
    name: str,
    description: str,
    tags: List[str],
    triggers: List[str],
) -> str:
    safe_name = json.dumps(name.strip(), ensure_ascii=False)
    safe_description = json.dumps(description.strip(), ensure_ascii=False)
    tags_text = json.dumps(tags, ensure_ascii=False)
    triggers_text = json.dumps(triggers, ensure_ascii=False)
    return (
        "---\n"
        f"name: {safe_name}\n"
        f"description: {safe_description}\n"
        f"tags: {tags_text}\n"
        f"triggers: {triggers_text}\n"
        "version: \"0.1.0\"\n"
        "author: \"local\"\n"
        "---\n\n"
        "# 使用场景\n\n"
        f"{description.strip() or '请在这里描述这个技能库要解决的问题。'}\n\n"
        "# 规则\n\n"
        "- 说明适用的建模场景和边界条件。\n"
        "- 说明需要优先遵守的工程约束。\n"
        "- 说明输出结果应包含哪些结构化信息。\n\n"
        "# 示例\n\n"
        "- 输入：\n"
        "- 输出：\n"
    )


def create_local_skill_library(
    name: str,
    *,
    description: str = "",
    tags: Optional[Iterable[str] | str] = None,
    triggers: Optional[Iterable[str] | str] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a new local skill-library directory with a starter SKILL.md."""

    display_name = (name or "").strip()
    if not display_name:
        raise ValueError("技能库名称不能为空")

    skills_root = Path(root or get_skills_root()).resolve()
    skills_root.mkdir(parents=True, exist_ok=True)

    dest_dir = _ensure_unique_dir(skills_root, display_name)
    skill_file = dest_dir / "SKILL.md"
    tag_list = _split_csv(tags)
    trigger_list = _split_csv(triggers)
    desc = description.strip() or f"{display_name} 的本地技能库"

    dest_dir.mkdir(parents=True, exist_ok=False)
    skill_file.write_text(
        _build_skill_markdown(
            name=display_name,
            description=desc,
            tags=tag_list,
            triggers=trigger_list,
        ),
        encoding="utf-8",
    )
    return {"item": _skill_record_from_dir(skills_root, dest_dir), "created_at": _utc_now_iso()}


def _copy_skill_dir(source_dir: Path, dest_dir: Path) -> None:
    shutil.copytree(source_dir, dest_dir)


def _copy_single_skill_file(source_file: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(source_file, dest_dir / "SKILL.md")


def import_skill_library(source_path: str, *, root: Optional[Path] = None) -> Dict[str, Any]:
    """Import an existing skill directory or a standalone SKILL.md file."""

    raw_source = (source_path or "").strip()
    if not raw_source:
        raise ValueError("缺少待导入的技能库路径")

    source = Path(raw_source).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"技能库路径不存在: {source}")

    skills_root = Path(root or get_skills_root()).resolve()
    skills_root.mkdir(parents=True, exist_ok=True)

    if _is_relative_to(source, skills_root):
        raise ValueError("该技能库已经位于本地 skills 目录中")

    if source.is_dir():
        skill_file = source / "SKILL.md"
        if not skill_file.exists():
            raise ValueError("导入目录中缺少 SKILL.md")
        dest_dir = _ensure_unique_dir(skills_root, source.name)
        _copy_skill_dir(source, dest_dir)
    else:
        if source.name.lower() != "skill.md":
            raise ValueError("当前仅支持导入目录或单个 SKILL.md 文件")
        dest_dir = _ensure_unique_dir(skills_root, source.parent.name or source.stem)
        _copy_single_skill_file(source, dest_dir)

    return {
        "item": _skill_record_from_dir(skills_root, dest_dir),
        "imported_from": str(source),
        "imported_at": _utc_now_iso(),
    }


def list_online_skill_library(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return a curated read-only online skill catalog."""

    local_items = {item["slug"] for item in list_local_skill_libraries(root)}
    items: List[Dict[str, Any]] = []
    for entry in ONLINE_SKILL_CATALOG:
        item = dict(entry)
        item["installed"] = item["id"] in local_items
        items.append(item)
    return items
