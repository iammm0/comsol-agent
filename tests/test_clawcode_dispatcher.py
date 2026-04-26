"""Tests for embedded claw-code COMSOL dispatcher."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

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
    dispatcher = ClawCodeComsolDispatcher(project_root=tmp_path)
    dispatcher.settings.claw_code_max_turns = 7
    dispatcher.settings.claw_code_timeout_seconds = 3
    dispatcher.settings.claw_code_model = "test-model"
    dispatcher.settings.claw_code_base_url = "http://127.0.0.1:8000/v1"
    dispatcher.settings.claw_code_api_key = "token"
    return dispatcher


def _run_result(final_output, *, stop_reason=None):
    return SimpleNamespace(
        final_output=final_output,
        stop_reason=stop_reason,
        turns=1,
        tool_calls=2,
    )


def test_dispatch_builds_embedded_agent_and_env(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)
    captured = {}

    class _FakeAgent:
        def __init__(self, model_config, runtime_config):
            captured["model_config"] = model_config
            captured["runtime_config"] = runtime_config

        def run(self, prompt):
            captured["prompt"] = prompt
            captured["env_during_run"] = os.environ.get("MPH_AGENT_ROOT")
            return _run_result(
                json.dumps({"status": "success", "message": "ok", "model_path": "/tmp/a.mph"})
            )

    monkeypatch.setattr("agent.executor.clawcode_dispatcher.LocalCodingAgent", _FakeAgent)

    result = dispatcher.dispatch(
        _plan(tmp_path), _step(), {"parameters": {}}, target_output_path="/tmp/a.mph"
    )

    assert result["status"] == "success"
    assert captured["model_config"].model == "test-model"
    assert captured["runtime_config"].cwd == tmp_path.resolve()
    assert captured["runtime_config"].permissions.allow_shell_commands is True
    assert captured["runtime_config"].permissions.allow_file_write is True
    assert captured["env_during_run"] == str(tmp_path.resolve())
    assert "target_output_path" in captured["prompt"]
    assert "python -m agent.executor.comsol_ops_cli" in captured["prompt"]
    assert "https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/api/index.html" in captured["prompt"]


def test_dispatch_returns_error_for_agent_exception(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    class _FailingAgent:
        def __init__(self, model_config, runtime_config):
            pass

        def run(self, prompt):
            raise RuntimeError("bad")

    monkeypatch.setattr("agent.executor.clawcode_dispatcher.LocalCodingAgent", _FailingAgent)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert result["details"]["exception"] == "RuntimeError"


def test_dispatch_returns_error_for_stop_reason(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    class _StoppedAgent:
        def __init__(self, model_config, runtime_config):
            pass

        def run(self, prompt):
            return _run_result("partial", stop_reason="max_turns")

    monkeypatch.setattr("agent.executor.clawcode_dispatcher.LocalCodingAgent", _StoppedAgent)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert result["details"]["stop_reason"] == "max_turns"


def test_dispatch_returns_error_for_invalid_json(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    class _FakeAgent:
        def __init__(self, model_config, runtime_config):
            pass

        def run(self, prompt):
            return _run_result("not json")

    monkeypatch.setattr("agent.executor.clawcode_dispatcher.LocalCodingAgent", _FakeAgent)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert "JSON" in result["message"]


def test_dispatch_returns_error_for_json_error_status(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    class _FakeAgent:
        def __init__(self, model_config, runtime_config):
            pass

        def run(self, prompt):
            return _run_result('```json\n{"status":"error","message":"comsol failed"}\n```')

    monkeypatch.setattr("agent.executor.clawcode_dispatcher.LocalCodingAgent", _FakeAgent)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert result["message"] == "comsol failed"


def test_dispatch_rejects_invalid_status(monkeypatch, tmp_path):
    dispatcher = _dispatcher(tmp_path)

    class _FakeAgent:
        def __init__(self, model_config, runtime_config):
            pass

        def run(self, prompt):
            return _run_result(json.dumps({"status": "done", "message": "bad"}))

    monkeypatch.setattr("agent.executor.clawcode_dispatcher.LocalCodingAgent", _FakeAgent)

    result = dispatcher.dispatch(_plan(tmp_path), _step(), {})

    assert result["status"] == "error"
    assert "status" in result["message"]
