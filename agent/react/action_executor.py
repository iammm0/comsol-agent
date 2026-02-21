"""行动执行器"""
from typing import Dict, Any, Optional
from pathlib import Path

from agent.planner.geometry_agent import GeometryAgent
from agent.planner.physics_agent import PhysicsAgent
from agent.planner.study_agent import StudyAgent
from agent.executor.comsol_runner import COMSOLRunner
from agent.executor.java_api_controller import JavaAPIController
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from schemas.task import ReActTaskPlan, ExecutionStep

logger = get_logger(__name__)


class ActionExecutor:
    """行动执行器 - 执行具体的建模操作；可选 event_bus 供上层发射事件。"""

    def __init__(self, event_bus: Optional[Any] = None):
        self.settings = get_settings()
        self.comsol_runner = COMSOLRunner()
        self.java_api_controller = JavaAPIController()
        self._event_bus = event_bus

        self._geometry_agent = None
        self._physics_agent = None
        self._study_agent = None
    
    def execute(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行步骤
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        logger.info(f"执行步骤: {step.action} ({step.step_type})")
        
        action_handlers = {
            "create_geometry": self.execute_geometry,
            "add_physics": self.execute_physics,
            "generate_mesh": self.execute_mesh,
            "configure_study": self.execute_study,
            "solve": self.execute_solve,
            "retry": self.execute_retry,
            "skip": self.execute_skip
        }
        
        handler = action_handlers.get(step.action)
        if not handler:
            return {
                "status": "error",
                "message": f"未知的行动: {step.action}"
            }
        
        try:
            result = handler(plan, step, thought)
            return result
        except Exception as e:
            logger.error(f"执行步骤失败: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def execute_geometry(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行几何建模
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        logger.info("执行几何建模...")
        
        # 若无几何计划，则用 GeometryAgent 从用户输入解析
        geometry_plan = getattr(plan, 'geometry_plan', None)
        if not geometry_plan:
            if not self._geometry_agent:
                self._geometry_agent = GeometryAgent()
            geometry_input = thought.get("parameters", {}).get("geometry_input") or getattr(plan, "user_input", "") or ""
            geometry_plan = self._geometry_agent.parse(geometry_input)
            plan.geometry_plan = geometry_plan
        
        model_name = getattr(plan, "model_name", None) or "model"
        output_filename = f"{model_name}.mph"
        
        try:
            model_path = self.comsol_runner.create_model_from_plan(geometry_plan, output_filename)
            plan.model_path = str(model_path)
            return {
                "status": "success",
                "message": "几何建模成功",
                "model_path": str(model_path),
                "geometry_plan": geometry_plan.to_dict()
            }
        except Exception as e:
            logger.error(f"几何建模失败: {e}")
            return {
                "status": "error",
                "message": f"几何建模失败: {e}"
            }
    
    def execute_physics(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行物理场设置
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        logger.info("执行物理场设置...")
        
        # 检查模型是否存在
        if not plan.model_path:
            return {
                "status": "error",
                "message": "模型文件不存在，请先执行几何建模"
            }
        
        # 使用 PhysicsAgent 解析物理场需求
        if not self._physics_agent:
            self._physics_agent = PhysicsAgent()
        
        physics_input = thought.get("parameters", {}).get("physics_input", plan.user_input)
        
        try:
            physics_plan = self._physics_agent.parse(physics_input)
            result = self.java_api_controller.add_physics(plan.model_path, physics_plan)
            if result.get("status") == "error":
                return {
                    "status": "error",
                    "message": result.get("message", "物理场设置失败"),
                }
            if result.get("saved_path"):
                plan.model_path = result["saved_path"]
            return {
                "status": "success",
                "message": "物理场设置成功",
                "physics_plan": physics_plan.model_dump(),
            }
        except NotImplementedError:
            logger.warning("PhysicsAgent 尚未实现，跳过物理场设置")
            return {
                "status": "warning",
                "message": "物理场设置功能尚未实现"
            }
        except Exception as e:
            logger.error(f"物理场设置失败: {e}")
            return {
                "status": "error",
                "message": f"物理场设置失败: {e}"
            }
    
    def execute_mesh(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行网格划分
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        logger.info("执行网格划分...")
        
        if not plan.model_path:
            return {
                "status": "error",
                "message": "模型文件不存在，请先执行几何建模"
            }
        
        try:
            mesh_params = thought.get("parameters", {}).get("mesh", {})
            result = self.java_api_controller.generate_mesh(plan.model_path, mesh_params)
            if result.get("status") == "error":
                return {
                    "status": "error",
                    "message": result.get("message", "网格划分失败"),
                }
            if result.get("saved_path"):
                plan.model_path = result["saved_path"]
            return {
                "status": "success",
                "message": "网格划分成功",
                "mesh_info": result
            }
        except Exception as e:
            logger.error(f"网格划分失败: {e}")
            return {
                "status": "error",
                "message": f"网格划分失败: {e}"
            }
    
    def execute_study(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行研究配置
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        logger.info("执行研究配置...")
        
        if not plan.model_path:
            return {
                "status": "error",
                "message": "模型文件不存在，请先执行几何建模"
            }
        
        # 使用 StudyAgent 解析研究需求
        if not self._study_agent:
            self._study_agent = StudyAgent()
        
        study_input = thought.get("parameters", {}).get("study_input", plan.user_input)
        
        try:
            study_plan = self._study_agent.parse(study_input)
            result = self.java_api_controller.configure_study(plan.model_path, study_plan)
            if result.get("status") == "error":
                return {
                    "status": "error",
                    "message": result.get("message", "研究配置失败"),
                }
            if result.get("saved_path"):
                plan.model_path = result["saved_path"]
            return {
                "status": "success",
                "message": "研究配置成功",
                "study_plan": study_plan.model_dump()
            }
        except NotImplementedError:
            logger.warning("StudyAgent 尚未实现，跳过研究配置")
            return {
                "status": "warning",
                "message": "研究配置功能尚未实现"
            }
        except Exception as e:
            logger.error(f"研究配置失败: {e}")
            return {
                "status": "error",
                "message": f"研究配置失败: {e}"
            }
    
    def execute_solve(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行求解
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        logger.info("执行求解...")
        
        if not plan.model_path:
            return {
                "status": "error",
                "message": "模型文件不存在"
            }
        
        try:
            result = self.java_api_controller.solve(plan.model_path)
            if result.get("status") == "error":
                return {
                    "status": "error",
                    "message": result.get("message", "求解失败"),
                }
            if result.get("saved_path"):
                plan.model_path = result["saved_path"]
            return {
                "status": "success",
                "message": "求解成功",
                "solve_info": result
            }
        except Exception as e:
            logger.error(f"求解失败: {e}")
            return {
                "status": "error",
                "message": f"求解失败: {e}"
            }
    
    def execute_retry(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        重试失败的步骤
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        failed_steps = thought.get("parameters", {}).get("failed_steps", [])
        
        if not failed_steps:
            return {
                "status": "error",
                "message": "没有需要重试的步骤"
            }
        
        # 找到失败的步骤并重试
        for step_id in failed_steps:
            for step in plan.execution_path:
                if step.step_id == step_id and step.status == "failed":
                    step.status = "pending"
                    logger.info(f"重置步骤 {step_id} 状态为 pending")
                    break
        
        return {
            "status": "success",
            "message": f"已重置 {len(failed_steps)} 个失败步骤"
        }
    
    def execute_skip(
        self,
        plan: ReActTaskPlan,
        step: ExecutionStep,
        thought: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        跳过失败的步骤
        
        Args:
            plan: 任务计划
            step: 执行步骤
            thought: 思考结果
        
        Returns:
            执行结果
        """
        failed_steps = thought.get("parameters", {}).get("failed_steps", [])
        
        if not failed_steps:
            return {
                "status": "error",
                "message": "没有需要跳过的步骤"
            }
        
        # 标记失败的步骤为跳过
        for step_id in failed_steps:
            for step in plan.execution_path:
                if step.step_id == step_id:
                    step.status = "completed"  # 标记为已完成（实际是跳过）
                    logger.info(f"跳过步骤 {step_id}")
                    break
        
        return {
            "status": "success",
            "message": f"已跳过 {len(failed_steps)} 个失败步骤"
        }
