from __future__ import annotations

from agent.utils.context_manager import ContextManager


def test_manual_summary_survives_auto_summary_refresh(tmp_path):
    cm = ContextManager(context_dir=tmp_path / "ctx")

    cm.set_summary_text("- 常用单位 mm\n- 输出优先 CSV")
    cm.add_conversation(
        user_input="创建一个散热片模型",
        assistant_summary="已确认散热片高度和材料范围。",
        plan={
            "units": "mm",
            "shapes": [{"type": "block"}],
        },
        success=True,
    )

    summary = cm.load_summary()
    assert summary is not None
    assert summary.manual_summary == "常用单位 mm\n输出优先 CSV"
    assert "User Memory" in summary.summary
    assert "Auto Summary" in summary.summary
    assert "Preferred unit: mm." in summary.auto_summary


def test_context_for_planner_contains_memory_and_recent_turns(tmp_path):
    cm = ContextManager(context_dir=tmp_path / "ctx")

    cm.set_summary_text("- 参数扫描要保留结果对比")
    cm.add_conversation(
        user_input="先讨论散热器鳍片间距",
        assistant_summary="建议先明确目标温升和对流边界。",
        plan={"units": "mm", "shapes": [{"type": "block"}]},
        success=True,
    )
    cm.save_discussion_card(
        {
            "physical_principles": ["稳态传热"],
            "target_metrics": ["最高温度"],
            "known_inputs": ["fin_gap=3[mm]"],
            "unknowns": ["对流换热系数未定"],
            "candidate_solutions": ["先做参数扫描"],
            "risks": ["网格过粗可能低估温升"],
        }
    )
    cm.save_plan(
        {
            "plan_confirmed": False,
            "unresolved_clarifications": ["q1"],
            "steps": [
                {"description": "建立散热器几何"},
                {"description": "配置稳态传热"},
            ],
        }
    )

    context = cm.get_context_for_planner()
    assert "Long-term memory" in context
    assert "参数扫描要保留结果对比" in context
    assert "Recent dialogue snippets" in context
    assert "Assistant: 建议先明确目标温升和对流边界。" in context
    assert "Current discussion card" in context
    assert "Current plan status" in context
