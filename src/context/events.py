"""
事件类型与事件总线，供会话编排与多模块上下文同步使用。

与 docs/agent-design-skills/session-and-events.md、docs/comsol-modules-and-context.md 对齐。
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time


class EventType(str, Enum):
    """关键状态变更事件类型，便于订阅方按类型过滤。"""
    # 模型开发器
    MODEL_SAVED = "model_saved"
    MODEL_OPENED = "model_opened"
    MODEL_MODIFIED = "model_modified"
    # App 开发器（预留）
    APP_OPENED = "app_opened"
    APP_CLOSED = "app_closed"
    # 模型管理器（预留）
    WORKSPACE_CHANGED = "workspace_changed"
    # 通用
    TASK_PHASE = "task_phase"
    PLAN_START = "plan_start"
    THINK_CHUNK = "think_chunk"
    EXEC_RESULT = "exec_result"
    CONTENT = "content"
    ERROR = "error"


@dataclass
class Event:
    """统一事件体，便于订阅方按 type 过滤、按 data 取数。"""
    type: EventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    iteration: Optional[int] = None


# 事件处理函数类型：接收 Event，无返回值
EventHandler = Callable[[Event], None]


class EventBus:
    """
    简单同步事件总线：按事件类型注册 handler，核心逻辑只调用 emit。
    UI 或上下文层订阅感兴趣的事件并更新界面/上下文。
    """

    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """按事件类型注册 handler。"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """注册接收所有事件的全局 handler（如日志、监控）。"""
        self._global_handlers.append(handler)

    def emit(self, event: Event) -> None:
        """发布事件，通知该类型的 handler 与全局 handler。"""
        for h in self._global_handlers:
            try:
                h(event)
            except Exception:
                pass
        for h in self._handlers.get(event.type, []):
            try:
                h(event)
            except Exception:
                pass
