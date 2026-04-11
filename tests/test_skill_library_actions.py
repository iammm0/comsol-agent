from pathlib import Path

from agent.run import actions
import agent.skills.manager as skill_manager


def test_skill_library_create_import_and_list(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    monkeypatch.setattr(skill_manager, "get_skills_root", lambda: skills_root)

    ok, message, created = actions.do_skills_create_local(
        name="Heat Workflow",
        description="Local heat-transfer workflow skill",
        tags=["heat", "workflow"],
        triggers=["散热器", "热应力"],
    )

    assert ok is True
    assert "创建" in message
    created_item = created["item"]
    assert created_item is not None
    assert Path(created_item["skill_file"]).exists()
    assert created_item["name"] == "Heat Workflow"

    external_dir = tmp_path / "external-skill"
    external_dir.mkdir(parents=True, exist_ok=True)
    (external_dir / "SKILL.md").write_text(
        """---
name: Imported Skill
description: Imported from external path
tags: ["imported"]
triggers: ["导入"]
---

# Imported

This is an imported skill.
""",
        encoding="utf-8",
    )

    ok, message, imported = actions.do_skills_import_local(str(external_dir))
    assert ok is True
    assert "导入" in message
    imported_item = imported["item"]
    assert imported_item is not None
    assert Path(imported_item["skill_file"]).exists()
    assert imported_item["name"] == "Imported Skill"

    ok, _, listed = actions.do_skills_list_local()
    assert ok is True
    assert listed["total"] == 2
    names = {item["name"] for item in listed["items"]}
    assert "Heat Workflow" in names
    assert "Imported Skill" in names


def test_skill_library_online_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_manager, "get_skills_root", lambda: tmp_path / "skills")

    ok, message, result = actions.do_skills_list_online()

    assert ok is True
    assert message == "ok"
    assert result["total"] >= 1
    assert any(item["id"] == "comsol-basics" for item in result["items"])
