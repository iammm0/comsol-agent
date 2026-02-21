"""无 Typer 依赖的纯函数：供 TUI 与 CLI 子命令共用的 do_run、do_plan、do_exec 等。"""
import json
from pathlib import Path
from typing import Optional, Tuple, Any

from agent.dependencies import get_agent, get_context_manager, get_settings
from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_generator import JavaGenerator
from agent.utils.env_check import check_environment
from agent.utils.logger import setup_logging, get_logger
from schemas.geometry import GeometryPlan

logger = get_logger(__name__)


def _ensure_logging(verbose: bool = False) -> None:
    setup_logging("DEBUG" if verbose else "INFO")


def do_run(
    user_input: str,
    output: Optional[str] = None,
    use_react: bool = True,
    no_context: bool = False,
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None,
    max_iterations: int = 10,
    skip_check: bool = False,
    verbose: bool = False,
) -> Tuple[bool, str]:
    """执行默认模式：自然语言 -> 创建模型。返回 (成功, 要显示的文本)。"""
    _ensure_logging(verbose)
    from agent.utils.env_check import validate_environment

    if not skip_check:
        is_valid, error_msg = validate_environment()
        if not is_valid:
            return False, f"环境检查未通过: {error_msg}"

    context_manager = get_context_manager()
    try:
        if use_react:
            core = get_agent(
                "core",
                backend=backend,
                api_key=api_key,
                base_url=base_url,
                ollama_url=ollama_url,
                model=model,
                max_iterations=max_iterations,
            )
            model_path = core.run(user_input, output)
            context_manager.add_conversation(
                user_input=user_input,
                plan={"architecture": "react"},
                model_path=str(model_path),
                success=True,
            )
            return True, f"模型已生成: {model_path}"
        else:
            context = None if no_context else context_manager.get_context_for_planner()
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
            return True, f"模型已生成: {model_path}"
    except Exception as e:
        logger.exception("do_run 失败")
        context_manager.add_conversation(user_input=user_input, success=False, error=str(e))
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


def do_context_show() -> Tuple[bool, str]:
    """上下文摘要。"""
    cm = get_context_manager()
    summary = cm.load_summary()
    if summary:
        return True, f"{summary.summary}\n\n最后更新: {summary.last_updated[:19]}"
    return True, "暂无上下文摘要"


def do_context_history(limit: int = 10) -> Tuple[bool, str]:
    """对话历史。"""
    cm = get_context_manager()
    history_list = cm.get_recent_history(limit)
    lines = [f"最近 {len(history_list)} 条对话历史\n"]
    for i, entry in enumerate(history_list, 1):
        ts = entry.get("timestamp", "")[:19]
        ui = (entry.get("user_input") or "")[:60]
        ok = entry.get("success", True)
        st = "成功" if ok else "失败"
        lines.append(f"{i}. [{st}] {ts} {ui}...")
    return True, "\n".join(lines)


def do_context_stats() -> Tuple[bool, str]:
    """上下文统计。"""
    cm = get_context_manager()
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


def do_context_clear() -> Tuple[bool, str]:
    """清除对话历史。"""
    get_context_manager().clear_history()
    return True, "对话历史已清除"
