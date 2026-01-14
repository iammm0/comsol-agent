"""Executor Agent - 生成 COMSOL Java API 代码"""
from pathlib import Path
from typing import Optional

from loguru import logger

from src.comsol.templates import COMSOLTemplate
from src.planner.schema import GeometryPlan
from src.comsol.config import comsol_config


class ExecutorAgent:
    """Executor Agent - 根据 JSON 生成 COMSOL Java API 代码"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        初始化 Executor Agent
        
        Args:
            output_dir: 输出目录，如果为 None 则使用配置中的目录
        """
        self.output_dir = output_dir or comsol_config.model_output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_code(self, plan: GeometryPlan, output_filename: Optional[str] = None) -> str:
        """
        根据 GeometryPlan 生成完整的 Java 代码
        
        Args:
            plan: 几何建模计划
            output_filename: 输出文件名（不含路径），如果为 None 则自动生成
        
        Returns:
            生成的 Java 代码字符串
        """
        logger.info(f"生成 Java 代码，模型: {plan.model_name}, 形状数量: {len(plan.shapes)}")
        
        # 确定输出文件路径
        if output_filename is None:
            output_filename = f"{plan.model_name}.mph"
        
        output_path = str(self.output_dir / output_filename)
        
        # 生成代码
        java_code = COMSOLTemplate.generate_full_code(
            shapes=plan.shapes,
            model_name=plan.model_name,
            output_path=output_path
        )
        
        logger.debug(f"生成的 Java 代码长度: {len(java_code)} 字符")
        return java_code
    
    def save_code(self, code: str, filename: str = "generated_model.java") -> Path:
        """
        保存生成的 Java 代码到文件（用于调试）
        
        Args:
            code: Java 代码
            filename: 文件名
        
        Returns:
            保存的文件路径
        """
        file_path = self.output_dir / filename
        file_path.write_text(code, encoding="utf-8")
        logger.info(f"Java 代码已保存到: {file_path}")
        return file_path
