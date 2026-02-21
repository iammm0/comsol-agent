"""
会话级共享上下文，供模型开发器 / App 开发器 / 模型管理器三模块读写。

与 docs/comsol-modules-and-context.md 中「SessionContext」对应。
生命周期：随会话创建/恢复而加载，随会话结束可归档。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SessionContext:
    """
    当前会话的工作状态，三模块共享同一份逻辑视图。
    """

    # 当前模型（模型开发器）
    current_model_path: Optional[Path] = None
    current_model_name: Optional[str] = None
    model_modified: bool = False

    # 当前仿真 App（App 开发器，可选）
    current_app_path: Optional[Path] = None
    current_app_name: Optional[str] = None
    current_app_model_path: Optional[Path] = None  # 关联的 .mph

    # 模型管理器工作区（可选）
    workspace_path: Optional[Path] = None
    recent_models: List[Path] = field(default_factory=list)

    # 跨轮对话摘要/记忆（供三模块共用）
    conversation_summary: Optional[str] = None
    last_execution_result: Optional[str] = None

    # 扩展字段，便于后续加字段而不改签名
    extra: Dict[str, Any] = field(default_factory=dict)

    def set_current_model(self, path: Path, name: Optional[str] = None, modified: bool = False) -> None:
        """设置当前模型路径与名称。"""
        self.current_model_path = Path(path) if path else None
        self.current_model_name = name or (path.name if path else None)
        self.model_modified = modified

    def set_current_app(self, path: Optional[Path] = None, name: Optional[str] = None, model_path: Optional[Path] = None) -> None:
        """设置当前 App 相关信息。"""
        self.current_app_path = Path(path) if path else None
        self.current_app_name = name
        self.current_app_model_path = Path(model_path) if model_path else None

    def append_recent_model(self, path: Path, max_size: int = 20) -> None:
        """将模型路径加入最近列表（去重并限制长度）。"""
        p = Path(path)
        if p in self.recent_models:
            self.recent_models.remove(p)
        self.recent_models.insert(0, p)
        self.recent_models = self.recent_models[:max_size]
