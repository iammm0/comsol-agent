"""Executor 单元测试：do_exec_from_file、COMSOLRunner/JavaAPIController 依赖（不启动 JVM）。"""
import json
import tempfile
from pathlib import Path

import pytest
from unittest.mock import patch, Mock

from schemas.geometry import GeometryPlan, GeometryShape
from agent.run.actions import do_exec_from_file


@pytest.fixture
def sample_plan():
    return GeometryPlan(
        model_name="test_model",
        units="m",
        shapes=[
            GeometryShape(
                type="rectangle",
                parameters={"width": 1.0, "height": 0.5},
                position={"x": 0.0, "y": 0.0},
                name="rect1",
            )
        ],
    )


@pytest.fixture
def plan_file(sample_plan, tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(sample_plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class TestDoExecFromFile:
    """do_exec_from_file：从 JSON 计划文件创建模型（不启动 JVM）。"""

    def test_do_exec_from_file_success_when_runner_mocked(self, plan_file):
        with patch("agent.run.actions.COMSOLRunner") as mock_runner_cls:
            mock_runner_cls.return_value.create_model_from_plan.return_value = Path("/tmp/out.mph")
            ok, msg = do_exec_from_file(plan_file, output=None, verbose=False)
            assert ok is True
            assert "模型已生成" in msg or "out.mph" in msg
            mock_runner_cls.return_value.create_model_from_plan.assert_called_once()

    def test_do_exec_from_file_invalid_json_fails(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        ok, msg = do_exec_from_file(bad_file, verbose=False)
        assert ok is False
        assert msg

    def test_do_exec_from_file_nonexistent_fails(self, tmp_path):
        ok, msg = do_exec_from_file(tmp_path / "nonexistent.json", verbose=False)
        assert ok is False
        assert msg
