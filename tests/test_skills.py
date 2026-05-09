"""Skills 单元测试：SkillLoader 解析、SkillInjector 注入。"""
import pytest
from pathlib import Path

from agent.core.events import EventBus, EventType
from agent.skills.api_catalog_builder import ApiCapabilityEntry
from agent.skills.loader import SkillLoader, Skill, _parse_skill_md
from agent.skills.injector import SkillInjector, MARKER


class TestParseSkillMd:
    """SKILL.md 解析（frontmatter + body）"""

    def test_with_frontmatter(self):
        content = """---
name: foo
description: bar
tags: [a, b]
---
# 正文
hello world
"""
        fm, body = _parse_skill_md(content)
        assert fm.get("name") == "foo"
        assert fm.get("description") == "bar"
        assert "正文" in body
        assert "hello world" in body

    def test_without_frontmatter(self):
        content = "no frontmatter\njust body"
        fm, body = _parse_skill_md(content)
        assert fm == {}
        assert "no frontmatter" in body


def _skills_library_root() -> Path:
    return Path(__file__).parent.parent / "agent" / "skills" / "library"


class TestSkillLoader:
    """SkillLoader：扫描 agent/skills/library、按 name/tag/triggers 查询"""

    def test_list_skills(self):
        root = _skills_library_root()
        if not root.exists():
            pytest.skip("agent/skills/library 目录不存在")
        loader = SkillLoader(roots=[root])
        skills = loader.list_skills()
        assert isinstance(skills, list)
        for s in skills:
            assert isinstance(s, Skill)
            assert s.name
            assert hasattr(s, "instructions")
            assert hasattr(s, "triggers")

    def test_get_skill_by_name(self):
        root = _skills_library_root()
        if not root.exists():
            pytest.skip("agent/skills/library 目录不存在")
        loader = SkillLoader(roots=[root])
        # 至少有一个 comsol-basics
        skill = loader.get_skill("comsol-basics")
        if skill:
            assert "矩形" in skill.instructions or "rectangle" in skill.instructions.lower()

    def test_get_skills_by_triggers(self):
        root = _skills_library_root()
        if not root.exists():
            pytest.skip("agent/skills/library 目录不存在")
        loader = SkillLoader(roots=[root])
        skills = loader.get_skills_by_triggers("创建一个矩形，几何")
        assert isinstance(skills, list)
        # 命中 trigger 的应排在前面
        if skills:
            assert any("几何" in s.instructions or "矩形" in s.instructions for s in skills)


class TestSkillInjector:
    """SkillInjector：按 query 匹配技能并注入到 prompt"""

    def test_inject_into_prompt_with_loader(self):
        root = _skills_library_root()
        if not root.exists():
            pytest.skip("agent/skills/library 目录不存在")
        loader = SkillLoader(roots=[root])
        injector = SkillInjector(loader=loader, top_k=2)
        user_prompt = "用户输入：画一个矩形"
        out = injector.inject_into_prompt("画一个矩形", user_prompt)
        assert MARKER in out
        assert "用户输入" in out
        # 应包含技能正文或至少标记
        assert out.strip().startswith(MARKER) or MARKER in out

    def test_inject_into_prompt_empty_loader(self):
        loader = SkillLoader(roots=[])  # 空根目录，无技能
        injector = SkillInjector(loader=loader, top_k=2)
        user_prompt = "hello"
        out = injector.inject_into_prompt("hello", user_prompt)
        assert out == user_prompt

    def test_last_used_skills(self):
        root = _skills_library_root()
        if not root.exists():
            pytest.skip("agent/skills/library 目录不存在")
        injector = SkillInjector(loader=SkillLoader(roots=[root]), top_k=2)
        injector.inject_into_prompt("几何 矩形", "prompt")
        names = injector.last_used_skills()
        assert isinstance(names, list)


def _make_capability_entry(
    name: str,
    *,
    title: str = "",
    keywords=None,
    invoke_mode: str = "wrapper",
    category: str = "geometry",
) -> ApiCapabilityEntry:
    return ApiCapabilityEntry(
        name=name,
        title=title or name,
        description=f"description for {name}",
        invoke_mode=invoke_mode,
        category=category,
        recommended_action="call_official_api",
        params_schema={},
        examples=[],
        wrapper_name=name,
        owner="model",
        method_name=name.replace("api_", ""),
        keywords=list(keywords or []),
    )


class TestCapabilityScanEvents:
    """SkillInjector 在筛选 wrapper 时应通过 EventBus 推送扫描事件，且不破坏向后兼容。"""

    def _seed_entries(self, injector: SkillInjector):
        injector._api_entries = [
            _make_capability_entry(
                "api_create_rectangle",
                title="Create rectangle",
                keywords=["geometry", "rectangle", "矩形"],
                invoke_mode="native",
            ),
            _make_capability_entry(
                "api_set_heat_transfer",
                title="Set heat transfer",
                keywords=["heat", "transfer", "physics"],
            ),
            _make_capability_entry(
                "api_solve_study",
                title="Solve study",
                keywords=["study", "solve"],
            ),
            _make_capability_entry(
                "api_export_results",
                title="Export results",
                keywords=["export", "results"],
            ),
        ]

    def test_emits_full_event_sequence(self):
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))

        injector = SkillInjector(loader=SkillLoader(roots=[]), top_k=2, event_bus=bus)
        self._seed_entries(injector)

        results = injector._search_capability_entries("rectangle 矩形", limit=2)
        assert results, "应至少命中一个候选"

        types = [e.type for e in events]
        assert types[0] == EventType.CAPABILITY_SCAN_START
        assert types[-1] == EventType.CAPABILITY_SCAN_END
        assert EventType.CAPABILITY_SCAN_PROGRESS in types
        assert EventType.CAPABILITY_SCAN_HIT in types

        start = next(e for e in events if e.type == EventType.CAPABILITY_SCAN_START)
        assert start.data["total"] == 4
        assert start.data["mode"] == "keyword"
        assert start.data["query"] == "rectangle 矩形"

        end = next(e for e in events if e.type == EventType.CAPABILITY_SCAN_END)
        assert end.data["total_scanned"] == 4
        assert isinstance(end.data["hits"], list)
        assert end.data["hits"], "end 事件应携带最终入选 hits"
        for hit in end.data["hits"]:
            assert "name" in hit and "score" in hit

        hit_events = [e for e in events if e.type == EventType.CAPABILITY_SCAN_HIT]
        for hit in hit_events:
            assert hit.data.get("matched_terms"), "命中事件必须列出匹配关键字"

    def test_no_event_bus_is_backward_compatible(self):
        injector = SkillInjector(loader=SkillLoader(roots=[]), top_k=2)
        self._seed_entries(injector)
        results = injector._search_capability_entries("solve study", limit=1)
        assert results
        assert results[0].name == "api_solve_study"

    def test_set_event_bus_attaches_lazily(self):
        injector = SkillInjector(loader=SkillLoader(roots=[]), top_k=1)
        self._seed_entries(injector)
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))
        injector.set_event_bus(bus)

        injector._search_capability_entries("export", limit=1)
        types = [e.type for e in events]
        assert EventType.CAPABILITY_SCAN_START in types
        assert EventType.CAPABILITY_SCAN_END in types
