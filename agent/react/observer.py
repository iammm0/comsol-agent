"""观察器 - 观察执行结果"""
from typing import Dict, Any
from pathlib import Path
from uuid import uuid4

from agent.utils.logger import get_logger
from schemas.task import ReActTaskPlan, ExecutionStep, Observation

logger = get_logger(__name__)


class Observer:
    """观察器 - 观察执行结果并验证模型状态"""
    
    def __init__(self):
        """初始化观察器"""
        pass
    
    def observe(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """
        观察执行结果
        
        Args:
            plan: 任务计划
            step: 执行步骤
            result: 执行结果
        
        Returns:
            观察结果
        """
        logger.debug(f"观察步骤 {step.step_id} 的执行结果")
        
        # 根据步骤类型进行不同的观察
        if step.step_type == "geometry":
            return self.observe_geometry(plan, step, result)
        elif step.step_type == "physics":
            return self.observe_physics(plan, step, result)
        elif step.step_type == "mesh":
            return self.observe_mesh(plan, step, result)
        elif step.step_type == "study":
            return self.observe_study(plan, step, result)
        elif step.step_type == "solve":
            return self.observe_solve(plan, step, result)
        else:
            return self._create_observation(step, result)
    
    def observe_geometry(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """
        观察几何构建结果
        
        Args:
            plan: 任务计划
            step: 执行步骤
            result: 执行结果
        
        Returns:
            观察结果
        """
        status = result.get("status", "unknown")
        
        if status == "success":
            # 检查模型文件是否存在
            model_path = result.get("model_path") or plan.model_path
            if model_path and Path(model_path).exists():
                return Observation(
                    observation_id=str(uuid4()),
                    step_id=step.step_id,
                    status="success",
                    message="几何构建成功，模型文件已生成",
                    data={"model_path": model_path}
                )
            else:
                return Observation(
                    observation_id=str(uuid4()),
                    step_id=step.step_id,
                    status="warning",
                    message="几何构建成功，但模型文件未找到",
                    data=result
                )
        else:
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="error",
                message=f"几何构建失败: {result.get('message', '未知错误')}",
                data=result
            )
    
    def observe_physics(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """
        观察物理场设置结果
        
        Args:
            plan: 任务计划
            step: 执行步骤
            result: 执行结果
        
        Returns:
            观察结果
        """
        status = result.get("status", "unknown")
        
        if status == "success":
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="success",
                message="物理场设置成功",
                data=result
            )
        elif status == "warning":
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="warning",
                message=result.get("message", "物理场设置有警告"),
                data=result
            )
        else:
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="error",
                message=f"物理场设置失败: {result.get('message', '未知错误')}",
                data=result
            )
    
    def observe_mesh(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """
        观察网格划分结果
        
        Args:
            plan: 任务计划
            step: 执行步骤
            result: 执行结果
        
        Returns:
            观察结果
        """
        status = result.get("status", "unknown")
        
        if status == "success":
            mesh_info = result.get("mesh_info", {})
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="success",
                message="网格划分成功",
                data=mesh_info
            )
        else:
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="error",
                message=f"网格划分失败: {result.get('message', '未知错误')}",
                data=result
            )
    
    def observe_study(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """
        观察研究配置结果
        
        Args:
            plan: 任务计划
            step: 执行步骤
            result: 执行结果
        
        Returns:
            观察结果
        """
        status = result.get("status", "unknown")
        
        if status == "success":
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="success",
                message="研究配置成功",
                data=result
            )
        elif status == "warning":
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="warning",
                message=result.get("message", "研究配置有警告"),
                data=result
            )
        else:
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="error",
                message=f"研究配置失败: {result.get('message', '未知错误')}",
                data=result
            )
    
    def observe_solve(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """
        观察求解结果
        
        Args:
            plan: 任务计划
            step: 执行步骤
            result: 执行结果
        
        Returns:
            观察结果
        """
        status = result.get("status", "unknown")
        
        if status == "success":
            solve_info = result.get("solve_info", {})
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="success",
                message="求解成功",
                data=solve_info
            )
        else:
            return Observation(
                observation_id=str(uuid4()),
                step_id=step.step_id,
                status="error",
                message=f"求解失败: {result.get('message', '未知错误')}",
                data=result
            )
    
    def observe_model_state(
        self,
        plan: ReActTaskPlan
    ) -> Observation:
        """
        观察模型整体状态
        
        Args:
            plan: 任务计划
        
        Returns:
            观察结果
        """
        # 检查模型文件
        if not plan.model_path:
            return Observation(
                observation_id=str(uuid4()),
                step_id="overall",
                status="error",
                message="模型文件路径未设置"
            )
        
        model_path = Path(plan.model_path)
        if not model_path.exists():
            return Observation(
                observation_id=str(uuid4()),
                step_id="overall",
                status="error",
                message="模型文件不存在"
            )
        
        # 检查文件大小
        file_size = model_path.stat().st_size
        if file_size == 0:
            return Observation(
                observation_id=str(uuid4()),
                step_id="overall",
                status="warning",
                message="模型文件为空"
            )
        
        # 检查步骤完成情况
        completed_steps = sum(1 for step in plan.execution_path if step.status == "completed")
        total_steps = len(plan.execution_path)
        
        return Observation(
            observation_id=str(uuid4()),
            step_id="overall",
            status="success" if completed_steps == total_steps else "warning",
            message=f"模型状态: {completed_steps}/{total_steps} 步骤已完成",
            data={
                "model_path": str(model_path),
                "file_size": file_size,
                "completed_steps": completed_steps,
                "total_steps": total_steps
            }
        )
    
    def _create_observation(
        self,
        step: ExecutionStep,
        result: Dict[str, Any]
    ) -> Observation:
        """创建通用观察结果"""
        status = result.get("status", "unknown")
        
        observation_status = "success" if status == "success" else "error"
        
        return Observation(
            observation_id=str(uuid4()),
            step_id=step.step_id,
            status=observation_status,
            message=result.get("message", f"步骤 {step.action} 执行完成"),
            data=result
        )
