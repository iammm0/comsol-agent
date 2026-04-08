"""Tests for discuss/plan staged workflow guards and clarification loop."""

from __future__ import annotations

from agent.run.discussion_mode import DiscussionModeHandler
from agent.run.plan_mode import PlanModeHandler
from schemas.task import DiscussionCard


class _DummyContextManager:
    def __init__(self) -> None:
        self._discussion = None
        self._plan = None
        self.plan_readable = ""

    def load_discussion_card(self):
        return self._discussion

    def save_discussion_card(self, payload):
        self._discussion = payload

    def load_plan(self):
        return self._plan

    def save_plan(self, payload):
        self._plan = payload

    def save_plan_readable(self, text: str):
        self.plan_readable = text


def test_discussion_requires_explicit_finalize_keyword():
    ctx = _DummyContextManager()
    handler = DiscussionModeHandler(context_manager=ctx)

    _reply, card = handler.process("传热原理，目标温度低于350K，未知对流系数")
    assert card["finalized"] is False

    _reply2, finalized = handler.process("进入规划")
    assert finalized["finalized"] is True

    reply3, still_finalized = handler.process("再补充一个风险项")
    assert still_finalized["finalized"] is True
    assert "finalized" in reply3


def test_plan_rejects_when_discussion_not_finalized():
    ctx = _DummyContextManager()
    ctx.save_discussion_card(DiscussionCard(finalized=False).model_dump(mode="json"))
    handler = PlanModeHandler(context_manager=ctx, get_agent=lambda *_args, **_kwargs: None)

    reply, plan, confirmed, questions = handler.process("开始规划")
    assert plan is None
    assert confirmed is False
    assert questions is None
    assert "finalized" in reply


def test_plan_returns_clarifying_questions_when_unresolved():
    ctx = _DummyContextManager()
    ctx.save_discussion_card(DiscussionCard(finalized=True).model_dump(mode="json"))
    ctx.save_plan(
        {
            "discussion_card_ref": "card-1",
            "clarifying_questions": [
                {
                    "id": "q1",
                    "text": "请确认边界条件",
                    "type": "single",
                    "options": [
                        {
                            "id": "opt_recommended",
                            "label": "使用推荐值",
                            "value": "recommended",
                            "recommended": True,
                        }
                    ],
                }
            ],
            "unresolved_clarifications": ["q1"],
            "answered_clarifications": [],
            "plan_confirmed": False,
        }
    )
    handler = PlanModeHandler(context_manager=ctx, get_agent=lambda *_args, **_kwargs: None)

    reply, plan, confirmed, questions = handler.process("继续规划")
    assert confirmed is False
    assert plan is not None
    assert isinstance(questions, list) and len(questions) == 1
    assert "澄清" in reply
    assert ctx.plan_readable


def test_plan_answers_close_loop_and_confirm():
    ctx = _DummyContextManager()
    ctx.save_discussion_card(DiscussionCard(finalized=True).model_dump(mode="json"))
    ctx.save_plan(
        {
            "discussion_card_ref": "card-1",
            "clarifying_questions": [
                {
                    "id": "q1",
                    "text": "请确认边界条件",
                    "type": "single",
                    "options": [
                        {
                            "id": "opt_recommended",
                            "label": "使用推荐值",
                            "value": "recommended",
                            "recommended": True,
                        }
                    ],
                }
            ],
            "unresolved_clarifications": ["q1"],
            "answered_clarifications": [],
            "plan_confirmed": False,
        }
    )
    handler = PlanModeHandler(context_manager=ctx, get_agent=lambda *_args, **_kwargs: None)

    reply, plan, confirmed, questions = handler.process(
        "确认计划",
        clarifying_answers=[
            {
                "question_id": "q1",
                "selected_option_ids": ["opt_recommended"],
            }
        ],
    )

    assert confirmed is True
    assert questions is None
    assert plan is not None
    assert plan["plan_confirmed"] is True
    assert plan["unresolved_clarifications"] == []
    assert "确认" in reply
