from agent.skills.api_catalog_builder import ApiCapabilityEntry, build_api_capability_entries
from agent.skills.injector import RUNTIME_MARKER, SkillInjector
from agent.skills.loader import SkillLoader


def test_build_api_capability_entries_includes_native_and_wrapper(monkeypatch):
    class _DummyController:
        def get_ops_catalog(self, limit=10000, offset=0):
            return {
                "items": [
                    {
                        "category": "网格",
                        "label": "生成网格",
                        "invoke_mode": "native",
                        "recommended_action": "generate_mesh",
                        "params_schema": {"mesh": "object"},
                        "examples": [{"action": "generate_mesh"}],
                    },
                    {
                        "category": "网格",
                        "label": "api_meshsequence_automeshsize",
                        "invoke_mode": "wrapper",
                        "recommended_action": "call_official_api",
                        "params_schema": {"args": "any[]?"},
                        "examples": [
                            {
                                "action": "api_meshsequence_automeshsize",
                                "owner": "com.comsol.model.MeshSequence",
                                "method_name": "autoMeshSize",
                            }
                        ],
                    },
                ]
            }

    monkeypatch.setattr(
        "agent.skills.api_catalog_builder.JavaAPIController",
        _DummyController,
    )

    entries = build_api_capability_entries()

    assert len(entries) == 2
    assert any(entry.invoke_mode == "native" for entry in entries)
    assert any(entry.invoke_mode == "wrapper" for entry in entries)
    assert any(entry.recommended_action == "generate_mesh" for entry in entries)
    assert any(entry.wrapper_name == "api_meshsequence_automeshsize" for entry in entries)


def test_skill_injector_adds_runtime_capabilities_block():
    injector = SkillInjector(loader=SkillLoader(roots=[]), top_k=3, doc_top_k=0)
    injector._api_entries = [
        ApiCapabilityEntry(
            name="native:generate_mesh",
            title="生成网格",
            description="Native ActionExecutor mesh operation.",
            invoke_mode="native",
            category="网格",
            recommended_action="generate_mesh",
            params_schema={"mesh": "object"},
            examples=[{"action": "generate_mesh"}],
            keywords=["网格", "mesh", "边界层"],
        ),
        ApiCapabilityEntry(
            name="api_meshsequence_automeshsize",
            title="网格 wrapper: api_meshsequence_automeshsize",
            description="Wrapper for mesh auto size.",
            invoke_mode="wrapper",
            category="网格",
            recommended_action="call_official_api",
            params_schema={"args": "any[]?"},
            examples=[{"action": "api_meshsequence_automeshsize"}],
            wrapper_name="api_meshsequence_automeshsize",
            owner="com.comsol.model.MeshSequence",
            method_name="autoMeshSize",
            keywords=["网格", "mesh", "边界层"],
        ),
    ]

    prompt = injector.inject_into_prompt("设置边界层网格", "user prompt")

    assert RUNTIME_MARKER in prompt
    assert "generate_mesh" in prompt
    assert "api_meshsequence_automeshsize" in prompt
    assert injector.last_used_capabilities()
