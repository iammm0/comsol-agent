"""主入口 - 整合所有组件实现端到端流程"""
import sys
import argparse
from pathlib import Path

from loguru import logger

from src.planner.agent import PlannerAgent
from src.comsol.api_wrapper import COMSOLWrapper
from src.utils.config import settings


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )


def create_model_from_text(user_input: str, output_filename: str = None) -> Path:
    """
    从自然语言描述创建 COMSOL 模型
    
    Args:
        user_input: 用户自然语言描述
        output_filename: 输出文件名（可选）
    
    Returns:
        生成的模型文件路径
    """
    logger.info("=" * 60)
    logger.info("开始创建 COMSOL 模型")
    logger.info("=" * 60)
    
    try:
        # 步骤 1: Planner Agent 解析自然语言
        logger.info("步骤 1: 解析自然语言...")
        planner = PlannerAgent()
        plan = planner.parse(user_input)
        logger.info(f"解析成功: {len(plan.shapes)} 个形状")
        
        # 步骤 2: 创建 COMSOL 模型
        logger.info("步骤 2: 创建 COMSOL 模型...")
        comsol = COMSOLWrapper()
        model_path = comsol.create_model_from_plan(plan, output_filename)
        
        logger.info("=" * 60)
        logger.info(f"✅ 模型创建成功: {model_path}")
        logger.info("=" * 60)
        
        return model_path
        
    except Exception as e:
        logger.error(f"❌ 创建模型失败: {e}")
        raise


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="COMSOL Multiphysics Agent - 将自然语言转换为 COMSOL 模型文件"
    )
    parser.add_argument(
        "input",
        type=str,
        help="自然语言描述的几何建模需求"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="输出文件名（不含路径）"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )
    
    args = parser.parse_args()
    
    # 配置日志级别
    if args.verbose:
        settings.log_level = "DEBUG"
    
    setup_logging()
    
    try:
        model_path = create_model_from_text(args.input, args.output)
        print(f"\n✅ 模型已生成: {model_path}")
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
