"""环境检查模块"""
import os
from pathlib import Path
from typing import Tuple, List

from agent.utils.config import get_settings
from agent.utils.logger import get_logger
from agent.utils import secrets as secrets_utils

logger = get_logger(__name__)


class EnvCheckResult:
    """环境检查结果"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    def add_error(self, message: str):
        """添加错误"""
        self.errors.append(message)
    
    def add_warning(self, message: str):
        """添加警告"""
        self.warnings.append(message)
    
    def add_info(self, message: str):
        """添加信息"""
        self.info.append(message)
    
    def is_valid(self) -> bool:
        """检查是否有效（无错误）"""
        return len(self.errors) == 0
    
    def has_warnings(self) -> bool:
        """检查是否有警告"""
        return len(self.warnings) > 0


def check_environment() -> EnvCheckResult:
    """
    检查环境配置
    
    Returns:
        EnvCheckResult 对象
    """
    result = EnvCheckResult()
    settings = get_settings()
    
    # 1. 检查 LLM 后端配置
    backend = settings.llm_backend.lower()
    result.add_info(f"LLM 后端: {backend}")
    
    if backend == "dashscope":
        key = settings.get_api_key_for_backend("dashscope")
        if not key:
            result.add_error("DASHSCOPE_API_KEY 未配置，请设置环境变量、.env 或使用 keyring")
        else:
            result.add_info(f"DASHSCOPE_API_KEY 已配置（{secrets_utils.mask_key(key)}）")
            
    elif backend == "openai":
        key = settings.get_api_key_for_backend("openai")
        if not key:
            result.add_error("OPENAI_API_KEY 未配置，请设置环境变量、.env 或使用 keyring")
        else:
            result.add_info(f"OPENAI_API_KEY 已配置（{secrets_utils.mask_key(key)}）")
            if settings.openai_base_url:
                result.add_info(f"OpenAI 基础 URL: {settings.openai_base_url}")
            else:
                result.add_info("使用 OpenAI 官方 API")
                
    elif backend == "openai-compatible":
        key = settings.get_api_key_for_backend("openai-compatible")
        if not key:
            result.add_error("OPENAI_COMPATIBLE_API_KEY 未配置，请设置环境变量、.env 或使用 keyring")
        else:
            result.add_info(f"OPENAI_COMPATIBLE_API_KEY 已配置（{secrets_utils.mask_key(key)}）")
        
        if not settings.openai_compatible_base_url:
            result.add_error("OPENAI_COMPATIBLE_BASE_URL 未配置，请设置环境变量或 .env 文件")
        else:
            result.add_info(f"OpenAI 兼容 API 基础 URL: {settings.openai_compatible_base_url}")
            # 测试连接
            try:
                import requests
                test_url = f"{settings.openai_compatible_base_url.rstrip('/')}/models"
                response = requests.get(test_url, timeout=5, headers={"Authorization": f"Bearer {settings.openai_compatible_api_key}"})
                if response.status_code == 200:
                    result.add_info("OpenAI 兼容 API 服务可访问")
                else:
                    result.add_warning(f"OpenAI 兼容 API 服务响应异常: {response.status_code}")
            except Exception as e:
                result.add_warning(f"无法连接到 OpenAI 兼容 API 服务: {e}")
                
    elif backend == "ollama":
        # 检查 Ollama 服务
        try:
            import requests
            test_url = f"{settings.ollama_url}/api/tags"
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                result.add_info(f"Ollama 服务可访问: {settings.ollama_url}")
                result.add_info(f"可用模型: {', '.join(model_names[:5])}" + (f" (共 {len(model_names)} 个)" if len(model_names) > 5 else ""))
            else:
                result.add_warning(f"Ollama 服务响应异常: {settings.ollama_url}")
        except Exception as e:
            result.add_error(f"无法连接到 Ollama 服务 ({settings.ollama_url}): {e}")
    else:
        result.add_error(f"不支持的 LLM 后端: {backend}，支持的后端: dashscope, openai, openai-compatible, ollama")
    
    # 2. 检查 COMSOL_JAR_PATH
    if not settings.comsol_jar_path:
        result.add_error("COMSOL_JAR_PATH 未配置，请设置环境变量或 .env 文件")
    else:
        jar_path = Path(settings.comsol_jar_path)
        if jar_path.exists():
            size_mb = jar_path.stat().st_size / (1024 * 1024)
            result.add_info(f"COMSOL JAR 文件存在: {jar_path} ({size_mb:.2f} MB)")
        else:
            result.add_error(f"COMSOL JAR 文件不存在: {jar_path}")
    
    # 3. 检查 JAVA_HOME
    if not settings.java_home:
        # 尝试从环境变量获取
        import os
        java_home_env = os.environ.get("JAVA_HOME")
        if java_home_env:
            settings.java_home = java_home_env
            result.add_info(f"从环境变量获取 JAVA_HOME: {java_home_env}")
        else:
            result.add_error("JAVA_HOME 未配置，请设置环境变量或 .env 文件")
    
    if settings.java_home:
        java_home_path = Path(settings.java_home)
        if java_home_path.exists():
            # 检查 Java 可执行文件
            java_exe = java_home_path / "bin" / "java.exe"
            if not java_exe.exists():
                java_exe = java_home_path / "bin" / "java"
            if java_exe.exists():
                result.add_info(f"Java 可执行文件存在: {java_exe}")
            else:
                result.add_warning(f"未找到 Java 可执行文件: {java_home_path / 'bin'}")
        else:
            result.add_error(f"JAVA_HOME 路径不存在: {java_home_path}")
    
    # 4. 检查 MODEL_OUTPUT_DIR
    if not settings.model_output_dir:
        result.add_error("MODEL_OUTPUT_DIR 未配置")
    else:
        output_dir = Path(settings.model_output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            # 测试写入权限
            test_file = output_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            result.add_info(f"输出目录可访问: {output_dir}")
        except Exception as e:
            result.add_error(f"输出目录无法访问: {output_dir} ({e})")
    
    # 5. 检查 Python 依赖
    if backend == "dashscope":
        try:
            import dashscope
            result.add_info("dashscope 已安装")
        except ImportError:
            result.add_error("dashscope 未安装，请运行: pip install dashscope")
    
    if backend in ["openai", "openai-compatible"]:
        try:
            import openai
            result.add_info("openai 已安装")
        except ImportError:
            result.add_error("openai 未安装，请运行: pip install openai")
    
    try:
        import requests
        result.add_info("requests 已安装")
    except ImportError:
        result.add_error("requests 未安装，请运行: pip install requests")
    
    try:
        import jpype
        result.add_info("jpype1 已安装")
    except ImportError:
        result.add_error("jpype1 未安装，请运行: pip install jpype1")
    
    return result


def validate_environment() -> Tuple[bool, str]:
    """
    验证环境配置（简化版，用于启动前检查）
    
    Returns:
        (is_valid, error_message)
    """
    result = check_environment()
    
    if not result.is_valid():
        error_msg = "环境配置错误:\n" + "\n".join(f"  - {err}" for err in result.errors)
        return False, error_msg
    
    return True, ""


def print_check_result(result: EnvCheckResult):
    """打印检查结果"""
    from rich.console import Console
    from rich.panel import Panel
    
    console = Console()
    
    if result.is_valid():
        console.print(Panel("[green]✅ 环境检查通过[/green]", title="环境检查"))
    else:
        console.print(Panel("[red]❌ 环境检查失败[/red]", title="环境检查"))
    
    if result.errors:
        console.print("\n[red]错误:[/red]")
        for error in result.errors:
            console.print(f"  [red]❌[/red] {error}")
    
    if result.warnings:
        console.print("\n[yellow]警告:[/yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]⚠️[/yellow] {warning}")
    
    if result.info:
        console.print("\n[cyan]信息:[/cyan]")
        for info in result.info:
            console.print(f"  [cyan]ℹ️[/cyan] {info}")
