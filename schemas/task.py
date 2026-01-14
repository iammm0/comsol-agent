"""任务数据结构定义"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from datetime import datetime

from schemas.geometry import GeometryPlan
from schemas.physics import PhysicsPlan
from schemas.study import StudyPlan


class ExecutionStep(BaseModel):
    """执行步骤"""
    
    step_id: str = Field(..., description="步骤ID")
    step_type: Literal["geometry", "physics", "mesh", "study", "solve"] = Field(
        ..., description="步骤类型"
    )
    action: str = Field(..., description="执行动作")
    parameters: Dict[str, Any] = Field(default={}, description="步骤参数")
    status: Literal["pending", "running", "completed", "failed"] = Field(
        default="pending", description="步骤状态"
    )
    result: Optional[Dict[str, Any]] = Field(default=None, description="执行结果")


class ReasoningCheckpoint(BaseModel):
    """推理检查点"""
    
    checkpoint_id: str = Field(..., description="检查点ID")
    checkpoint_type: Literal["validation", "verification", "optimization"] = Field(
        ..., description="检查点类型"
    )
    description: str = Field(..., description="检查点描述")
    criteria: Dict[str, Any] = Field(default={}, description="检查标准")
    status: Literal["pending", "passed", "failed"] = Field(
        default="pending", description="检查状态"
    )
    feedback: Optional[str] = Field(default=None, description="检查反馈")


class Observation(BaseModel):
    """观察结果"""
    
    observation_id: str = Field(..., description="观察ID")
    step_id: str = Field(..., description="关联的步骤ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="观察时间")
    status: Literal["success", "warning", "error"] = Field(..., description="观察状态")
    message: str = Field(..., description="观察消息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="观察数据")


class IterationRecord(BaseModel):
    """迭代记录"""
    
    iteration_id: int = Field(..., description="迭代次数")
    timestamp: datetime = Field(default_factory=datetime.now, description="迭代时间")
    reason: str = Field(..., description="迭代原因")
    changes: Dict[str, Any] = Field(default={}, description="计划变更")
    observations: List[Observation] = Field(default=[], description="本次迭代的观察结果")


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


class ReActTaskPlan(BaseModel):
    """ReAct 任务计划 - 包含推理链路和执行链路"""
    
    task_id: str = Field(..., description="任务ID")
    model_name: str = Field(..., description="模型名称")
    user_input: str = Field(..., description="用户原始输入")
    
    # 执行链路
    execution_path: List[ExecutionStep] = Field(
        default=[], description="执行步骤列表"
    )
    current_step_index: int = Field(default=0, description="当前执行步骤索引")
    
    # 推理链路
    reasoning_path: List[ReasoningCheckpoint] = Field(
        default=[], description="推理检查点列表"
    )
    
    # 观察结果
    observations: List[Observation] = Field(
        default=[], description="观察结果列表"
    )
    
    # 迭代历史
    iterations: List[IterationRecord] = Field(
        default=[], description="迭代历史"
    )
    
    # 任务状态
    status: Literal["planning", "executing", "observing", "iterating", "completed", "failed"] = Field(
        default="planning", description="任务状态"
    )
    
    # 模型路径
    model_path: Optional[str] = Field(default=None, description="生成的模型文件路径")
    
    # 错误信息
    error: Optional[str] = Field(default=None, description="错误信息")
    
    def get_current_step(self) -> Optional[ExecutionStep]:
        """获取当前执行步骤"""
        if 0 <= self.current_step_index < len(self.execution_path):
            return self.execution_path[self.current_step_index]
        return None
    
    def add_observation(self, observation: Observation):
        """添加观察结果"""
        self.observations.append(observation)
    
    def add_iteration(self, iteration: IterationRecord):
        """添加迭代记录"""
        self.iterations.append(iteration)
    
    def is_complete(self) -> bool:
        """检查任务是否完成"""
        return self.status == "completed"
    
    def has_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status == "failed"
    
    # 用于存储几何计划（动态属性）
    geometry_plan: Optional[Any] = None