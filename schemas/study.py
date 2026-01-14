"""研究类型数据结构定义（预留）"""
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field


class StudyType(BaseModel):
    """研究类型定义"""
    
    type: Literal["stationary", "time_dependent", "eigenvalue", "frequency"] = Field(
        ..., description="研究类型"
    )
    
    parameters: Dict[str, Any] = Field(
        default={},
        description="研究参数"
    )


class StudyPlan(BaseModel):
    """研究计划"""
    
    studies: list[StudyType] = Field(
        default=[],
        description="研究列表"
    )
