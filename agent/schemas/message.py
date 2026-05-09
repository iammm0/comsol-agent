"""统一消息模型：供历史、持久化与日志使用。"""
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

RoleType = Literal["user", "assistant", "system"]


class AgentMessage(BaseModel):
    """Agent 消息：role/content/metadata，便于序列化与持久化。"""

    role: RoleType = Field(..., description="角色：user / assistant / system")
    content: str = Field(..., description="正文")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="可选元数据")

    class Config:
        frozen = False
