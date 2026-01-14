"""COMSOL 配置管理"""
import os
from pathlib import Path
from typing import Optional

from src.utils.config import settings


class COMSOLConfig:
    """COMSOL 配置类"""
    
    def __init__(self):
        self.jar_path = settings.comsol_jar_path
        self.java_home = settings.java_home or os.environ.get("JAVA_HOME")
        self.model_output_dir = Path(settings.model_output_dir)
        
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        验证 COMSOL 配置
        
        Returns:
            (is_valid, error_message)
        """
        if not self.jar_path:
            return False, "COMSOL JAR 路径未配置，请设置 COMSOL_JAR_PATH"
        
        if not Path(self.jar_path).exists():
            return False, f"COMSOL JAR 文件不存在: {self.jar_path}"
        
        if not self.java_home:
            return False, "JAVA_HOME 未配置，请设置 JAVA_HOME 环境变量或配置"
        
        if not Path(self.java_home).exists():
            return False, f"JAVA_HOME 路径不存在: {self.java_home}"
        
        # 确保输出目录存在
        self.model_output_dir.mkdir(parents=True, exist_ok=True)
        
        return True, None
    
    def get_java_path(self) -> Optional[str]:
        """获取 Java 可执行文件路径"""
        if not self.java_home:
            return None
        
        java_path = Path(self.java_home) / "bin" / "java.exe"
        if java_path.exists():
            return str(java_path)
        
        # 尝试 Unix 风格路径
        java_path = Path(self.java_home) / "bin" / "java"
        if java_path.exists():
            return str(java_path)
        
        return None


# 全局配置实例
comsol_config = COMSOLConfig()
