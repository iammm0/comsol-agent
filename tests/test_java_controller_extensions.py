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


def test_infer_category_saveitemparam_is_not_definition():
    """含子串 param 的数据库类名不得误判为「定义」。"""
    cat = JavaAPIController._infer_category(
        "com.comsol.api.database.param.SaveItemParam",
        "assignedTagKeys",
        "api_saveitemparam_assignedtagkeys",
    )
    assert cat == "开发工具"


def test_infer_category_geomsequence_is_geometry():
    cat = JavaAPIController._infer_category(
        "com.comsol.model.GeomSequence",
        "run",
        "api_geomsequence_run",
    )
    assert cat == "几何"


def test_infer_category_parameter_container_is_definition():
    cat = JavaAPIController._infer_category(
        "com.comsol.model.ParameterContainer",
        "param",
        "api_parametercontainer_param",
    )
    assert cat == "定义"


def test_ops_catalog_contains_categories_and_wrapper_entries(controller):
    controller._official_api_wrappers = {
        "api_geomsequence_run": {
            "owner": "com.comsol.model.GeomSequence",
            "method": "run",
        }
    }

    res = controller.get_ops_catalog(limit=200, offset=0, wrappers_only=False)
    assert res["status"] == "success"
    assert "categories" in res
    assert len(res["categories"]) == 8
    assert any(item.get("invoke_mode") == "native" for item in res.get("items", []))
    assert any(item.get("invoke_mode") == "wrapper" for item in res.get("items", []))


def test_ops_catalog_wrappers_only_excludes_native(controller):
    controller._official_api_wrappers = {
        "api_geomsequence_run": {
            "owner": "com.comsol.model.GeomSequence",
            "method": "run",
        }
    }
    res = controller.get_ops_catalog(limit=500, offset=0, wrappers_only=True)
    assert res["status"] == "success"
    items = res.get("items") or []
    assert items
    assert all(item.get("invoke_mode") == "wrapper" for item in items)
    assert any(item.get("label") == "api_geomsequence_run" for item in items)


def test_extract_model_operation_case_rejects_missing_file(controller, tmp_path):
    missing = tmp_path / "missing.mph"
    res = controller.extract_model_operation_case(str(missing))
    assert res["status"] == "error"
    assert "not found" in res["message"]


def test_extract_model_operation_case_builds_sectioned_analysis(controller, tmp_path, monkeypatch):
    model_path = tmp_path / "demo.mph"
    model_path.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(
        controller,
        "list_model_tree",
        lambda _path: {
            "status": "success",
            "tree": {
                "geometries": ["geom1"],
                "materials": ["mat1"],
                "physics": ["ht"],
                "meshes": ["mesh1"],
                "studies": ["std1"],
                "results": ["pg1"],
            },
        },
    )
    monkeypatch.setattr(
        controller,
        "list_global_parameters",
        lambda _path: {
            "status": "success",
            "items": [
                {
                    "name": "L",
                    "value": "10[mm]",
                    "unit": "mm",
                    "description": "channel length",
                }
            ],
        },
    )
    monkeypatch.setattr(
        controller,
        "get_node_tree",
        lambda _path: {
            "status": "success",
            "node_tree": "\n".join(
                [
                    "component comp1",
                    "geometry geom1",
                    "material mat1",
                    "physics ht",
                    "mesh mesh1",
                    "study std1",
                    "result pg1",
                ]
            ),
        },
    )

    res = controller.extract_model_operation_case(str(model_path))

    assert res["status"] == "success"
    case = res["case"]
    assert case["source_model_path"] == str(model_path.resolve())
    assert case["global_definitions"][0]["name"] == "L"
    assert case["geometry_setup"][0]["tag"] == "geom1"
    assert case["material_setup"][0]["tag"] == "mat1"
    assert case["physics_setup"][0]["tag"] == "ht"
    assert case["mesh_setup"][0]["tag"] == "mesh1"
    assert case["study_setup"][0]["tag"] == "std1"
    assert case["postprocess_setup"][0]["tag"] == "pg1"
    assert case["design_intent"]
    assert "原始模型路径" in case["copy_edit_prompt"]
    assert case["context_block"]
