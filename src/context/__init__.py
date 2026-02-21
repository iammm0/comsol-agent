"""
会话上下文与事件总线，供三模块 Agent 与会话编排使用。

详见 docs/comsol-modules-and-context.md、docs/agent-design-skills/session-and-events.md。
"""
from src.context.session_context import SessionContext
from src.context.events import Event, EventBus, EventType

__all__ = [
    "SessionContext",
    "Event",
    "EventBus",
    "EventType",
]
