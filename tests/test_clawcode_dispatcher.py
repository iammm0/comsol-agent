"""Tests for claw-code COMSOL subprocess dispatcher."""

import json
import subprocess
from pathlib import Path

from agent.executor.clawcode_dispatcher import ClawCodeComsolDispatcher
from schemas.task import ExecutionStep, ReActTaskPlan


def _plan(tmp_path: Path) -> ReActTaskPlan:
    return ReActTaskPlan(
        task_id="t1",
        model_name="demo",
        user_input="创建模型",
        output_dir=str(tmp_path),
    )


def _step() -> ExecutionStep:
    return ExecutionStep(step_id="s1", step_type="geometry", action="create_geometry")


def _dispatcher(tmp_path: Path) -> ClawCodeComsolDispatcher:
    agent_root = tmp_path / "claw"
    (agent_root / "src").mkdir(parents=True)
    (agent_root / "src" / "main.py").write_text("", encoding="utf-8")
    dispatcher = ClawCodeComsolDispatcher(project_root=tmp_path)
    dispatcher.settings.claw_code_agent_root = str(agent_root)
    dispatcher.settings.claw_code_python_executable = "python3"
    dispatcher.settings.claw_code_max_turns = 7
    dispatcher.settings.claw_code_timeout_seconds = 3
    dispatcher.settings.claw_code_model = "test-model"
    dispatcher.settings.claw_code_base_url = "http://127.0.0.1:8000/v1"
    dispatcher.settings.claw_code_api_key = "token"
    dispatcher.agent_root = agent_root.resolve()
    return dispatcher


def test_dispatch_builds_subprocess_command_and_env(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"status": "success", "message": "ok", "model_path": "/tmp/a.mph"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {"parameters": {}}, target_output_path="/tmp/a.mph")

    assert result["status"] == "success"
    assert captured["cmd"][:4] == ["python3", "-m", "src.main", "agent"]
    assert "--allow-shell" in captured["cmd"]
    assert "--allow-write" in captured["cmd"]
    assert "--max-turns" in captured["cmd"]
    assert "test-model" in captured["cmd"]
    assert captured["cwd"] == str(tmp_path.resolve())
    assert str(dispatcher.agent_root) in captured["env"]["PYTHONPATH"]
    assert captured["env"]["MPH_AGENT_ROOT"] == str(tmp_path.resolve())
    assert "target_output_path" in captured["cmd"][4]


def test_dispatch_returns_error_for_process_failure(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 2, stdout="out", stderr="bad"),
    )

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert result["details"]["returncode"] == 2


def test_dispatch_returns_error_for_timeout(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=3)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert "超时" in result["message"]


def test_dispatch_returns_error_for_invalid_json(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="not json", stderr=""),
    )

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert "JSON" in result["message"]


def test_dispatch_returns_error_for_json_error_status(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd,
            0,
            stdout='```json\n{"status":"error","message":"comsol failed"}\n```',
            stderr="",
        ),
    )

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert result["message"] == "comsol failed"


def test_dispatch_rejects_invalid_status(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"status": "done", "message": "bad"}),
            stderr="",
        ),
    )

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert "status" in result["message"]
