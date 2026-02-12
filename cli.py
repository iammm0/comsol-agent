"""CLI 入口模块：依赖组装 + 调用 run 函数，子命令通过 get_agent 获取实例。"""
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON

from agent.dependencies import get_agent, get_context_manager, get_settings
from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_generator import JavaGenerator
from agent.utils.env_check import validate_environment, check_environment, print_check_result
from agent.utils.logger import setup_logging, get_logger
from schemas.geometry import GeometryPlan

app = typer.Typer(help="COMSOL Multiphysics Agent CLI")
console = Console()
logger = get_logger(__name__)


def _check_env_before_run() -> bool:
    """运行前环境检查"""
    is_valid, error_msg = validate_environment()
    if not is_valid:
        console.print(f"\n[red]{error_msg}[/red]")
        console.print("\n[yellow]提示:[/yellow] 请配置以下环境变量或创建 .env 文件:")
        console.print("  - DASHSCOPE_API_KEY: 通义千问 API Key")
        console.print("  - COMSOL_JAR_PATH: COMSOL JAR 文件路径")
        console.print("  - JAVA_HOME: Java 安装路径")
        console.print("  - MODEL_OUTPUT_DIR: 模型输出目录（可选，默认为安装目录下的 models）")
        console.print("\n运行 [cyan]comsol-agent doctor[/cyan] 查看详细诊断信息")
        return False
    return True


@app.command()
def run(
    input_text: str = typer.Argument(..., help="自然语言描述的几何建模需求"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="输出文件名（不含路径）"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="显示详细日志"),
    skip_check: bool = typer.Option(False, "--skip-check", help="跳过环境检查"),
    no_context: bool = typer.Option(False, "--no-context", help="不使用上下文记忆"),
    backend: Optional[str] = typer.Option(None, "--backend", help="LLM 后端 (dashscope/openai/openai-compatible/ollama)，覆盖配置"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API Key（覆盖配置）"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API 基础 URL（用于 openai/openai-compatible）"),
    ollama_url: Optional[str] = typer.Option(None, "--ollama-url", help="Ollama 服务地址（仅用于 ollama 后端）"),
    model: Optional[str] = typer.Option(None, "--model", help="模型名称，覆盖配置"),
    use_react: bool = typer.Option(True, "--react/--no-react", help="使用 ReAct 架构（默认启用）"),
    max_iterations: int = typer.Option(10, "--max-iterations", help="ReAct 最大迭代次数"),
):
    """主入口：接收自然语言并创建 COMSOL 模型"""
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
            console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
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
            console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
            return 0
        
    except Exception as e:
        logger.error(f"创建模型失败: {e}")
        
        # 保存失败的对话记录
        context_manager.add_conversation(
            user_input=input_text,
            success=False,
            error=str(e)
        )
        
        console.print(f"\n[red]❌ 错误: {e}[/red]")
        return 1


@app.command()
def plan(
    input_text: str = typer.Argument(..., help="自然语言描述的几何建模需求"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="输出 JSON 文件路径"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="显示详细日志"),
):
    """仅执行 Planner：解析自然语言为结构化 JSON"""
    setup_logging("DEBUG" if verbose else "INFO")

    try:
        planner = get_agent("planner")
        plan = planner.parse(input_text)
        
        plan_dict = plan.to_dict()
        
        if output:
            output.write_text(json.dumps(plan_dict, ensure_ascii=False, indent=2), encoding="utf-8")
            console.print(f"[green]✅ 计划已保存到: {output}[/green]")
        else:
            console.print(JSON(json.dumps(plan_dict, ensure_ascii=False)))
        
        return 0
        
    except Exception as e:
        logger.error(f"解析失败: {e}")
        console.print(f"[red]❌ 错误: {e}[/red]")
        return 1


@app.command()
def exec(
    plan_file: Path = typer.Argument(..., help="GeometryPlan JSON 文件路径"),
    output: Optional[str] = typer.Option(None, "-o", "--output", help="输出文件名（不含路径）"),
    code_only: bool = typer.Option(False, "--code-only", help="仅生成 Java 代码，不执行"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="显示详细日志"),
):
    """仅执行 Executor：根据 JSON 计划创建模型或生成代码"""
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
            console.print(f"[green]✅ 模型已生成: {model_path}[/green]")
        
        return 0
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        console.print(f"[red]❌ 错误: {e}[/red]")
        return 1


@app.command()
def demo(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="显示详细日志"),
):
    """演示功能：运行示例"""
    setup_logging("DEBUG" if verbose else "INFO")
    
    demo_cases = [
        "创建一个宽1米、高0.5米的矩形",
        "在原点放置一个半径为0.3米的圆",
        "创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)",
    ]
    
    console.print("[bold]COMSOL Agent 演示[/bold]\n")
    
    for i, case in enumerate(demo_cases, 1):
        console.print(f"[cyan]示例 {i}:[/cyan] {case}")
        try:
            planner = get_agent("planner")
            plan = planner.parse(case)
            console.print(f"  [green]✅ 解析成功: {len(plan.shapes)} 个形状[/green]")
            console.print(f"  模型名称: {plan.model_name}, 单位: {plan.units}")
        except Exception as e:
            console.print(f"  [red]❌ 解析失败: {e}[/red]")
        console.print()
    
    return 0


@app.command()
def doctor(
    verbose: bool = typer.Option(False, "-v", "--verbose", help="显示详细日志"),
):
    """诊断功能：检查环境配置"""
    setup_logging("DEBUG" if verbose else "INFO")

    console.print("[bold]COMSOL Agent 环境诊断[/bold]\n")
    status = get_settings().show_config_status()
    console.print("[dim]各后端配置状态: %s[/dim]\n" % status)

    result = check_environment()
    print_check_result(result)

    return 0 if result.is_valid() else 1


@app.command()
def context(
    show: bool = typer.Option(False, "--show", help="显示上下文摘要"),
    history: bool = typer.Option(False, "--history", help="显示对话历史"),
    stats: bool = typer.Option(False, "--stats", help="显示统计信息"),
    clear: bool = typer.Option(False, "--clear", help="清除对话历史"),
    limit: int = typer.Option(10, "--limit", help="显示历史记录数量"),
):
    """上下文管理：查看和管理对话历史"""
    context_manager = get_context_manager()
    
    if clear:
        if typer.confirm("确定要清除所有对话历史吗？"):
            context_manager.clear_history()
            console.print("[green]✅ 对话历史已清除[/green]")
        else:
            console.print("[yellow]已取消[/yellow]")
        return 0
    
    if stats:
        stats_data = context_manager.get_stats()
        console.print("[bold]上下文统计[/bold]\n")
        console.print(f"总对话数: {stats_data['total_conversations']}")
        console.print(f"成功: {stats_data['successful']}")
        console.print(f"失败: {stats_data['failed']}")
        if stats_data['recent_shapes']:
            console.print(f"最近使用的形状: {', '.join(stats_data['recent_shapes'])}")
        if stats_data['preferences']:
            console.print(f"用户偏好: {stats_data['preferences']}")
        return 0
    
    if history:
        history_list = context_manager.get_recent_history(limit)
        console.print(f"[bold]最近 {len(history_list)} 条对话历史[/bold]\n")
        for i, entry in enumerate(history_list, 1):
            timestamp = entry.get('timestamp', '')[:19]  # 只显示日期和时间
            user_input = entry.get('user_input', '')[:60]
            success = entry.get('success', True)
            status = "[green]✅[/green]" if success else "[red]❌[/red]"
            console.print(f"{i}. {status} [{timestamp}] {user_input}...")
        return 0
    
    if show or not any([show, history, stats, clear]):
        # 默认显示摘要
        summary = context_manager.load_summary()
        if summary:
            console.print("[bold]上下文摘要[/bold]\n")
            console.print(summary.summary)
            console.print(f"\n[dim]最后更新: {summary.last_updated[:19]}[/dim]")
        else:
            console.print("[yellow]暂无上下文摘要[/yellow]")
        return 0
    
    return 0


if __name__ == "__main__":
    app()
