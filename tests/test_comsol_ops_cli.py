"""Tests for the COMSOL operations JSON CLI used by claw-code."""

import json
from pathlib import Path

from agent.executor import comsol_ops_cli


class _DummyController:
    def __init__(self):
        self.registered = False

    def register_official_api_wrappers(self, refresh=False):
        self.registered = True
        return {"status": "success", "refresh": refresh}

    def get_ops_catalog(self, query=None, limit=200, offset=0):
        return {
            "status": "success",
            "query": query,
            "limit": limit,
            "offset": offset,
            "items": [{"label": "官方 API 兜底调用"}],
        }

    def fetch_official_api_entries(self, url, refresh=False):
        return [{"owner": "com.comsol.model.Model", "method_name": "save", "url": url}]

    def list_model_tree(self, model_path):
        return {"status": "success", "model_path": model_path, "tree": {}}

    def define_global_parameters(self, model_path, definitions, save_to_path=None):
        return {
            "status": "success",
            "model_path": model_path,
            "count": len(definitions),
            "saved_path": save_to_path,
        }

    def invoke_official_api(self, model_path, method_name, args=None, target_path=None):
        return {
            "status": "success",
            "model_path": model_path,
            "method": method_name,
            "args": args,
            "target_path": target_path,
        }

    def invoke_official_static_api(self, class_name, method_name, args=None):
        return {
            "status": "success",
            "class_name": class_name,
            "method": method_name,
            "args": args,
        }


def _json_from_stdout(capsys):
    return json.loads(capsys.readouterr().out)


def test_catalog_can_include_official_wrappers(monkeypatch, capsys):
    monkeypatch.setattr(comsol_ops_cli, "JavaAPIController", _DummyController)

    rc = comsol_ops_cli.main(["catalog", "--include-official", "--query", "api"])

    assert rc == 0
    out = _json_from_stdout(capsys)
    assert out["status"] == "success"
    assert out["query"] == "api"


def test_call_controller_operation_with_typed_payload(monkeypatch, capsys):
    monkeypatch.setattr(comsol_ops_cli, "JavaAPIController", _DummyController)
    payload = {
        "model_path": "/tmp/in.mph",
        "definitions": [{"name": "L", "value": "1[m]"}],
        "save_to_path": "/tmp/out.mph",
    }

    rc = comsol_ops_cli.main(
        ["call", "define_global_parameters", "--payload-json", json.dumps(payload)]
    )

    assert rc == 0
    out = _json_from_stdout(capsys)
    assert out["status"] == "success"
    assert out["count"] == 1


def test_official_instance_and_static_calls(monkeypatch, capsys):
    monkeypatch.setattr(comsol_ops_cli, "JavaAPIController", _DummyController)

    rc = comsol_ops_cli.main(
        [
            "official",
            "--payload-json",
            json.dumps(
                {
                    "model_path": "/tmp/in.mph",
                    "method": "run",
                    "args": [],
                    "target_path": [{"method": "geom", "args": ["geom1"]}],
                }
            ),
        ]
    )
    assert rc == 0
    assert _json_from_stdout(capsys)["method"] == "run"

    rc = comsol_ops_cli.main(
        [
            "official-static",
            "--payload-json",
            json.dumps(
                {
                    "class_name": "com.comsol.model.util.ModelUtil",
                    "method": "initStandalone",
                    "args": [False],
                }
            ),
        ]
    )
    assert rc == 0
    assert _json_from_stdout(capsys)["class_name"] == "com.comsol.model.util.ModelUtil"


def test_create_model_uses_comsol_runner(monkeypatch, capsys, tmp_path):
    class _DummyRunner:
        def create_model_from_plan(self, plan, output_filename, output_dir=None):
            assert plan.model_name == "demo"
            return Path(output_dir or tmp_path) / output_filename

    monkeypatch.setattr(comsol_ops_cli, "JavaAPIController", _DummyController)
    monkeypatch.setattr(comsol_ops_cli, "COMSOLRunner", _DummyRunner)
    payload = {
        "geometry_plan": {
            "model_name": "demo",
            "dimension": 2,
            "shapes": [{"type": "rectangle", "parameters": {"width": 1, "height": 1}}],
        },
        "output_filename": "demo.mph",
        "output_dir": str(tmp_path),
    }

    rc = comsol_ops_cli.main(["create-model", "--payload-json", json.dumps(payload)])

    assert rc == 0
    out = _json_from_stdout(capsys)
    assert out["status"] == "success"
    assert out["model_path"].endswith("demo.mph")


def test_private_controller_operation_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(comsol_ops_cli, "JavaAPIController", _DummyController)

    rc = comsol_ops_cli.main(["call", "_load_model", "--payload-json", "{}"])

    assert rc == 1
    out = _json_from_stdout(capsys)
    assert out["status"] == "error"
