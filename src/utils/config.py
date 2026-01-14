"""配置管理模块"""
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings(BaseSettings):
    """应用配置"""
    
    # Qwen API 配置
    dashscope_api_key: str = ""
    
    # COMSOL 配置
    comsol_jar_path: str = ""
    java_home: Optional[str] = None
    model_output_dir: str = "./models"
    
    # 日志配置
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> any:
            if field_name == "dashscope_api_key":
                return raw_val
            return cls.json_loads(raw_val)


# 全局配置实例
settings = Settings()

# 确保输出目录存在
Path(settings.model_output_dir).mkdir(parents=True, exist_ok=True)
