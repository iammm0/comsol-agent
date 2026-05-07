"""把 mph-agent 的 clarifying_questions/answers 接到 ``AskUserRuntime``。

mph-agent 现在有两种触发澄清的入口：
1. ``ReasoningEngine`` 在 understand_and_plan 时返回 ``ClarifyingQuestion``；
   桌面端把用户回答以 ``ClarifyingAnswer`` 的形式回传，再次调用 ReActAgent。
2. 用户直接在桌面端输入对话，希望让 LLM 调用某个外部 ask-user 工具时，需要离线
   回放（CI / 自动化复现）。

现在两条路径都可以经过 ``AskUserRuntime``：
- ``seed_ask_user_runtime``: 把 ``clarifying_answers`` 列表转成 ``QueuedUserAnswer``
  写入 ``.port_sessions/ask_user_runtime.json``；
- ``resolve_clarifying_answer``: 当 LocalCodingAgent 在 dispatcher 内部触发
  ask_user 工具时，从已落盘的队列里直接消费。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, List, Optional

from agent.clawcode.ask_user_runtime import (
    AskUserResponse,
    AskUserRuntime,
    QueuedUserAnswer,
)
from agent.utils.logger import get_logger

logger = get_logger(__name__)


def _to_payload(answer: Any) -> Optional[dict]:
    """把多种来源的"用户回答"统一成 ``QueuedUserAnswer.from_dict`` 期望的字典。"""

    if isinstance(answer, dict):
        return dict(answer)
    if hasattr(answer, "model_dump"):
        try:
            return answer.model_dump(mode="json")
        except Exception:
            pass
    if hasattr(answer, "dict"):
        try:
            return answer.dict()
        except Exception:
            pass
    return None


def seed_ask_user_runtime(
    cwd: Path,
    clarifying_answers: Iterable[Any],
) -> AskUserRuntime:
    """把 clarifying_answers 灌入 AskUserRuntime 状态文件。

    每条回答会以 ``question_id`` 优先匹配；若 ``selected_option_ids`` 为空，
    则把 ``content`` 当作自由文本回答。
    """

    runtime = AskUserRuntime.from_workspace(cwd.resolve())
    queued: List[QueuedUserAnswer] = list(runtime.queued_answers)
    appended = 0

    for raw in clarifying_answers or []:
        payload = _to_payload(raw)
        if not payload:
            continue
        question_id = (payload.get("question_id") or payload.get("id") or "").strip() or None
        question = (payload.get("question") or "").strip() or None
        # 兼容 mph-agent ClarifyingAnswer：selected_option_ids + content
        answer_text = ""
        selected = payload.get("selected_option_ids") or payload.get("answers") or []
        if isinstance(selected, list) and selected:
            answer_text = ", ".join(str(item) for item in selected if str(item).strip())
        if not answer_text:
            content = (payload.get("content") or payload.get("answer") or "").strip()
            answer_text = content
        if not answer_text:
            continue
        entry = QueuedUserAnswer.from_dict(
            {
                "answer": answer_text,
                "question_id": question_id,
                "question": question,
                "match": "exact" if question else "contains",
                "consume": True,
            }
        )
        if entry is None:
            continue
        queued.append(entry)
        appended += 1

    if appended:
        runtime.queued_answers = tuple(queued)
        try:
            runtime._persist_state()  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            logger.warning("写入 ask_user_runtime 状态失败：%s", exc)
    return runtime


def resolve_clarifying_answer(
    cwd: Path,
    *,
    question: str,
    question_id: Optional[str] = None,
    header: Optional[str] = None,
) -> Optional[AskUserResponse]:
    """从队列中消费一条匹配的回答，未命中返回 None（不抛异常）。"""

    runtime = AskUserRuntime.from_workspace(cwd.resolve())
    try:
        return runtime.answer(
            question=question,
            question_id=question_id,
            header=header,
        )
    except LookupError:
        return None
