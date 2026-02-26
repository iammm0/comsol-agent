"""TUI 桥接：从 stdin 读 JSON 行，调用 agent.actions，向 stdout 写 JSON 行。供 Bun OpenTUI 前端通过子进程调用。"""
import json
import sys
from pathlib import Path
from typing import Any

from agent.actions import (
    do_run,
    do_plan,
    do_exec_from_file,
    do_demo,
    do_doctor,
    do_context_show,
    do_context_get_summary,
    do_context_set_summary,
    do_context_history,
    do_context_stats,
    do_context_clear,
    do_ollama_ping,
    do_config_save,
)
from agent.events import EventBus, Event, EventType
from agent.executor.java_api_controller import JavaAPIController
from agent.utils.context_manager import get_all_models_from_context, get_context_manager


def _reply(ok: bool, message: str, **extra: Any) -> None:
    payload: dict = {"ok": ok, "message": message, **extra}
    line = json.dumps(_json_safe(payload), ensure_ascii=False) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


def _json_safe(obj: Any) -> Any:
    """将对象转为 JSON 可序列化形式。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def _emit_event(event: Event) -> None:
    """将事件序列化为 JSON 行写入 stdout。"""
    payload = {
        "_event": True,
        "type": event.type.value,
        "data": _json_safe(event.data),
        "iteration": event.iteration,
    }
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    sys.stdout.write(line)
    sys.stdout.flush()


def _handle(req: dict[str, Any]) -> None:
    cmd = (req.get("cmd") or "").strip()
    if not cmd:
        _reply(False, "缺少 cmd")
        return

    try:
        if cmd == "run":
            event_bus = EventBus()
            event_bus.subscribe_all(_emit_event)

            try:
                ok, msg = do_run(
                    user_input=(req.get("input") or "").strip(),
                    output=req.get("output") or None,
                    use_react=req.get("use_react", True),
                    no_context=req.get("no_context", False),
                    conversation_id=req.get("conversation_id") or None,
                    backend=req.get("backend") or None,
                    api_key=req.get("api_key") or None,
                    base_url=req.get("base_url") or None,
                    ollama_url=req.get("ollama_url") or None,
                    model=req.get("model") or None,
                    skip_check=req.get("skip_check", False),
                    verbose=req.get("verbose", False),
                    event_bus=event_bus,
                )
                _reply(ok, msg)
            except Exception as e:
                _emit_event(Event(type=EventType.ERROR, data={"message": str(e)}))
                _reply(False, str(e))
            return

        if cmd == "plan":
            out_path = req.get("output_path")
            path = Path(out_path) if out_path else None
            ok, msg = do_plan(
                user_input=(req.get("input") or "").strip(),
                output_path=path,
                verbose=req.get("verbose", False),
            )
            _reply(ok, msg)
            return

        if cmd == "exec":
            path_str = (req.get("path") or "").strip()
            if not path_str:
                _reply(False, "缺少 path")
                return
            path = Path(path_str)
            if not path.exists():
                _reply(False, f"文件不存在: {path}")
                return
            ok, msg = do_exec_from_file(
                plan_file=path,
                output=req.get("output") or None,
                code_only=req.get("code_only", False),
                verbose=req.get("verbose", False),
            )
            _reply(ok, msg)
            return

        if cmd == "demo":
            ok, msg = do_demo(verbose=req.get("verbose", False))
            _reply(ok, msg)
            return

        if cmd == "doctor":
            ok, msg = do_doctor(verbose=req.get("verbose", False))
            _reply(ok, msg)
            return

        if cmd == "context_show":
            ok, msg = do_context_show(conversation_id=req.get("conversation_id") or None)
            _reply(ok, msg)
            return

        if cmd == "context_get_summary":
            ok, msg = do_context_get_summary(conversation_id=req.get("conversation_id") or None)
            _reply(ok, msg)
            return

        if cmd == "context_set_summary":
            text = (req.get("text") or "").strip()
            ok, msg = do_context_set_summary(
                conversation_id=req.get("conversation_id") or None,
                text=text,
            )
            _reply(ok, msg)
            return

        if cmd == "ollama_ping":
            ok, msg = do_ollama_ping(ollama_url=req.get("ollama_url") or "")
            _reply(ok, msg)
            return

        if cmd == "context_history":
            limit = req.get("limit", 10)
            ok, msg = do_context_history(limit=limit, conversation_id=req.get("conversation_id") or None)
            _reply(ok, msg)
            return

        if cmd == "context_stats":
            ok, msg = do_context_stats(conversation_id=req.get("conversation_id") or None)
            _reply(ok, msg)
            return

        if cmd == "context_clear":
            ok, msg = do_context_clear(conversation_id=req.get("conversation_id") or None)
            _reply(ok, msg)
            return

        if cmd == "config_save":
            config = req.get("config")
            if isinstance(config, dict):
                ok, msg = do_config_save(config)
            else:
                ok, msg = False, "缺少 config"
            _reply(ok, msg)
            return

        if cmd == "model_preview":
            path_str = (req.get("path") or req.get("model_path") or "").strip()
            if not path_str:
                _reply(False, "缺少 path 或 model_path")
                return
            if not Path(path_str).exists():
                _reply(False, "模型文件不存在", image_base64=None)
                return
            try:
                ctrl = JavaAPIController()
                width = int(req.get("width") or 640)
                height = int(req.get("height") or 480)
                result = ctrl.export_model_preview(path_str, width=width, height=height)
                ok = result.get("status") == "success"
                _reply(ok, result.get("message", ""), image_base64=result.get("image_base64"))
            except Exception as e:
                _reply(False, str(e), image_base64=None)
            return

        if cmd == "models_list":
            limit = int(req.get("limit") or 50)
            try:
                models = get_all_models_from_context(limit=limit)
                _reply(True, "ok", models=models)
            except Exception as e:
                _reply(False, str(e), models=[])
            return

        if cmd == "conversation_delete":
            conversation_id = (req.get("conversation_id") or "").strip()
            if not conversation_id:
                _reply(False, "缺少 conversation_id", deleted_paths=[])
                return
            try:
                cm = get_context_manager(conversation_id=conversation_id)
                deleted_paths = cm.delete_conversation_and_models()
                _reply(True, "已删除对话及其关联的 COMSOL 模型", deleted_paths=deleted_paths)
            except Exception as e:
                _reply(False, str(e), deleted_paths=[])
            return

        _reply(False, f"未知命令: {cmd}")
    except Exception as e:
        _reply(False, str(e))


def main() -> None:
    """从 stdin 按行读 JSON，处理并写一行 JSON 到 stdout。"""
    if sys.stdin.isatty():
        sys.stderr.write("tui-bridge: 请通过管道或子进程调用，不要直接交互运行\n")
        sys.exit(1)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _reply(False, f"JSON 解析错误: {e}")
            continue
        _handle(req)


if __name__ == "__main__":
    main()
