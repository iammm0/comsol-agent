"""主启动程序 - 用于调试和开发。生产环境推荐直接运行 comsol-agent（无参数）进入全终端交互。"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 与 py_to_mph_minimal 一致：先加载 .env，再在导入 COMSOL/JVM 相关模块前设置 JAVA_HOME
from dotenv import load_dotenv
load_dotenv(project_root / ".env")
from agent.utils.java_runtime import ensure_java_home_from_venv
ensure_java_home_from_venv(project_root)

from agent.dependencies import get_agent, get_settings
from agent.executor.comsol_runner import COMSOLRunner
from agent.utils.logger import setup_logging, get_logger
from rich.console import Console
from rich.panel import Panel

console = Console()
logger = get_logger(__name__)


def main():
    """主函数"""
    setup_logging("INFO")

    # 无参数或 --interactive 时进入与 cli 一致的全终端 TUI
    if len(sys.argv) == 1 or (len(sys.argv) >= 2 and sys.argv[1] in ("--interactive", "-i")):
        from agent.tui import run_tui
        if len(sys.argv) > 1:
            sys.argv = [sys.argv[0]]  # 去掉 -i/--interactive
        run_tui()
        return

    console.print(Panel.fit(
        "[bold cyan]COMSOL Multiphysics Agent - 调试模式[/bold cyan]",
        border_style="cyan"
    ))
    settings = get_settings()
    console.print(f"\n[dim]LLM 后端: {settings.llm_backend}[/dim]")
    console.print(f"[dim]模型输出目录: {settings.model_output_dir}[/dim]")
    console.print("\n[bold]示例用法:[/bold]")
    console.print("  python main.py --react '创建一个宽1米、高0.5米的矩形'")
    console.print("  python main.py --no-react '创建一个矩形'")
    console.print("  python main.py --interactive   # 或直接运行 comsol-agent 进入全终端交互")
    console.print("\n[yellow]推荐: 直接运行 comsol-agent（无参数）进入全终端交互模式[/yellow]\n")

    # 解析命令行参数
    if len(sys.argv) < 2:
        print_help()
        return
    
    use_react = True
    user_input = None
    output_filename = None
    interactive = False
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg == "--react":
            use_react = True
            i += 1
        elif arg == "--no-react":
            use_react = False
            i += 1
        elif arg == "--interactive" or arg == "-i":
            interactive = True
            i += 1
        elif arg == "--output" or arg == "-o":
            if i + 1 < len(sys.argv):
                output_filename = sys.argv[i + 1]
                i += 2
            else:
                console.print("[red]错误: --output 需要指定文件名[/red]")
                return
        elif arg == "--help" or arg == "-h":
            print_help()
            return
        elif not arg.startswith("-"):
            user_input = arg
            i += 1
        else:
            console.print(f"[red]未知参数: {arg}[/red]")
            i += 1
    
    if not user_input:
        console.print("[red]错误: 请提供用户输入，或使用 --interactive / 直接运行 comsol-agent 进入交互模式[/red]")
        return
    
    try:
        if use_react:
            console.print("\n[bold green]使用 ReAct 架构[/bold green]")
            console.print(f"[dim]用户输入: {user_input}[/dim]\n")
            core = get_agent("core", max_iterations=10)
            model_path = core.run(user_input, output_filename)
            console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
        else:
            console.print("\n[bold yellow]使用传统架构[/bold yellow]")
            console.print(f"[dim]用户输入: {user_input}[/dim]\n")
            planner = get_agent("planner")
            plan = planner.parse(user_input)
            console.print(f"[green]✅ 解析成功: {len(plan.shapes)} 个形状[/green]")
            runner = COMSOLRunner()
            model_path = runner.create_model_from_plan(plan, output_filename)
            console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  用户中断[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.exception("执行失败")
        console.print(f"\n[red]❌ 错误: {e}[/red]")
        sys.exit(1)


def print_help():
    """打印帮助信息"""
    help_text = """
COMSOL Multiphysics Agent - 主启动程序

用法:
    python main.py [选项] [用户输入]

选项:
    --react              使用 ReAct 架构（默认）
    --no-react           使用传统架构
    --interactive, -i    进入交互模式
    --output, -o <文件>  指定输出文件名
    --help, -h           显示此帮助信息

示例:
    # 使用 ReAct 架构
    python main.py --react "创建一个宽1米、高0.5米的矩形"
    
    # 使用传统架构
    python main.py --no-react "创建一个矩形"
    
    # 交互模式
    python main.py --interactive
    
    # 指定输出文件
    python main.py "创建模型" -o my_model.mph

架构说明:
    ReAct 架构（推荐）:
        - 支持完整的推理链路和执行链路
        - 自动迭代改进计划
        - 支持几何、物理场、网格、研究、求解的完整流程
    
    传统架构:
        - 仅支持几何建模
        - 简单直接的执行流程
"""
    print(help_text)


if __name__ == "__main__":
    main()
