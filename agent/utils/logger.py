"""日志工具"""
import sys
from loguru import logger as loguru_logger
from typing import Optional

from agent.utils.config import get_settings


def get_logger(name: str):
    """
    获取日志记录器
    
    Args:
        name: 模块名称
    
    Returns:
        日志记录器实例
    """
    return loguru_logger.bind(name=name)


def setup_logging(log_level: Optional[str] = None):
    """
    配置日志系统
    
    Args:
        log_level: 日志级别，如果为 None 则从配置读取
    """
    settings = get_settings()
    level = log_level or settings.log_level
    
    # 移除默认处理器
    loguru_logger.remove()
    
    # 添加控制台处理器
    loguru_logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    )
