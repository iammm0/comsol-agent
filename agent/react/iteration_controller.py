"""迭代控制器"""
from typing import Dict, Any
from datetime import datetime
from uuid import uuid4

from agent.utils.llm import LLMClient
from agent.utils.logger import get_logger
from schemas.task import ReActTaskPlan, Observation, IterationRecord, ExecutionStep

logger = get_logger(__name__)


class IterationController:
    """迭代控制器 - 控制迭代流程"""
    
    def __init__(self, llm: LLMClient):
        """
        初始化迭代控制器
        
        Args:
            llm: LLM 客户端
        """
        self.llm = llm
        self.max_iterations = 10
    
    def should_iterate(
        self,
        plan: ReActTaskPlan,
        observation: Observation
    ) -> bool:
        """
        判断是否需要迭代
        
        Args:
            plan: 任务计划
            observation: 观察结果
        
        Returns:
            是否需要迭代
        """
        # 如果观察结果是错误，需要迭代
        if observation.status == "error":
            return True
        
        # 如果观察结果是警告，可能需要迭代
        if observation.status == "warning":
            # 检查是否有多个警告
            warning_count = sum(1 for obs in plan.observations if obs.status == "warning")
            if warning_count >= 3:
                return True
        
        # 如果所有步骤都已完成，不需要迭代
        if all(step.status == "completed" for step in plan.execution_path):
            return False
        
        # 如果有失败的步骤，需要迭代
        failed_steps = [step for step in plan.execution_path if step.status == "failed"]
        if failed_steps:
            return True
        
        # 如果迭代次数过多，不再迭代
        if len(plan.iterations) >= self.max_iterations:
            logger.warning(f"已达到最大迭代次数: {self.max_iterations}")
            return False
        
        return False
    
    def generate_feedback(
        self,
        plan: ReActTaskPlan,
        observation: Observation
    ) -> str:
        """
        生成反馈信息
        
        Args:
            plan: 任务计划
            observation: 观察结果
        
        Returns:
            反馈信息
        """
        feedback_parts = []
        
        # 添加观察结果
        feedback_parts.append(f"观察结果: {observation.message}")
        
        # 添加当前步骤信息
        current_step = plan.get_current_step()
        if current_step:
            feedback_parts.append(f"当前步骤: {current_step.action} ({current_step.step_type})")
            if current_step.status == "failed":
                feedback_parts.append(f"步骤失败: {current_step.result}")
        
        # 添加历史观察结果摘要
        recent_observations = plan.observations[-5:]  # 最近5个观察结果
        if recent_observations:
            error_count = sum(1 for obs in recent_observations if obs.status == "error")
            warning_count = sum(1 for obs in recent_observations if obs.status == "warning")
            if error_count > 0:
                feedback_parts.append(f"最近有 {error_count} 个错误")
            if warning_count > 0:
                feedback_parts.append(f"最近有 {warning_count} 个警告")
        
        # 添加步骤完成情况
        completed = sum(1 for step in plan.execution_path if step.status == "completed")
        total = len(plan.execution_path)
        feedback_parts.append(f"进度: {completed}/{total} 步骤已完成")
        
        return "\n".join(feedback_parts)
    
    def update_plan(
        self,
        plan: ReActTaskPlan,
        observation: Observation
    ) -> ReActTaskPlan:
        """
        根据观察结果更新计划
        
        Args:
            plan: 当前任务计划
            observation: 观察结果
        
        Returns:
            更新后的计划
        """
        logger.info("更新任务计划...")
        
        # 生成反馈
        feedback = self.generate_feedback(plan, observation)
        
        # 记录迭代
        iteration = IterationRecord(
            iteration_id=len(plan.iterations) + 1,
            reason=observation.message,
            changes={},
            observations=[observation]
        )
        
        # 根据观察结果类型更新计划
        if observation.status == "error":
            plan = self._handle_error(plan, observation, feedback)
        elif observation.status == "warning":
            plan = self._handle_warning(plan, observation, feedback)
        
        # 添加迭代记录
        plan.add_iteration(iteration)
        
        return plan
    
    def _handle_error(
        self,
        plan: ReActTaskPlan,
        observation: Observation,
        feedback: str
    ) -> ReActTaskPlan:
        """
        处理错误情况
        
        Args:
            plan: 任务计划
            observation: 观察结果
            feedback: 反馈信息
        
        Returns:
            更新后的计划
        """
        current_step = plan.get_current_step()
        
        if not current_step:
            logger.warning("无法处理错误：没有当前步骤")
            return plan
        
        # 如果步骤失败，尝试重试或跳过
        if current_step.status == "failed":
            # 检查重试次数
            retry_count = current_step.parameters.get("retry_count", 0)
            
            if retry_count < 3:
                # 重试
                current_step.status = "pending"
                current_step.parameters["retry_count"] = retry_count + 1
                logger.info(f"重试步骤 {current_step.step_id} (第 {retry_count + 1} 次)")
            else:
                # 跳过失败的步骤
                current_step.status = "completed"  # 标记为已完成（实际是跳过）
                logger.warning(f"跳过步骤 {current_step.step_id}（重试次数过多）")
                
                # 移动到下一步
                if plan.current_step_index < len(plan.execution_path) - 1:
                    plan.current_step_index += 1
        
        # 使用 LLM 分析错误并生成改进建议
        try:
            improved_plan = self._llm_refine_plan(plan, feedback)
            return improved_plan
        except Exception as e:
            logger.warning(f"LLM 改进计划失败: {e}")
            return plan
    
    def _handle_warning(
        self,
        plan: ReActTaskPlan,
        observation: Observation,
        feedback: str
    ) -> ReActTaskPlan:
        """
        处理警告情况
        
        Args:
            plan: 任务计划
            observation: 观察结果
            feedback: 反馈信息
        
        Returns:
            更新后的计划
        """
        # 警告通常不需要立即处理，但可以记录
        logger.info(f"收到警告: {observation.message}")
        
        # 如果警告过多，可能需要调整计划
        warning_count = sum(1 for obs in plan.observations if obs.status == "warning")
        if warning_count >= 5:
            logger.warning("警告过多，尝试优化计划")
            try:
                improved_plan = self._llm_refine_plan(plan, feedback)
                return improved_plan
            except Exception as e:
                logger.warning(f"LLM 优化计划失败: {e}")
        
        return plan
    
    def _llm_refine_plan(
        self,
        plan: ReActTaskPlan,
        feedback: str
    ) -> ReActTaskPlan:
        """
        使用 LLM 改进计划
        
        Args:
            plan: 当前任务计划
            feedback: 反馈信息
        
        Returns:
            改进后的计划
        """
        try:
            prompt = f"""
当前 COMSOL 建模任务执行遇到问题，请分析反馈并给出改进建议：

任务计划：
- 模型名称: {plan.model_name}
- 用户需求: {plan.user_input}
- 当前步骤: {plan.current_step_index + 1}/{len(plan.execution_path)}
- 执行步骤: {[step.action for step in plan.execution_path]}

反馈信息：
{feedback}

请以 JSON 格式返回改进建议，包含：
- suggested_changes: 建议的变更（字符串描述）
- new_steps: 需要添加的新步骤列表（如果有）
- modified_steps: 需要修改的步骤列表（包含 step_id 和修改内容）
- skip_current: 是否跳过当前步骤（布尔值）
"""
            
            response = self.llm.call(prompt, temperature=0.2)
            
            # 解析响应（简化处理）
            import json
            import re
            
            # 尝试提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                suggestions = json.loads(json_match.group(0))
                
                # 应用建议
                if suggestions.get("skip_current"):
                    current_step = plan.get_current_step()
                    if current_step:
                        current_step.status = "completed"  # 跳过
                        if plan.current_step_index < len(plan.execution_path) - 1:
                            plan.current_step_index += 1
                
                # 添加新步骤（如果需要）
                if "new_steps" in suggestions:
                    for step_data in suggestions["new_steps"]:
                        new_step = ExecutionStep(
                            step_id=f"step_{len(plan.execution_path) + 1}",
                            step_type=step_data.get("step_type", "geometry"),
                            action=step_data.get("action", "create_geometry"),
                            parameters=step_data.get("parameters", {}),
                            status="pending"
                        )
                        plan.execution_path.append(new_step)
                
                # 修改现有步骤
                if "modified_steps" in suggestions:
                    for mod in suggestions["modified_steps"]:
                        step_id = mod.get("step_id")
                        for step in plan.execution_path:
                            if step.step_id == step_id:
                                if "parameters" in mod:
                                    step.parameters.update(mod["parameters"])
                                if "action" in mod:
                                    step.action = mod["action"]
                                break
                
                logger.info("计划已根据 LLM 建议更新")
            
        except Exception as e:
            logger.warning(f"LLM 改进计划失败: {e}")
        
        return plan
