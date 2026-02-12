"""配置管理"""
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

from agent.utils import secrets as secrets_utils

# 加载 .env 文件
load_dotenv()


def get_install_dir() -> Path:
    """获取安装目录"""
    # 尝试从包元数据获取
    try:
        import importlib.metadata
        dist = importlib.metadata.distribution("agent-for-comsol-multiphysics")
        if dist and dist.locate_file:
            return Path(dist.locate_file("")).parent
    except Exception:
        pass
    
    # 回退到脚本所在目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        return Path(sys.executable).parent
    else:
        # 开发模式：使用项目根目录
        return Path(__file__).parent.parent.parent


def get_default_output_dir() -> str:
    """获取默认输出目录（安装目录下的 models 文件夹）"""
    install_dir = get_install_dir()
    return str(install_dir / "models")


class Settings(BaseSettings):
    """应用配置"""
    
    # LLM 后端配置
    llm_backend: str = "dashscope"  # "dashscope", "openai", "openai-compatible", "ollama"
    
    # Dashscope (Qwen) API 配置
    dashscope_api_key: str = ""
    
    # OpenAI 官方 API 配置
    openai_api_key: str = ""
    openai_base_url: Optional[str] = None  # 可选，默认使用官方 API
    openai_model: str = "gpt-3.5-turbo"  # OpenAI 模型名称
    
    # OpenAI 兼容 API 配置（第三方服务）
    openai_compatible_api_key: str = ""
    openai_compatible_base_url: str = ""  # 必须提供，例如 https://api.example.com/v1
    openai_compatible_model: str = "gpt-3.5-turbo"  # 第三方服务模型名称
    
    # Ollama 配置
    ollama_url: str = "http://localhost:11434"  # Ollama 服务地址
    ollama_model: str = "llama3"  # Ollama 模型名称
    
    # COMSOL 配置
    comsol_jar_path: str = ""
    java_home: Optional[str] = None
    model_output_dir: str = ""
    
    # 日志配置
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 如果未设置输出目录，使用默认值
        if not self.model_output_dir:
            self.model_output_dir = get_default_output_dir()

    def get_api_key_for_backend(self, backend: str) -> Optional[str]:
        """获取当前后端的 API Key。顺序：环境变量优先，再 keyring。"""
        if backend == "ollama":
            return None
        key = secrets_utils.get_api_key(backend)
        if key:
            return key
        # 回退到 pydantic 从 env 加载的字段
        if backend == "dashscope":
            return self.dashscope_api_key or None
        if backend == "openai":
            return self.openai_api_key or None
        if backend == "openai-compatible":
            return self.openai_compatible_api_key or None
        return None

    def get_base_url_for_backend(self, backend: str) -> Optional[str]:
        """获取当前后端的 API base URL。"""
        if backend == "openai":
            return self.openai_base_url
        if backend == "openai-compatible":
            return self.openai_compatible_base_url or None
        return None

    def get_model_for_backend(self, backend: str) -> str:
        """获取当前后端的模型名称。"""
        if backend == "dashscope":
            return getattr(self, "dashscope_model", "qwen-turbo") or "qwen-turbo"
        if backend == "openai":
            return self.openai_model or "gpt-3.5-turbo"
        if backend == "openai-compatible":
            return self.openai_compatible_model or "gpt-3.5-turbo"
        if backend == "ollama":
            return self.ollama_model or "llama3"
        return ""

    def show_config_status(self) -> Dict[str, bool]:
        """
        返回各 provider 是否已配置（不暴露密钥）。
        供 CLI/调试展示用。
        """
        status: Dict[str, bool] = {}
        for provider in ("dashscope", "openai", "openai-compatible"):
            status[provider] = bool(self.get_api_key_for_backend(provider))
        # ollama: 有 URL 即视为可尝试使用
        status["ollama"] = bool(self.ollama_url and self.ollama_url.strip())
        return status


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例（单例）"""
    global _settings
    if _settings is None:
        _settings = Settings()
        # 确保输出目录存在
        Path(_settings.model_output_dir).mkdir(parents=True, exist_ok=True)
    return _settings
