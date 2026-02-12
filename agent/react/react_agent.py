"""ReAct Agent 核心类"""
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import uuid4

from agent.react.reasoning_engine import ReasoningEngine
from agent.react.action_executor import ActionExecutor
from agent.react.observer import Observer
from agent.react.iteration_controller import IterationController
from agent.utils.llm import LLMClient
from agent.utils.logger import get_logger
from agent.utils.config import get_settings
from agent.events import EventBus, EventType
from schemas.task import ReActTaskPlan, ExecutionStep, Observation

logger = get_logger(__name__)


class ReActAgent:
    """ReAct Agent - 协调推理和执行；可选 EventBus 用于可观测。"""

    def __init__(
        self,
        backend: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: int = 10,
        event_bus: Optional[EventBus] = None,
    ):
        settings = get_settings()
        self._event_bus = event_bus

        self.llm = LLMClient(
            backend=backend or settings.llm_backend,
            api_key=api_key or settings.get_api_key_for_backend(backend or settings.llm_backend),
            base_url=base_url or settings.get_base_url_for_backend(backend or settings.llm_backend),
            ollama_url=ollama_url or settings.ollama_url,
            model=model or settings.get_model_for_backend(backend or settings.llm_backend),
        )

        self.reasoning_engine = ReasoningEngine(self.llm)
        self.action_executor = ActionExecutor(event_bus=event_bus)
        self.observer = Observer()
        self.iteration_controller = IterationController(self.llm)

        self.max_iterations = max_iterations
    
    def run(self, user_input: str, output_filename: Optional[str] = None) -> Path:
        """
        执行完整的 ReAct 流程
        
        Args:
            user_input: 用户自然语言输入
            output_filename: 输出文件名（可选）
        
        Returns:
            生成的模型文件路径
        
        Raises:
            RuntimeError: 执行失败
        """
        logger.info("=" * 60)
        logger.info("开始 ReAct 流程")
        logger.info("=" * 60)
        logger.info(f"用户输入: {user_input}")
        
        # 初始化任务计划
        plan = self._initial_plan(user_input, output_filename)
        
        # ReAct 主循环
        for iteration in range(self.max_iterations):
            logger.info("\n--- 迭代 %s/%s ---", iteration + 1, self.max_iterations)
            if self._event_bus:
                self._event_bus.emit_type(EventType.TASK_PHASE, {"phase": "react", "iteration": iteration + 1})

            try:
                thought = self.think(plan)
                logger.info("[Think] %s", thought.get("action", "N/A"))
                if self._event_bus:
                    self._event_bus.emit_type(EventType.THINK_CHUNK, {"thought": thought}, iteration=iteration + 1)

                if thought.get("action") == "complete":
                    logger.info("[Act] 任务已完成")
                    if self._event_bus:
                        self._event_bus.emit_type(EventType.ACTION_END, {"action": "complete"})
                    break

                if self._event_bus:
                    self._event_bus.emit_type(EventType.ACTION_START, {"thought": thought}, iteration=iteration + 1)
                result = self.act(plan, thought)
                logger.info("[Act] 执行结果: %s", result.get("status", "N/A"))
                if self._event_bus:
                    self._event_bus.emit_type(EventType.EXEC_RESULT, {"result": result}, iteration=iteration + 1)

                observation = self.observe(plan, result)
                logger.info("[Observe] %s", observation.message)
                if self._event_bus:
                    self._event_bus.emit_type(EventType.OBSERVATION, {"observation": observation.message, "status": observation.status}, iteration=iteration + 1)
                
                # 判断是否完成
                if observation.status == "success" and self._is_all_steps_complete(plan):
                    plan.status = "completed"
                    logger.info("✅ 所有步骤已完成")
                    break
                
                # Iterate: 根据观察结果更新计划
                if observation.status == "error" or observation.status == "warning":
                    plan = self.iterate(plan, observation)
                    logger.info(f"[Iterate] 计划已更新，当前步骤: {plan.current_step_index}")
                
            except Exception as e:
                logger.error(f"迭代 {iteration + 1} 失败: {e}")
                plan.status = "failed"
                plan.error = str(e)
                raise RuntimeError(f"ReAct 流程失败: {e}") from e
        
        # 检查最终状态
        if plan.status != "completed":
            if plan.status == "failed":
                raise RuntimeError(f"任务失败: {plan.error}")
            else:
                raise RuntimeError(f"任务未完成（达到最大迭代次数: {self.max_iterations}）")
        
        # 保存模型
        if plan.model_path:
            model_path = Path(plan.model_path)
            if model_path.exists():
                logger.info(f"✅ 模型已生成: {model_path}")
                return model_path
        
        raise RuntimeError("模型文件未生成")
    
    def think(self, plan: ReActTaskPlan) -> Dict[str, Any]:
        """
        推理当前状态，规划下一步行动
        
        Args:
            plan: 当前任务计划
        
        Returns:
            思考结果，包含下一步行动
        """
        plan.status = "planning"
        
        # 使用推理引擎进行推理
        thought = self.reasoning_engine.reason(plan)
        
        return thought
    
    def act(self, plan: ReActTaskPlan, thought: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行具体的建模操作
        
        Args:
            plan: 当前任务计划
            thought: 思考结果
        
        Returns:
            执行结果
        """
        plan.status = "executing"
        
        action = thought.get("action")
        if not action:
            return {"status": "error", "message": "未指定行动"}
        
        # 获取当前步骤
        current_step = plan.get_current_step()
        if not current_step:
            # 如果没有当前步骤，根据 action 创建新步骤
            current_step = self._create_step_from_action(action, thought)
            plan.execution_path.append(current_step)
            plan.current_step_index = len(plan.execution_path) - 1
        
        current_step.status = "running"
        
        try:
            # 执行行动
            result = self.action_executor.execute(plan, current_step, thought)
            
            current_step.status = "completed" if result.get("status") == "success" else "failed"
            current_step.result = result
            
            # 更新计划状态
            if result.get("status") == "success":
                # 移动到下一步
                if plan.current_step_index < len(plan.execution_path) - 1:
                    plan.current_step_index += 1
                else:
                    # 所有步骤完成
                    plan.status = "completed"
            
            return result
            
        except Exception as e:
            current_step.status = "failed"
            current_step.result = {"error": str(e)}
            logger.error(f"执行步骤失败: {e}")
            return {"status": "error", "message": str(e)}
    
    def observe(self, plan: ReActTaskPlan, result: Dict[str, Any]) -> Observation:
        """
        观察执行结果
        
        Args:
            plan: 当前任务计划
            result: 执行结果
        
        Returns:
            观察结果
        """
        plan.status = "observing"
        
        current_step = plan.get_current_step()
        if not current_step:
            return Observation(
                observation_id=str(uuid4()),
                step_id="unknown",
                status="error",
                message="无法观察：没有当前步骤"
            )
        
        # 使用观察器进行观察
        observation = self.observer.observe(plan, current_step, result)
        
        # 添加到计划
        plan.add_observation(observation)
        
        return observation
    
    def iterate(self, plan: ReActTaskPlan, observation: Observation) -> ReActTaskPlan:
        """
        根据观察结果改进计划
        
        Args:
            plan: 当前任务计划
            observation: 观察结果
        
        Returns:
            更新后的计划
        """
        plan.status = "iterating"
        
        # 使用迭代控制器更新计划
        updated_plan = self.iteration_controller.update_plan(plan, observation)
        
        return updated_plan
    
    def _initial_plan(self, user_input: str, output_filename: Optional[str] = None) -> ReActTaskPlan:
        """
        初始化任务计划
        
        Args:
            user_input: 用户输入
            output_filename: 输出文件名
        
        Returns:
            初始化的任务计划
        """
        task_id = str(uuid4())
        model_name = output_filename.replace(".mph", "") if output_filename else f"model_{task_id[:8]}"
        
        # 使用推理引擎理解需求并规划
        initial_plan = self.reasoning_engine.understand_and_plan(user_input, model_name)
        
        # 添加 geometry_plan 属性占位符（用于存储几何计划）
        initial_plan.geometry_plan = None
        
        return initial_plan
    
    def _create_step_from_action(self, action: str, thought: Dict[str, Any]) -> ExecutionStep:
        """
        根据行动创建执行步骤
        
        Args:
            action: 行动类型
            thought: 思考结果
        
        Returns:
            执行步骤
        """
        step_id = str(uuid4())
        
        # 根据 action 确定步骤类型
        step_type_map = {
            "create_geometry": "geometry",
            "add_physics": "physics",
            "generate_mesh": "mesh",
            "configure_study": "study",
            "solve": "solve"
        }
        
        step_type = step_type_map.get(action, "geometry")
        
        return ExecutionStep(
            step_id=step_id,
            step_type=step_type,
            action=action,
            parameters=thought.get("parameters", {}),
            status="pending"
        )
    
    def _is_all_steps_complete(self, plan: ReActTaskPlan) -> bool:
        """检查是否所有步骤都已完成"""
        if not plan.execution_path:
            return False
        
        return all(step.status == "completed" for step in plan.execution_path)
