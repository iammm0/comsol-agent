"""JSON CLI exposing COMSOL operations for embedded claw-code."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_api_controller import (
    OFFICIAL_COMSOL_API_INDEX_URL,
    JavaAPIController,
)
from schemas.geometry import GeometryPlan
from schemas.material import MaterialPlan
from schemas.physics import PhysicsPlan
from schemas.study import StudyPlan
from schemas.task import GlobalDefinitionPlan


KNOWN_CONTROLLER_PAYLOADS = {
    "add_materials": {"material_plan": MaterialPlan},
    "add_physics": {"physics_plan": PhysicsPlan},
    "configure_study": {"study_plan": StudyPlan},
    "define_global_parameters": {"definitions": "global_definitions"},
}


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Expose mph-agent COMSOL operations as JSON for claw-code."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog = subparsers.add_parser("catalog", help="List native and official COMSOL operations")
    catalog.add_argument("--query")
    catalog.add_argument("--limit", type=int, default=200)
    catalog.add_argument("--offset", type=int, default=0)
    catalog.add_argument("--include-official", action="store_true")
    catalog.add_argument("--refresh", action="store_true")

    call = subparsers.add_parser("call", help="Call a JavaAPIController operation by name")
    call.add_argument("operation", nargs="?")
    _add_payload_args(call)

    create = subparsers.add_parser("create-model", help="Create a model from a GeometryPlan")
    _add_payload_args(create)

    official = subparsers.add_parser("official", help="Invoke an instance method from COMSOL Java API")
    official.add_argument("--model-path")
    official.add_argument("--method")
    official.add_argument("--target-path")
    _add_payload_args(official)

    official_static = subparsers.add_parser(
        "official-static", help="Invoke a static method from COMSOL Java API"
    )
    official_static.add_argument("--class-name")
    official_static.add_argument("--method")
    _add_payload_args(official_static)

    index = subparsers.add_parser("official-index", help="Fetch the COMSOL 6.3 official API index")
    index.add_argument("--url", default=OFFICIAL_COMSOL_API_INDEX_URL)
    index.add_argument("--refresh", action="store_true")
    index.add_argument("--limit", type=int, default=200)

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        result = _run(args)
    except Exception as exc:
        result = {"status": "error", "message": str(exc)}
        _print_json(result)
        return 1

    _print_json(result)
    return 0 if result.get("status") != "error" else 1


def _add_payload_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--payload-json", help="Inline JSON payload")
    parser.add_argument("--payload-file", help="Path to a JSON payload file; '-' reads stdin")


def _run(args: argparse.Namespace) -> Dict[str, Any]:
    controller = JavaAPIController()
    if args.command == "catalog":
        if args.include_official:
            controller.register_official_api_wrappers(refresh=bool(args.refresh))
        return controller.get_ops_catalog(
            query=args.query,
            limit=int(args.limit),
            offset=int(args.offset),
        )

    if args.command == "official-index":
        entries = controller.fetch_official_api_entries(url=args.url, refresh=bool(args.refresh))
        return {
            "status": "success",
            "source_url": args.url,
            "total": len(entries),
            "items": entries[: max(0, int(args.limit))],
        }

    if args.command == "create-model":
        payload = _load_payload(args)
        plan_data = payload.get("geometry_plan") or payload.get("plan") or payload
        output_filename = payload.get("output_filename") or payload.get("model_name") or "model.mph"
        output_dir = payload.get("output_dir")
        plan = GeometryPlan.model_validate(plan_data)
        path = COMSOLRunner().create_model_from_plan(
            plan,
            output_filename=output_filename,
            output_dir=Path(output_dir) if output_dir else None,
        )
        return {"status": "success", "message": "模型创建成功", "model_path": str(path)}

    if args.command == "call":
        payload = _load_payload(args)
        operation = args.operation or payload.pop("operation", None)
        if not operation or not isinstance(operation, str):
            return {"status": "error", "message": "call 需要 operation"}
        kwargs = payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else payload
        return _call_controller(controller, operation, kwargs)

    if args.command == "official":
        payload = _load_payload(args)
        model_path = args.model_path or payload.get("model_path")
        method = args.method or payload.get("method") or payload.get("method_name")
        target_path = _json_arg(args.target_path) if args.target_path else payload.get("target_path")
        return controller.invoke_official_api(
            model_path=model_path,
            method_name=method,
            args=payload.get("args") or [],
            target_path=target_path,
        )

    if args.command == "official-static":
        payload = _load_payload(args)
        class_name = args.class_name or payload.get("class_name")
        method = args.method or payload.get("method") or payload.get("method_name")
        return controller.invoke_official_static_api(
            class_name=class_name,
            method_name=method,
            args=payload.get("args") or [],
        )

    return {"status": "error", "message": f"未知命令: {args.command}"}


def _call_controller(
    controller: JavaAPIController, operation: str, kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    if operation.startswith("_"):
        return {"status": "error", "message": f"不允许调用私有操作: {operation}"}
    method = getattr(controller, operation, None)
    if method is None or not callable(method):
        return {"status": "error", "message": f"未知 COMSOL 操作: {operation}"}

    coerced = dict(kwargs or {})
    for field, schema in KNOWN_CONTROLLER_PAYLOADS.get(operation, {}).items():
        if field not in coerced:
            continue
        coerced[field] = _coerce_payload(coerced[field], schema)
    return method(**coerced)


def _coerce_payload(value: Any, schema: Any) -> Any:
    if schema == "global_definitions":
        return [
            item if isinstance(item, GlobalDefinitionPlan) else GlobalDefinitionPlan.model_validate(item)
            for item in (value or [])
        ]
    if hasattr(schema, "model_validate"):
        return value if isinstance(value, schema) else schema.model_validate(value)
    return value


def _load_payload(args: argparse.Namespace) -> Dict[str, Any]:
    raw = "{}"
    if getattr(args, "payload_json", None):
        raw = args.payload_json
    elif getattr(args, "payload_file", None):
        if args.payload_file == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(args.payload_file).read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("payload 必须是 JSON object")
    return parsed


def _json_arg(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _print_json(result: Dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
