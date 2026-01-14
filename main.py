"""主启动程序 - 用于调试和开发"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent.react.react_agent import ReActAgent
from agent.planner.geometry_agent import GeometryAgent
from agent.executor.comsol_runner import COMSOLRunner
from agent.utils.logger import setup_logging, get_logger
from agent.utils.config import get_settings
from rich.console import Console
from rich.panel import Panel

console = Console()
logger = get_logger(__name__)


def main():
    """主函数"""
    setup_logging("INFO")
    
    console.print(Panel.fit(
        "[bold cyan]COMSOL Multiphysics Agent - 调试模式[/bold cyan]",
        border_style="cyan"
    ))
    
    # 显示配置信息
    settings = get_settings()
    console.print(f"\n[dim]LLM 后端: {settings.llm_backend}[/dim]")
    console.print(f"[dim]模型输出目录: {settings.model_output_dir}[/dim]")
    
    # 示例用法
    console.print("\n[bold]示例用法:[/bold]")
    console.print("1. 使用 ReAct 架构（推荐）:")
    console.print("   python main.py --react '创建一个宽1米、高0.5米的矩形'")
    console.print("\n2. 使用传统架构:")
    console.print("   python main.py --no-react '创建一个矩形'")
    console.print("\n3. 交互模式:")
    console.print("   python main.py --interactive")
    
    # 解析命令行参数
    if len(sys.argv) < 2:
        console.print("\n[yellow]提示: 使用 --help 查看帮助信息[/yellow]")
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
    
    # 交互模式
    if interactive:
        run_interactive_mode(use_react)
        return
    
    # 非交互模式
    if not user_input:
        console.print("[red]错误: 请提供用户输入或使用 --interactive 进入交互模式[/red]")
        return
    
    try:
        if use_react:
            console.print(f"\n[bold green]使用 ReAct 架构[/bold green]")
            console.print(f"[dim]用户输入: {user_input}[/dim]\n")
            
            react_agent = ReActAgent(max_iterations=10)
            model_path = react_agent.run(user_input, output_filename)
            
            console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
        else:
            console.print(f"\n[bold yellow]使用传统架构[/bold yellow]")
            console.print(f"[dim]用户输入: {user_input}[/dim]\n")
            
            # 使用传统架构
            planner = GeometryAgent()
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


def run_interactive_mode(use_react: bool):
    """运行交互模式"""
    console.print("\n[bold cyan]进入交互模式[/bold cyan]")
    console.print("[dim]输入 'quit' 或 'exit' 退出[/dim]\n")
    
    if use_react:
        react_agent = ReActAgent(max_iterations=10)
    else:
        planner = GeometryAgent()
        runner = COMSOLRunner()
    
    while True:
        try:
            user_input = input("\n[bold]请输入建模需求:[/bold] ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "exit", "q"]:
                console.print("\n[yellow]退出交互模式[/yellow]")
                break
            
            if use_react:
                console.print(f"\n[dim]使用 ReAct 架构处理...[/dim]")
                model_path = react_agent.run(user_input)
                console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
            else:
                console.print(f"\n[dim]使用传统架构处理...[/dim]")
                plan = planner.parse(user_input)
                console.print(f"[green]✅ 解析成功: {len(plan.shapes)} 个形状[/green]")
                model_path = runner.create_model_from_plan(plan)
                console.print(f"\n[green]✅ 模型已生成: {model_path}[/green]")
                
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  用户中断[/yellow]")
            break
        except Exception as e:
            logger.exception("处理失败")
            console.print(f"\n[red]❌ 错误: {e}[/red]")


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
