"""基本使用示例（使用 agent 包与 CLI 入口）。"""
from pathlib import Path
import sys
from typing import Optional

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.dependencies import get_agent
from agent.executor.comsol_runner import COMSOLRunner


def create_model_from_text(user_input: str, output_filename: Optional[str] = None):
    """
    从自然语言创建 COMSOL 模型（传统流程：Planner + Executor）。
    与旧 src.main.create_model_from_text 行为兼容。
    """
    planner = get_agent("planner")
    plan = planner.parse(user_input)
    runner = COMSOLRunner()
    return runner.create_model_from_plan(plan, output_filename)


def example_rectangle():
    print("\n" + "=" * 60)
    print("示例 1: 创建矩形")
    print("=" * 60)
    try:
        model_path = create_model_from_text(
            "创建一个宽1米、高0.5米的矩形",
            output_filename="rectangle_example.mph",
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def example_circle():
    print("\n" + "=" * 60)
    print("示例 2: 创建圆形")
    print("=" * 60)
    try:
        model_path = create_model_from_text(
            "在原点放置一个半径为0.3米的圆",
            output_filename="circle_example.mph",
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def example_ellipse():
    print("\n" + "=" * 60)
    print("示例 3: 创建椭圆")
    print("=" * 60)
    try:
        model_path = create_model_from_text(
            "创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)",
            output_filename="ellipse_example.mph",
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def example_with_react():
    """使用 ReAct 架构（推荐）"""
    print("\n" + "=" * 60)
    print("示例: ReAct 架构")
    print("=" * 60)
    try:
        core = get_agent("core", max_iterations=5)
        model_path = core.run("创建一个宽1米、高0.5米的矩形", "react_example.mph")
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    print("COMSOL Agent 使用示例")
    print("=" * 60)
    print("注意: 运行前请确保已配置 .env 文件")
    print("=" * 60)

    example_rectangle()
    example_circle()
    example_ellipse()
    # example_with_react()  # 可选：ReAct 流程

    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)
