"""Run mph-agent end-to-end repeatedly and save actionable failure logs.

This is a developer regression harness for the desktop agent backend. It does
not patch source code by itself; use it to reproduce the next blocking error,
fix the code, then run again until a complete model is produced.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.core.events import Event, EventBus  # noqa: E402
from agent.run.actions import do_run  # noqa: E402
from agent.utils.config import get_settings  # noqa: E402


DEFAULT_PROMPT = (
    "创建一个完整的二维稳态传热 COMSOL 模型；如有澄清问题，请使用推荐默认选项继续，不要停下来询问。"
    "几何为 1 m x 0.5 m 的矩形板，"
    "材料为铝，左边界温度 373.15 K，右边界温度 293.15 K，"
    "上下边界绝热；生成普通网格，配置稳态研究并求解，保存 mph 文件。"
)


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_jsonl(path: Path, item: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False, default=_json_default) + "\n")


def _latest_run_end(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(events):
        if item.get("type") == "run_end":
            data = item.get("data")
            return data if isinstance(data, dict) else None
    return None


def _latest_plan_end(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(events):
        if item.get("type") == "plan_end":
            data = item.get("data")
            return data if isinstance(data, dict) else None
    return None


def _recommended_clarifying_answers(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract recommended choices from PLAN_END clarification payloads.

    The desktop event currently serializes Pydantic clarifying questions as
    strings, so this parser intentionally supports both dict and string shapes.
    """

    plan_end = _latest_plan_end(events) or {}
    questions = plan_end.get("clarifying_questions")
    if not isinstance(questions, list):
        return []

    answers: list[dict[str, Any]] = []
    for question in questions:
        if isinstance(question, dict):
            qid = question.get("id")
            options = question.get("options") or []
            selected = [
                opt.get("id")
                for opt in options
                if isinstance(opt, dict) and opt.get("recommended") and opt.get("id")
            ]
            if not selected and options and isinstance(options[0], dict) and options[0].get("id"):
                selected = [options[0]["id"]]
        else:
            text = str(question)
            q_match = re.search(r"id='([^']+)'", text)
            qid = q_match.group(1) if q_match else None
            selected = []
            for opt_text in re.findall(r"ClarifyingOption\((.*?)\)", text):
                if "recommended=True" not in opt_text:
                    continue
                opt_match = re.search(r"id='([^']+)'", opt_text)
                if opt_match:
                    selected.append(opt_match.group(1))
            if not selected:
                opt_match = re.search(r"ClarifyingOption\(id='([^']+)'", text)
                if opt_match:
                    selected = [opt_match.group(1)]

        if qid and selected:
            answers.append(
                {
                    "question_id": qid,
                    "selected_option_ids": selected,
                    "supplement_text": "",
                }
            )
    return answers


def run_once(
    *,
    prompt: str,
    attempt: int,
    phase: str,
    log_dir: Path,
    workspace_dir: Path,
    max_iterations: int,
    skip_check: bool,
    clarifying_answers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    event_bus = EventBus()
    events: list[dict[str, Any]] = []
    events_file = log_dir / f"attempt-{attempt:02d}-{phase}-events.jsonl"
    if events_file.exists():
        events_file.unlink()

    def on_event(event: Event) -> None:
        item = {
            "timestamp": event.timestamp.isoformat(),
            "type": str(event.type.value if hasattr(event.type, "value") else event.type),
            "iteration": event.iteration,
            "data": event.data,
        }
        events.append(item)
        _write_jsonl(events_file, item)

    event_bus.subscribe_all(on_event)

    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        raw_ok, message, needs_clarification = do_run(
            prompt,
            workspace_dir=str(workspace_dir),
            use_react=True,
            no_context=True,
            conversation_id=None,
            max_iterations=max_iterations,
            skip_check=skip_check,
            verbose=True,
            event_bus=event_bus,
            clarifying_answers=clarifying_answers,
        )
        exception = None
    except Exception as exc:  # do_run should normally catch, but keep harness robust.
        raw_ok = False
        message = str(exc)
        needs_clarification = False
        exception = traceback.format_exc()

    run_end = _latest_run_end(events)
    plan_end = _latest_plan_end(events) or {}
    model_path = None
    run_success = None
    if run_end:
        model_path = run_end.get("model_path")
        run_success = run_end.get("success")
    if plan_end.get("requires_clarification"):
        needs_clarification = True
    ok = bool(raw_ok and (run_success is not False) and not needs_clarification)

    summary = {
        "attempt": attempt,
        "started_at": started_at,
        "raw_ok": raw_ok,
        "run_success": run_success,
        "ok": ok,
        "message": message,
        "needs_clarification": needs_clarification,
        "model_path": model_path,
        "model_exists": bool(model_path and Path(str(model_path)).exists()),
        "events_file": str(events_file),
        "exception": exception,
        "recommended_clarifying_answers": _recommended_clarifying_answers(events),
    }
    (log_dir / f"attempt-{attempt:02d}-{phase}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--max-iterations", type=int, default=12)
    parser.add_argument("--skip-check", action="store_true")
    parser.add_argument("--log-dir", default=str(ROOT / "logs" / "agent-build-loop"))
    parser.add_argument("--workspace-dir", default=str(ROOT / "models" / "agent-build-loop"))
    args = parser.parse_args()

    settings = get_settings()
    log_dir = Path(args.log_dir).resolve()
    workspace_dir = Path(args.workspace_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config_snapshot = {
        "llm_backend": settings.llm_backend,
        "model": settings.get_model_for_backend(settings.llm_backend),
        "comsol_jar_path": settings.comsol_jar_path,
        "model_output_dir": settings.model_output_dir,
        "workspace_dir": str(workspace_dir),
    }
    (log_dir / "config.json").write_text(
        json.dumps(config_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    final_summary: dict[str, Any] | None = None
    for attempt in range(1, max(1, args.attempts) + 1):
        summary = run_once(
            prompt=args.prompt,
            attempt=attempt,
            phase="plan",
            log_dir=log_dir,
            workspace_dir=workspace_dir,
            max_iterations=args.max_iterations,
            skip_check=bool(args.skip_check),
        )
        if summary["needs_clarification"]:
            answers = summary.get("recommended_clarifying_answers") or []
            if answers:
                summary = run_once(
                    prompt=args.prompt,
                    attempt=attempt,
                    phase="run",
                    log_dir=log_dir,
                    workspace_dir=workspace_dir,
                    max_iterations=args.max_iterations,
                    skip_check=bool(args.skip_check),
                    clarifying_answers=answers,
                )
        final_summary = summary
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))
        if summary["ok"] and summary["model_exists"] and not summary["needs_clarification"]:
            return 0

    return 0 if final_summary and final_summary["ok"] and final_summary["model_exists"] else 1


if __name__ == "__main__":
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
