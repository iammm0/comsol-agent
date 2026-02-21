"""CLI 入口模块：无参数即进入全终端交互；有子命令则走 Typer。"""
import sys
import json
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

# 与 py_to_mph_minimal 一致：先加载 .env，再在导入 COMSOL/JVM 相关模块前设置 JAVA_HOME
_cli_root = Path(__file__).resolve().parent
load_dotenv(_cli_root / ".env")
from agent.utils.java_runtime import ensure_java_home_from_venv
ensure_java_home_from_venv(_cli_root)

from agent.dependencies import get_agent, get_context_manager, get_settings
from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_generator import JavaGenerator
from agent.utils.env_check import validate_environment, check_environment, print_check_result
from agent.utils.logger import setup_logging, get_logger
from schemas.geometry import GeometryPlan

app = typer.Typer(help="COMSOL 多物理场仿真 Agent 命令行")

# 统一视觉：深色友好、高对比度
_theme = Theme({
    "success": "bold green",
    "error": "bold red",
    "warn": "bold yellow",
    "info": "cyan",
    "title": "bold cyan",
    "dim": "dim",
})
console = Console(theme=_theme)
logger = get_logger(__name__)


def _is_interactive_invocation() -> bool:
    """无子命令、无全局选项时视为「直接进交互」"""
    args = sys.argv[1:]
    if not args:
        return True
    if len(args) == 1 and args[0] in ("--help", "-h"):
        return False
    return False


def _check_env_before_run() -> bool:
    """运行前环境检查"""
    is_valid, error_msg = validate_environment()
    if not is_valid:
        hint = (
            "请配置环境变量或创建 .env 文件：\n"
            "  • DEEPSEEK_API_KEY / KIMI_API_KEY / OPENAI_COMPATIBLE_*（按所选 LLM 后端）\n"
            "  • COMSOL_JAR_PATH（COMSOL JAR 或 plugins 目录）\n"
            "  • JAVA_HOME（可选，不设则使用内置 JDK 11）\n"
            "  • MODEL_OUTPUT_DIR（可选）\n\n"
            "运行 [cyan]comsol-agent doctor[/cyan] 查看详细诊断"
        )
        console.print(Panel(error_msg, title="[error] 环境配置错误", border_style="red"))
        console.print(Panel(hint, title="[warn] 提示", border_style="yellow"))
        return False
    return True


@app.command()
def run(
    input_text: str = typer.Argument(..., help="自然语言描述的几何建模需求"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="输出模型文件名（不含路径）"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="输出详细日志"),
    skip_check: bool = typer.Option(False, "--skip-check", help="跳过运行前环境检查"),
    no_context: bool = typer.Option(False, "--no-context", help="不使用上下文记忆"),
    backend: Optional[str] = typer.Option(None, "--backend", help="LLM 后端：deepseek / kimi / ollama / openai-compatible（覆盖配置）"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API Key（覆盖配置）"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API 基础 URL（仅 openai-compatible 中转）"),
    ollama_url: Optional[str] = typer.Option(None, "--ollama-url", help="Ollama 服务地址（仅 ollama 后端）"),
    model: Optional[str] = typer.Option(None, "--model", help="模型名称（覆盖配置）"),
    use_react: bool = typer.Option(True, "--react/--no-react", help="是否使用 ReAct 架构（默认启用）"),
    max_iterations: int = typer.Option(10, "--max-iterations", help="ReAct 最大迭代次数"),
):
    """主入口：根据自然语言描述创建 COMSOL 模型"""
    setup_logging("DEBUG" if verbose else "INFO")
    
    # 环境检查
    if not skip_check and not _check_env_before_run():
        return 1
    
    context_manager = get_context_manager()

    try:
        logger.info("开始创建 COMSOL 模型")

        if use_react:
            logger.info("使用 ReAct 架构")
            core = get_agent(
                "core",
                backend=backend,
                api_key=api_key,
                base_url=base_url,
                ollama_url=ollama_url,
                model=model,
                max_iterations=max_iterations,
            )
            model_path = core.run(input_text, output)
            context_manager.add_conversation(
                user_input=input_text,
                plan={"architecture": "react"},
                model_path=str(model_path),
                success=True,
            )
            console.print(Panel(f"[success]✅ 模型已生成[/success]\n{model_path}", border_style="green"))
            return 0
        else:
            logger.info("使用传统架构")
            context = None if no_context else context_manager.get_context_for_planner()
            if context:
                logger.debug("使用上下文: %s...", context[:100])
            planner = get_agent(
                "planner",
                backend=backend,
                api_key=api_key,
                base_url=base_url,
                ollama_url=ollama_url,
                model=model,
            )
            plan = planner.parse(input_text, context=context)
            logger.info("解析成功: %s 个形状", len(plan.shapes))
            runner = COMSOLRunner()
            model_path = runner.create_model_from_plan(plan, output)
            context_manager.add_conversation(
                user_input=input_text,
                plan=plan.to_dict(),
                model_path=str(model_path),
                success=True,
            )
            console.print(Panel(f"[success]✅ 模型已生成[/success]\n{model_path}", border_style="green"))
            return 0
        
    except Exception as e:
        logger.error(f"创建模型失败: {e}")
        context_manager.add_conversation(
            user_input=input_text,
            success=False,
            error=str(e)
        )
        console.print(Panel(str(e), title="[error] 错误", border_style="red"))
        return 1


@app.command()
def plan(
    input_text: str = typer.Argument(..., help="自然语言描述的几何建模需求"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="将解析结果写入的 JSON 文件路径"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="输出详细日志"),
):
    """仅执行规划器：将自然语言解析为结构化 JSON 计划"""
    setup_logging("DEBUG" if verbose else "INFO")

    try:
        planner = get_agent("planner")
        plan = planner.parse(input_text)
        
        plan_dict = plan.to_dict()
        
        if output:
            output.write_text(json.dumps(plan_dict, ensure_ascii=False, indent=2), encoding="utf-8")
            console.print(Panel(f"[success]✅ 计划已保存[/success]\n{output}", border_style="green"))
        else:
            console.print(Panel(JSON(json.dumps(plan_dict, ensure_ascii=False)), title="[title] 解析结果", border_style="cyan"))
        
        return 0
        
    except Exception as e:
        logger.error(f"解析失败: {e}")
        console.print(Panel(str(e), title="[error] 错误", border_style="red"))
        return 1


@app.command()
def exec(
    plan_file: Path = typer.Argument(..., help="几何计划 JSON 文件路径"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="输出模型文件名（不含路径）"),
    code_only: bool = typer.Option(False, "--code-only", help="只生成 Java 代码，不调用 COMSOL 执行"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="输出详细日志"),
):
    """仅执行执行器：根据 JSON 计划创建模型或生成 Java 代码"""
    setup_logging("DEBUG" if verbose else "INFO")
    
    try:
        # 加载计划
        plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
        plan = GeometryPlan.from_dict(plan_data)
        
        if code_only:
            # 仅生成 Java 代码
            generator = JavaGenerator()
            java_code = generator.generate_from_plan(plan, output)
            console.print(java_code)
        else:
            # 创建 COMSOL 模型
            runner = COMSOLRunner()
            model_path = runner.create_model_from_plan(plan, output)
            console.print(Panel(f"[success]✅ 模型已生成[/success]\n{model_path}", border_style="green"))
        
        return 0
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        console.print(Panel(str(e), title="[error] 错误", border_style="red"))
        return 1


@app.command()
def demo(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="输出详细日志"),
):
    """演示：运行内置几何建模示例"""
    setup_logging("DEBUG" if verbose else "INFO")
    
    demo_cases = [
        "创建一个宽1米、高0.5米的矩形",
        "在原点放置一个半径为0.3米的圆",
        "创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)",
    ]
    
    table = Table(title="COMSOL Agent 演示", border_style="cyan", title_style="bold cyan")
    table.add_column("示例", style="cyan", width=8)
    table.add_column("描述", style="white")
    table.add_column("结果", style="green")
    for i, case in enumerate(demo_cases, 1):
        try:
            planner = get_agent("planner")
            plan = planner.parse(case)
            result = f"✅ {len(plan.shapes)} 个形状 · {plan.model_name} · {plan.units}"
        except Exception as e:
            result = f"❌ {e}"
        table.add_row(str(i), case, result)
    console.print(Panel(table, border_style="cyan"))
    return 0


@app.command()
def doctor(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="输出详细日志"),
):
    """诊断：检查 COMSOL、Java、LLM 等环境配置"""
    setup_logging("DEBUG" if verbose else "INFO")

    status = get_settings().show_config_status()
    st = Table.grid(expand=True)
    st.add_column(style="cyan")
    for k, v in status.items():
        st.add_row(f"  {k}: [green]已配置[/green]" if v else f"  {k}: [dim]未配置[/dim]")
    console.print(Panel(st, title="[title] 后端配置状态", border_style="cyan"))
    console.print()

    result = check_environment()
    print_check_result(result)

    return 0 if result.is_valid() else 1


@app.command()
def context(
    show: bool = typer.Option(False, "--show", help="输出上下文摘要"),
    history: bool = typer.Option(False, "--history", help="输出对话历史列表"),
    stats: bool = typer.Option(False, "--stats", help="输出统计信息"),
    clear: bool = typer.Option(False, "--clear", help="清除全部对话历史"),
    limit: int = typer.Option(10, "--limit", help="历史记录条数（用于 --history）"),
):
    """上下文管理：查看或清除对话历史与摘要"""
    context_manager = get_context_manager()
    
    if clear:
        if typer.confirm("确定要清除所有对话历史吗？"):
            context_manager.clear_history()
            console.print(Panel("[success]✅ 对话历史已清除[/success]", border_style="green"))
        else:
            console.print("[warn]已取消[/warn]")
        return 0

    if stats:
        stats_data = context_manager.get_stats()
        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column(style="cyan")
        t.add_column(style="white")
        t.add_row("总对话数", str(stats_data["total_conversations"]))
        t.add_row("成功", str(stats_data["successful"]))
        t.add_row("失败", str(stats_data["failed"]))
        if stats_data.get("recent_shapes"):
            t.add_row("最近形状", ", ".join(stats_data["recent_shapes"]))
        if stats_data.get("preferences"):
            t.add_row("用户偏好", str(stats_data["preferences"]))
        console.print(Panel(t, title="[title] 上下文统计", border_style="cyan"))
        return 0

    if history:
        history_list = context_manager.get_recent_history(limit)
        t = Table(title=f"最近 {len(history_list)} 条对话", border_style="cyan", title_style="bold cyan")
        t.add_column("", width=4, style="dim")
        t.add_column("状态", width=4)
        t.add_column("时间", width=20, style="dim")
        t.add_column("输入", style="white")
        for i, entry in enumerate(history_list, 1):
            ts = entry.get("timestamp", "")[:19]
            inp = (entry.get("user_input", "") or "")[:50]
            ok = entry.get("success", True)
            t.add_row(str(i), "[green]✅[/green]" if ok else "[red]❌[/red]", ts, inp)
        console.print(Panel(t, border_style="cyan"))
        return 0

    if show or not any([show, history, stats, clear]):
        summary = context_manager.load_summary()
        if summary:
            body = summary.summary + f"\n\n[dim]最后更新: {summary.last_updated[:19]}[/dim]"
            console.print(Panel(body, title="[title] 上下文摘要", border_style="cyan"))
        else:
            console.print(Panel("暂无上下文摘要", title="[warn] 上下文[/warn]", border_style="yellow"))
        return 0
    
    return 0


def main() -> None:
    """入口：无参数进全终端交互，否则走 Typer 子命令。"""
    if _is_interactive_invocation():
        from agent.tui import run_tui
        run_tui()
    else:
        app()


if __name__ == "__main__":
    main()
