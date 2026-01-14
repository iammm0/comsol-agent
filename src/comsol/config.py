"""COMSOL 配置管理"""
import os
from pathlib import Path
from typing import Optional, List

from src.utils.config import settings


class COMSOLConfig:
    """COMSOL 配置类"""
    
    def __init__(self):
        self.jar_path = settings.comsol_jar_path
        self.java_home = settings.java_home or os.environ.get("JAVA_HOME")
        self.model_output_dir = Path(settings.model_output_dir)
        
    def get_classpath(self) -> str:
        """
        获取 Java classpath 字符串
        
        如果配置的是目录，则自动收集所有jar文件
        如果配置的是单个jar文件，则直接返回
        
        Returns:
            classpath 字符串（多个路径用分号分隔，Windows）或冒号分隔（Unix）
        """
        path = Path(self.jar_path)
        
        if not path.exists():
            raise ValueError(f"COMSOL JAR 路径不存在: {self.jar_path}")
        
        # 如果是目录，收集所有jar文件
        if path.is_dir():
            jar_files = list(path.glob("*.jar"))
            if not jar_files:
                raise ValueError(f"在目录中未找到任何jar文件: {self.jar_path}")
            
            # Windows使用分号，Unix使用冒号
            separator = ";" if os.name == "nt" else ":"
            return separator.join(str(jar) for jar in jar_files)
        
        # 如果是单个文件，直接返回
        return str(path)
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        验证 COMSOL 配置
        
        Returns:
            (is_valid, error_message)
        """
        if not self.jar_path:
            return False, "COMSOL JAR 路径未配置，请设置 COMSOL_JAR_PATH"
        
        path = Path(self.jar_path)
        if not path.exists():
            return False, f"COMSOL JAR 路径不存在: {self.jar_path}"
        
        # 如果是目录，检查是否包含jar文件
        if path.is_dir():
            jar_files = list(path.glob("*.jar"))
            if not jar_files:
                return False, f"目录中未找到任何jar文件: {self.jar_path}"
        
        # 如果是文件，检查是否是jar文件
        elif not path.suffix.lower() == ".jar":
            return False, f"指定的文件不是jar文件: {self.jar_path}"
        
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
