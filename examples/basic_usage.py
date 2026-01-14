"""基本使用示例"""
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.main import create_model_from_text
from loguru import logger


def example_rectangle():
    """示例 1: 创建矩形"""
    print("\n" + "=" * 60)
    print("示例 1: 创建矩形")
    print("=" * 60)
    
    try:
        model_path = create_model_from_text(
            "创建一个宽1米、高0.5米的矩形",
            output_filename="rectangle_example.mph"
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def example_circle():
    """示例 2: 创建圆形"""
    print("\n" + "=" * 60)
    print("示例 2: 创建圆形")
    print("=" * 60)
    
    try:
        model_path = create_model_from_text(
            "在原点放置一个半径为0.3米的圆",
            output_filename="circle_example.mph"
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def example_ellipse():
    """示例 3: 创建椭圆"""
    print("\n" + "=" * 60)
    print("示例 3: 创建椭圆")
    print("=" * 60)
    
    try:
        model_path = create_model_from_text(
            "创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)",
            output_filename="ellipse_example.mph"
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


def example_multiple_shapes():
    """示例 4: 创建多个形状"""
    print("\n" + "=" * 60)
    print("示例 4: 创建多个形状")
    print("=" * 60)
    
    try:
        model_path = create_model_from_text(
            "创建一个宽1米、高0.5米的矩形，然后在(1.5, 0)位置放置一个半径为0.2米的圆",
            output_filename="multiple_shapes_example.mph"
        )
        print(f"✅ 模型已生成: {model_path}")
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    print("COMSOL Agent 使用示例")
    print("=" * 60)
    print("注意: 运行前请确保已配置 .env 文件")
    print("=" * 60)
    
    # 运行示例
    example_rectangle()
    example_circle()
    example_ellipse()
    example_multiple_shapes()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)
