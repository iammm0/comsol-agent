"""任务数据结构定义"""
from typing import Optional
from pydantic import BaseModel, Field

from schemas.geometry import GeometryPlan
from schemas.physics import PhysicsPlan
from schemas.study import StudyPlan


class TaskPlan(BaseModel):
    """完整任务计划"""
    
    geometry: Optional[GeometryPlan] = Field(
        default=None,
        description="几何建模计划"
    )
    
    physics: Optional[PhysicsPlan] = Field(
        default=None,
        description="物理场计划"
    )
    
    study: Optional[StudyPlan] = Field(
        default=None,
        description="研究计划"
    )
    
    def has_geometry(self) -> bool:
        """检查是否有几何计划"""
        return self.geometry is not None
    
    def has_physics(self) -> bool:
        """检查是否有物理场计划"""
        return self.physics is not None
    
    def has_study(self) -> bool:
        """检查是否有研究计划"""
        return self.study is not None
