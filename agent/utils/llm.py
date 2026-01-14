"""LLM 工具函数 - 支持多种后端"""
import json
from typing import Optional, Literal
from abc import ABC, abstractmethod

from agent.utils.logger import get_logger

logger = get_logger(__name__)


class LLMBackend(ABC):
    """LLM 后端抽象基类"""
    
    @abstractmethod
    def call(self, prompt: str, model: str, temperature: float = 0.1, max_retries: int = 3) -> str:
        """调用 LLM API"""
        pass


class DashscopeBackend(LLMBackend):
    """Dashscope (Qwen) 后端"""
    
    def __init__(self, api_key: str):
        """
        初始化 Dashscope 后端
        
        Args:
            api_key: Dashscope API Key
        """
        try:
            import dashscope
            from dashscope import Generation
            self.dashscope = dashscope
            self.Generation = Generation
            dashscope.api_key = api_key
        except ImportError:
            raise ImportError("dashscope 未安装，请运行: pip install dashscope")
    
    def call(self, prompt: str, model: str = "qwen-turbo", temperature: float = 0.1, max_retries: int = 3) -> str:
        """调用 Dashscope API"""
        for attempt in range(max_retries):
            try:
                logger.debug(f"调用 Dashscope API (尝试 {attempt + 1}/{max_retries})")
                
                response = self.Generation.call(
                    model=model,
                    prompt=prompt,
                    result_format='message',
                    temperature=temperature,
                )
                
                if response.status_code != 200:
                    raise ValueError(f"API 调用失败: {response.message}")
                
                response_text = response.output.choices[0].message.content
                logger.debug(f"Dashscope 响应长度: {len(response_text)} 字符")
                
                return response_text
                
            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次调用失败: {e}")
                if attempt == max_retries - 1:
                    raise ValueError(f"Dashscope API 调用失败: {e}") from e
        
        raise ValueError("Dashscope API 调用失败，已达到最大重试次数")


class OpenAIBackend(LLMBackend):
    """OpenAI 官方 API 后端"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """
        初始化 OpenAI 后端
        
        Args:
            api_key: OpenAI API Key
            base_url: API 基础 URL（可选，默认使用官方 API）
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("openai 未安装，请运行: pip install openai")
    
    def call(self, prompt: str, model: str = "gpt-3.5-turbo", temperature: float = 0.1, max_retries: int = 3) -> str:
        """调用 OpenAI API"""
        for attempt in range(max_retries):
            try:
                logger.debug(f"调用 OpenAI API (尝试 {attempt + 1}/{max_retries})")
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                
                response_text = response.choices[0].message.content
                if not response_text:
                    raise ValueError("OpenAI API 返回空响应")
                
                logger.debug(f"OpenAI 响应长度: {len(response_text)} 字符")
                
                return response_text
                
            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次调用失败: {e}")
                if attempt == max_retries - 1:
                    raise ValueError(f"OpenAI API 调用失败: {e}") from e
        
        raise ValueError("OpenAI API 调用失败，已达到最大重试次数")


class OpenAICompatibleBackend(LLMBackend):
    """OpenAI 兼容 API 后端（支持第三方服务）"""
    
    def __init__(self, api_key: str, base_url: str):
        """
        初始化 OpenAI 兼容后端
        
        Args:
            api_key: API Key
            base_url: API 基础 URL（必须提供，例如 https://api.example.com/v1）
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError("openai 未安装，请运行: pip install openai")
        
        self.base_url = base_url
        logger.info(f"使用 OpenAI 兼容 API: {base_url}")
    
    def call(self, prompt: str, model: str = "gpt-3.5-turbo", temperature: float = 0.1, max_retries: int = 3) -> str:
        """调用 OpenAI 兼容 API"""
        for attempt in range(max_retries):
            try:
                logger.debug(f"调用 OpenAI 兼容 API (尝试 {attempt + 1}/{max_retries})")
                logger.debug(f"服务地址: {self.base_url}, 模型: {model}")
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                
                response_text = response.choices[0].message.content
                if not response_text:
                    raise ValueError("API 返回空响应")
                
                logger.debug(f"API 响应长度: {len(response_text)} 字符")
                
                return response_text
                
            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次调用失败: {e}")
                if attempt == max_retries - 1:
                    raise ValueError(f"OpenAI 兼容 API 调用失败: {e}") from e
        
        raise ValueError("OpenAI 兼容 API 调用失败，已达到最大重试次数")


class OllamaBackend(LLMBackend):
    """Ollama 后端（支持本地和远程）"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        初始化 Ollama 后端
        
        Args:
            base_url: Ollama 服务地址，默认本地 http://localhost:11434
        """
        self.base_url = base_url.rstrip('/')
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("requests 未安装，请运行: pip install requests")
    
    def call(self, prompt: str, model: str = "llama3", temperature: float = 0.1, max_retries: int = 3) -> str:
        """调用 Ollama API"""
        api_url = f"{self.base_url}/api/generate"
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"调用 Ollama API (尝试 {attempt + 1}/{max_retries})")
                logger.debug(f"Ollama 服务地址: {self.base_url}, 模型: {model}")
                
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    }
                }
                
                response = self.requests.post(api_url, json=payload, timeout=120)
                response.raise_for_status()
                
                result = response.json()
                response_text = result.get("response", "")
                
                if not response_text:
                    raise ValueError("Ollama API 返回空响应")
                
                logger.debug(f"Ollama 响应长度: {len(response_text)} 字符")
                
                return response_text
                
            except self.requests.exceptions.ConnectionError as e:
                error_msg = f"无法连接到 Ollama 服务 ({self.base_url})，请确保 Ollama 正在运行"
                logger.warning(f"第 {attempt + 1} 次调用失败: {error_msg}")
                if attempt == max_retries - 1:
                    raise ValueError(error_msg) from e
            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次调用失败: {e}")
                if attempt == max_retries - 1:
                    raise ValueError(f"Ollama API 调用失败: {e}") from e
        
        raise ValueError("Ollama API 调用失败，已达到最大重试次数")
    
    def list_models(self) -> list:
        """列出可用的模型"""
        try:
            api_url = f"{self.base_url}/api/tags"
            response = self.requests.get(api_url, timeout=10)
            response.raise_for_status()
            result = response.json()
            return [model["name"] for model in result.get("models", [])]
        except Exception as e:
            logger.warning(f"获取模型列表失败: {e}")
            return []


class LLMClient:
    """LLM 客户端封装 - 支持多种后端"""
    
    def __init__(
        self,
        backend: Literal["dashscope", "openai", "openai-compatible", "ollama"] = "dashscope",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化 LLM 客户端
        
        Args:
            backend: 后端类型
                - "dashscope": Dashscope (Qwen) 官方 API
                - "openai": OpenAI 官方 API
                - "openai-compatible": 符合 OpenAI API 规范的第三方服务
                - "ollama": Ollama 服务（本地或远程）
            api_key: API Key（用于 dashscope、openai、openai-compatible）
            base_url: API 基础 URL
                - 对于 openai: 可选，默认使用官方 API
                - 对于 openai-compatible: 必须提供，例如 https://api.example.com/v1
            ollama_url: Ollama 服务地址（仅用于 ollama 后端，默认 http://localhost:11434）
            model: 模型名称（可选，使用后端默认值）
        """
        self.backend_type = backend
        self.model = model
        
        if backend == "dashscope":
            if not api_key:
                raise ValueError("使用 dashscope 后端需要提供 api_key")
            self.backend = DashscopeBackend(api_key)
            self.default_model = model or "qwen-turbo"
            
        elif backend == "openai":
            if not api_key:
                raise ValueError("使用 openai 后端需要提供 api_key")
            self.backend = OpenAIBackend(api_key, base_url=base_url)
            self.default_model = model or "gpt-3.5-turbo"
            
        elif backend == "openai-compatible":
            if not api_key:
                raise ValueError("使用 openai-compatible 后端需要提供 api_key")
            if not base_url:
                raise ValueError("使用 openai-compatible 后端需要提供 base_url")
            self.backend = OpenAICompatibleBackend(api_key, base_url)
            self.default_model = model or "gpt-3.5-turbo"
            
        elif backend == "ollama":
            ollama_url = ollama_url or "http://localhost:11434"
            self.backend = OllamaBackend(ollama_url)
            self.default_model = model or "llama3"
            
        else:
            raise ValueError(f"不支持的后端类型: {backend}，支持的后端: dashscope, openai, openai-compatible, ollama")
        
        logger.info(f"LLM 客户端已初始化: {backend}, 模型: {self.default_model}")
    
    def call(self, prompt: str, model: Optional[str] = None, temperature: float = 0.1, max_retries: int = 3) -> str:
        """
        调用 LLM API
        
        Args:
            prompt: 输入提示
            model: 模型名称（可选，使用初始化时的默认值）
            temperature: 温度参数
            max_retries: 最大重试次数
        
        Returns:
            LLM 响应文本
        
        Raises:
            ValueError: API 调用失败
        """
        model = model or self.default_model
        return self.backend.call(prompt, model, temperature, max_retries)
