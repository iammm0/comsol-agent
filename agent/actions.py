"""无 Typer 依赖的纯函数：供 TUI 与 CLI 子命令共用的 do_run、do_plan、do_exec 等。"""
import json
from pathlib import Path
from typing import Optional, Tuple, Any

from agent.dependencies import get_agent, get_context_manager, get_settings
from agent.events import EventBus
from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_generator import JavaGenerator
from agent.memory_agent import update_conversation_memory
from agent.utils.env_check import check_environment
from agent.utils.logger import setup_logging, get_logger
from schemas.geometry import GeometryPlan

logger = get_logger(__name__)


def _update_memory_after_run(
    conversation_id: Optional[str],
    user_input: str,
    assistant_summary: str,
    success: bool,
) -> None:
    """有 conversation_id 时更新会话记忆；优先 Celery 异步，不可用时同步执行。"""
    if not conversation_id:
        return
    try:
        from agent.memory_tasks import update_memory_task
        update_memory_task.delay(
            conversation_id, user_input, assistant_summary, success
        )
    except Exception:
        update_conversation_memory(
            conversation_id, user_input, assistant_summary, success
        )


def _ensure_logging(verbose: bool = False) -> None:
    setup_logging("DEBUG" if verbose else "INFO")


def do_run(
    user_input: str,
    output: Optional[str] = None,
    use_react: bool = True,
    no_context: bool = False,
    conversation_id: Optional[str] = None,
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None,
    max_iterations: int = 10,
    skip_check: bool = False,
    verbose: bool = False,
    event_bus: Optional[EventBus] = None,
) -> Tuple[bool, str]:
    """执行默认模式：自然语言 -> 创建模型。conversation_id 存在时使用该会话的上下文与摘要。"""
    _ensure_logging(verbose)
    from agent.utils.env_check import validate_environment

    if not skip_check:
        is_valid, error_msg = validate_environment()
        if not is_valid:
            return False, f"环境检查未通过: {error_msg}"

    context_manager = get_context_manager(conversation_id)
    memory_context = None if no_context else context_manager.get_context_for_planner()
    try:
        if use_react:
            output_dir = context_manager.context_dir if conversation_id else None
            if conversation_id:
                context_manager.start_run_log(user_input)
            core = get_agent(
                "core",
                backend=backend,
                api_key=api_key,
                base_url=base_url,
                ollama_url=ollama_url,
                model=model,
                max_iterations=max_iterations,
                event_bus=event_bus,
                context_manager=context_manager if conversation_id else None,
            )
            model_path = core.run(
                user_input,
                output,
                memory_context=memory_context,
                output_dir=output_dir,
            )
            context_manager.add_conversation(
                user_input=user_input,
                plan={"architecture": "react"},
                model_path=str(model_path),
                success=True,
            )
            if conversation_id:
                _update_memory_after_run(
                    conversation_id,
                    user_input,
                    f"模型已生成: {model_path}",
                    True,
                )
            return True, f"模型已生成: {model_path}"
        else:
            context = memory_context
            planner = get_agent(
                "planner",
                backend=backend,
                api_key=api_key,
                base_url=base_url,
                ollama_url=ollama_url,
                model=model,
            )
            plan = planner.parse(user_input, context=context)
            runner = COMSOLRunner()
            model_path = runner.create_model_from_plan(plan, output)
            context_manager.add_conversation(
                user_input=user_input,
                plan=plan.to_dict(),
                model_path=str(model_path),
                success=True,
            )
            if conversation_id:
                _update_memory_after_run(
                    conversation_id,
                    user_input,
                    f"模型已生成: {model_path}",
                    True,
                )
            return True, f"模型已生成: {model_path}"
    except Exception as e:
        logger.exception("do_run 失败")
        context_manager.add_conversation(user_input=user_input, success=False, error=str(e))
        if conversation_id:
            _update_memory_after_run(conversation_id, user_input, str(e), False)
        return False, str(e)


def do_plan(
    user_input: str,
    output_path: Optional[Path] = None,
    verbose: bool = False,
) -> Tuple[bool, str]:
    """计划模式：自然语言 -> JSON。返回 (成功, 要显示的文本)。"""
    _ensure_logging(verbose)
    try:
        planner = get_agent("planner")
        plan = planner.parse(user_input)
        plan_dict = plan.to_dict()
        text = json.dumps(plan_dict, ensure_ascii=False, indent=2)
        if output_path:
            output_path.write_text(text, encoding="utf-8")
            return True, f"计划已保存到: {output_path}\n\n{text}"
        return True, text
    except Exception as e:
        logger.exception("do_plan 失败")
        return False, str(e)


def do_exec_from_file(
    plan_file: Path,
    output: Optional[str] = None,
    code_only: bool = False,
    verbose: bool = False,
) -> Tuple[bool, str]:
    """根据 JSON 计划文件执行：创建模型或仅生成代码。"""
    _ensure_logging(verbose)
    try:
        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
        plan = GeometryPlan.from_dict(plan_data)
        if code_only:
            generator = JavaGenerator()
            code = generator.generate_from_plan(plan, output)
            return True, code
        runner = COMSOLRunner()
        model_path = runner.create_model_from_plan(plan, output)
        return True, f"模型已生成: {model_path}"
    except Exception as e:
        logger.exception("do_exec 失败")
        return False, str(e)


def do_demo(verbose: bool = False) -> Tuple[bool, str]:
    """运行演示用例，返回汇总文本。"""
    _ensure_logging(verbose)
    demo_cases = [
        "创建一个宽1米、高0.5米的矩形",
        "在原点放置一个半径为0.3米的圆",
        "创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)",
        "创建一个3D长方体，宽1米、高0.5米、深0.3米",
        "创建一个半径0.2米、高0.5米的3D圆柱",
    ]
    lines = ["COMSOL Agent 演示\n"]
    planner = get_agent("planner")
    for i, case in enumerate(demo_cases, 1):
        lines.append(f"示例 {i}: {case}")
        try:
            plan = planner.parse(case)
            lines.append(f"  解析成功: {len(plan.shapes)} 个形状, 模型名: {plan.model_name}, 单位: {plan.units}")
        except Exception as e:
            lines.append(f"  解析失败: {e}")
        lines.append("")
    return True, "\n".join(lines)


def do_doctor(verbose: bool = False) -> Tuple[bool, str]:
    """运行环境诊断，返回结果文本。"""
    _ensure_logging(verbose)
    settings = get_settings()
    status = settings.show_config_status()
    result = check_environment()
    lines = [f"各后端配置状态: {status}", ""]
    if result.is_valid():
        lines.append("环境检查通过")
    else:
        lines.append("环境检查失败")
    for e in result.errors:
        lines.append(f"  错误: {e}")
    for w in result.warnings:
        lines.append(f"  警告: {w}")
    for i in result.info:
        lines.append(f"  {i}")
    return result.is_valid(), "\n".join(lines)


def do_context_show(conversation_id: Optional[str] = None) -> Tuple[bool, str]:
    """上下文摘要。conversation_id 存在时查看该会话的摘要。"""
    cm = get_context_manager(conversation_id)
    summary = cm.load_summary()
    if summary:
        return True, f"{summary.summary}\n\n最后更新: {summary.last_updated[:19]}"
    return True, "暂无上下文摘要"


def do_context_get_summary(conversation_id: Optional[str] = None) -> Tuple[bool, str]:
    """仅返回当前会话的摘要原文（供设置页编辑）。"""
    cm = get_context_manager(conversation_id)
    summary = cm.load_summary()
    if summary:
        return True, summary.summary
    return True, ""


def do_context_set_summary(conversation_id: Optional[str], text: str) -> Tuple[bool, str]:
    """设置当前会话的摘要原文（用户编辑记忆）。"""
    if not conversation_id:
        return False, "缺少 conversation_id"
    cm = get_context_manager(conversation_id)
    cm.set_summary_text(text)
    return True, "记忆已保存"


def do_ollama_ping(ollama_url: str) -> Tuple[bool, str]:
    """测试 Ollama 服务连通性。"""
    url = (ollama_url or "").strip()
    if not url:
        return False, "请填写 Ollama 地址"
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    try:
        import requests
        r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            names = [m.get("name", "") for m in models[:5]]
            return True, f"连接成功，可用模型: {', '.join(names) or '无'}"
        return False, f"响应异常: HTTP {r.status_code}"
    except Exception as e:
        return False, f"连接失败: {e}"


def do_context_history(limit: int = 10, conversation_id: Optional[str] = None) -> Tuple[bool, str]:
    """对话历史。"""
    cm = get_context_manager(conversation_id)
    history_list = cm.get_recent_history(limit)
    lines = [f"最近 {len(history_list)} 条对话历史\n"]
    for i, entry in enumerate(history_list, 1):
        ts = entry.get("timestamp", "")[:19]
        ui = (entry.get("user_input") or "")[:60]
        ok = entry.get("success", True)
        st = "成功" if ok else "失败"
        lines.append(f"{i}. [{st}] {ts} {ui}...")
    return True, "\n".join(lines)


def do_context_stats(conversation_id: Optional[str] = None) -> Tuple[bool, str]:
    """上下文统计。"""
    cm = get_context_manager(conversation_id)
    data = cm.get_stats()
    lines = [
        f"总对话数: {data['total_conversations']}",
        f"成功: {data['successful']}",
        f"失败: {data['failed']}",
    ]
    if data.get("recent_shapes"):
        lines.append(f"最近形状: {', '.join(data['recent_shapes'])}")
    if data.get("preferences"):
        lines.append(f"用户偏好: {data['preferences']}")
    return True, "\n".join(lines)


def do_context_clear(conversation_id: Optional[str] = None) -> Tuple[bool, str]:
    """清除对话历史。"""
    get_context_manager(conversation_id).clear_history()
    return True, "对话历史已清除"


def do_config_save(env_updates: Optional[dict] = None) -> Tuple[bool, str]:
    """将配置写入项目根目录的 .env 文件并重载配置，供桌面端保存后同步。"""
    if not env_updates:
        return False, "无配置项"
    from agent.utils.config import get_project_root, reload_settings

    root = get_project_root()
    env_path = root / ".env"
    env_keys = [
        "LLM_BACKEND",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "KIMI_API_KEY",
        "KIMI_MODEL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_MODEL",
        "OLLAMA_URL",
        "OLLAMA_MODEL",
        "COMSOL_JAR_PATH",
    ]
    # 读取已有行
    if env_path.exists():
        lines_out = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines_out = []
    # 键 -> 行索引（只记第一个出现的键）
    key_to_idx: dict[str, int] = {}
    for i, line in enumerate(lines_out):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key not in key_to_idx:
                key_to_idx[key] = i
    # 更新或追加
    for k in env_keys:
        v = env_updates.get(k)
        if v is None:
            continue
        v_str = str(v).strip()
        new_line = f"{k}={v_str}"
        if k in key_to_idx:
            lines_out[key_to_idx[k]] = new_line
        else:
            lines_out.append(new_line)
            key_to_idx[k] = len(lines_out) - 1
    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        reload_settings()
        return True, "配置已保存并已加载，将应用于后续 comsol-agent 调用"
    except Exception as e:
        return False, f"写入 .env 失败: {e}"
