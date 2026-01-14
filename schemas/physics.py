"""物理场建模数据结构定义（预留）"""
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field


class PhysicsField(BaseModel):
    """物理场定义"""
    
    type: Literal["heat", "electromagnetic", "structural", "fluid"] = Field(
        ..., description="物理场类型"
    )
    
    parameters: Dict[str, Any] = Field(
        default={},
        description="物理场参数"
    )


class PhysicsPlan(BaseModel):
    """物理场建模计划"""
    
    fields: list[PhysicsField] = Field(
        default=[],
        description="物理场列表"
    )
