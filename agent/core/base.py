"""Agent 基类：统一 process 接口与可选历史/记忆。"""
from abc import ABC, abstractmethod
from typing import List, Optional, Any

from schemas.message import AgentMessage


class BaseAgent(ABC):
    """
    抽象基类：子类实现 process(user_input, **kwargs)。
    系统提示词、对话历史、记忆可由基类提供默认，子类按需覆盖。
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        history: Optional[List[AgentMessage]] = None,
    ):
        self.system_prompt = system_prompt or self._default_system_prompt()
        self._history: List[AgentMessage] = history or []

    def _default_system_prompt(self) -> str:
        """子类可覆盖。"""
        return "You are a helpful assistant."

    @abstractmethod
    def process(self, user_input: str, **kwargs: Any) -> str:
        """
        处理用户输入，返回助手回复（或结构化结果的字符串表示）。
        子类必须实现。
        """
        ...

    def append_history(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """追加一条历史消息。"""
        self._history.append(
            AgentMessage(role=role, content=content, metadata=metadata or {})
        )

    def get_history(self) -> List[AgentMessage]:
        """返回当前会话历史（当前轮次）。"""
        return list(self._history)

    def clear_history(self) -> None:
        """清空当前轮次历史。"""
        self._history.clear()
