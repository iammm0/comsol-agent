"""敏感信息存储：keyring + 环境变量回退。读取顺序：先 env，再 keyring。"""
import os
from typing import Optional

# 用于 keyring 的服务名，与 provider 组成键
KEYRING_SERVICE = "comsol-agent"

# provider -> 环境变量名（优先从 env 读取）
PROVIDER_ENV_KEYS = {
    "dashscope": "DASHSCOPE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openai-compatible": "OPENAI_COMPATIBLE_API_KEY",
}


def get_api_key(provider: str) -> Optional[str]:
    """
    获取 API Key。顺序：先读环境变量，再读 keyring。
    provider: dashscope | openai | openai-compatible
    """
    env_key = PROVIDER_ENV_KEYS.get(provider)
    if env_key:
        value = os.environ.get(env_key)
        if value and value.strip():
            return value.strip()
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, provider)
    except Exception:
        return None


def set_api_key(provider: str, key: str) -> None:
    """将 API Key 写入 keyring。"""
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, provider, key)
    except Exception as e:
        raise RuntimeError(f"keyring 不可用: {e}") from e


def delete_api_key(provider: str) -> None:
    """从 keyring 删除 API Key。"""
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, provider)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception:
        pass


def mask_key(key: Optional[str], prefix_len: int = 8) -> str:
    """返回掩码后的 key（仅前缀 + ***），用于日志或状态展示。"""
    if not key or len(key) <= prefix_len:
        return "***"
    return key[:prefix_len] + "***"
