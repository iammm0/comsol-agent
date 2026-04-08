"""Tests for JavaAPIController extensions added for staged workflow."""

from pathlib import Path

import pytest

from agent.executor import java_api_controller as jac
from agent.executor.java_api_controller import JavaAPIController


@pytest.fixture
def controller(monkeypatch):
    class _DummyRunner:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(jac, "COMSOLRunner", _DummyRunner)
    return JavaAPIController()


def test_define_global_parameters_validation_fails_before_comsol_call(controller, tmp_path):
    model_path = tmp_path / "demo.mph"
    model_path.write_text("dummy", encoding="utf-8")

    res = controller.define_global_parameters(
        str(model_path),
        [
            {"name": "L", "value": "0.1[m]"},
            {"name": "L", "value": "0.2[m]"},
        ],
    )
    assert res["status"] == "error"
    assert res["message"] == "global definitions validation failed"
    assert isinstance(res.get("details"), list)


def test_ops_catalog_contains_categories_and_wrapper_entries(controller):
    controller._official_api_wrappers = {
        "api_geomsequence_run": {
            "owner": "com.comsol.model.GeomSequence",
            "method": "run",
        }
    }

    res = controller.get_ops_catalog(limit=200, offset=0)
    assert res["status"] == "success"
    assert "categories" in res
    assert len(res["categories"]) == 8
    assert any(item.get("invoke_mode") == "native" for item in res.get("items", []))
    assert any(item.get("invoke_mode") == "wrapper" for item in res.get("items", []))


def test_extract_model_operation_case_rejects_missing_file(controller, tmp_path):
    missing = tmp_path / "missing.mph"
    res = controller.extract_model_operation_case(str(missing))
    assert res["status"] == "error"
    assert "not found" in res["message"]
