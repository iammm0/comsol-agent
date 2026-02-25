"""推理引擎"""
import json
import re
from typing import Dict, Any, Optional, List
from uuid import uuid4

from agent.utils.llm import LLMClient
from agent.utils.prompt_loader import prompt_loader
from agent.skills import get_skill_injector
from agent.utils.logger import get_logger
from schemas.task import ReActTaskPlan, ExecutionStep, ReasoningCheckpoint

logger = get_logger(__name__)


class ReasoningEngine:
    """推理引擎 - 负责推理和规划"""
    
    def __init__(self, llm: LLMClient):
        """
        初始化推理引擎
        
        Args:
            llm: LLM 客户端
        """
        self.llm = llm
    
    def understand_and_plan(
        self,
        user_input: str,
        model_name: str
    ) -> ReActTaskPlan:
        """
        理解用户需求并规划任务
        
        Args:
            user_input: 用户输入
            model_name: 模型名称
        
        Returns:
            初始化的任务计划
        """
        logger.info("理解用户需求并规划任务...")
        
        # 使用 LLM 理解需求
        understanding = self.understand_requirement(user_input)
        
        # 规划执行链路
        execution_path = self.plan_execution_path(understanding)
        
        # 规划推理链路
        reasoning_path = self.plan_reasoning_path(execution_path)
        
        # 创建任务计划
        plan = ReActTaskPlan(
            task_id=str(uuid4()),
            model_name=model_name,
            user_input=user_input,
            execution_path=execution_path,
            reasoning_path=reasoning_path,
            status="planning"
        )
        
        logger.info(f"规划完成: {len(execution_path)} 个执行步骤, {len(reasoning_path)} 个检查点")
        
        return plan
    
    def understand_requirement(self, user_input: str) -> Dict[str, Any]:
        """
        理解用户需求
        
        Args:
            user_input: 用户输入
        
        Returns:
            理解结果
        """
        try:
            prompt = prompt_loader.format(
                "react",
                "reasoning",
                user_input=user_input
            )
        except Exception:
            # 如果 Prompt 不存在，使用简单模板
            prompt = f"""
请分析以下 COMSOL 建模需求，识别需要哪些建模步骤：

用户需求：{user_input}

请以 JSON 格式返回分析结果，包含：
- task_type: 任务类型（geometry/physics/study/full）
- required_steps: 需要的步骤列表
- parameters: 关键参数
"""
        prompt = get_skill_injector().inject_into_prompt(user_input, prompt)
        response = self.llm.call(prompt, temperature=0.1)
        
        # 提取 JSON
        understanding = self._extract_json(response)
        
        return understanding
    
    def plan_execution_path(self, understanding: Dict[str, Any]) -> List[ExecutionStep]:
        """
        规划执行链路
        
        Args:
            understanding: 需求理解结果
        
        Returns:
            执行步骤列表
        """
        steps = []
        
        task_type = understanding.get("task_type", "geometry")
        required_steps = understanding.get("required_steps", [])
        
        # 如果没有指定步骤，根据任务类型推断
        if not required_steps:
            if task_type == "geometry":
                required_steps = ["create_geometry"]
            elif task_type == "physics":
                required_steps = ["create_geometry", "add_physics"]
            elif task_type == "study":
                required_steps = ["create_geometry", "add_physics", "configure_study"]
            elif task_type == "full":
                required_steps = ["create_geometry", "add_physics", "generate_mesh", "configure_study", "solve"]
        
        # 创建执行步骤
        for i, step_action in enumerate(required_steps):
            step_type_map = {
                "create_geometry": "geometry",
                "add_physics": "physics",
                "generate_mesh": "mesh",
                "configure_study": "study",
                "solve": "solve"
            }
            
            step_type = step_type_map.get(step_action, "geometry")
            
            step = ExecutionStep(
                step_id=f"step_{i+1}",
                step_type=step_type,
                action=step_action,
                parameters=understanding.get("parameters", {}),
                status="pending"
            )
            steps.append(step)
        
        return steps
    
    def plan_reasoning_path(self, execution_path: List[ExecutionStep]) -> List[ReasoningCheckpoint]:
        """
        规划推理链路（验证点、检查点）
        
        Args:
            execution_path: 执行步骤列表
        
        Returns:
            推理检查点列表
        """
        checkpoints = []
        
        # 为每个执行步骤创建检查点
        for step in execution_path:
            checkpoint = ReasoningCheckpoint(
                checkpoint_id=f"checkpoint_{step.step_id}",
                checkpoint_type="validation",
                description=f"验证 {step.action} 步骤",
                criteria={"step_id": step.step_id},
                status="pending"
            )
            checkpoints.append(checkpoint)
        
        # 添加整体验证检查点
        overall_checkpoint = ReasoningCheckpoint(
            checkpoint_id="checkpoint_overall",
            checkpoint_type="verification",
            description="整体模型验证",
            criteria={"all_steps_complete": True},
            status="pending"
        )
        checkpoints.append(overall_checkpoint)
        
        return checkpoints
    
    def reason(self, plan: ReActTaskPlan) -> Dict[str, Any]:
        """
        推理当前状态，决定下一步行动
        
        Args:
            plan: 当前任务计划
        
        Returns:
            思考结果
        """
        current_step = plan.get_current_step()
        
        # 如果所有步骤都已完成
        if all(step.status == "completed" for step in plan.execution_path):
            return {
                "action": "complete",
                "reasoning": "所有步骤已完成",
                "parameters": {}
            }
        
        # 如果有失败的步骤
        failed_steps = [step for step in plan.execution_path if step.status == "failed"]
        if failed_steps:
            # 尝试修复或跳过
            return {
                "action": "retry" if len(failed_steps) == 1 else "skip",
                "reasoning": f"检测到 {len(failed_steps)} 个失败步骤",
                "parameters": {"failed_steps": [s.step_id for s in failed_steps]}
            }
        
        # 如果有待执行的步骤
        if current_step and current_step.status == "pending":
            return {
                "action": current_step.action,
                "reasoning": f"执行步骤: {current_step.action}",
                "parameters": current_step.parameters
            }
        
        # 默认：继续执行下一步
        if plan.current_step_index < len(plan.execution_path) - 1:
            plan.current_step_index += 1
            next_step = plan.get_current_step()
            if next_step:
                return {
                    "action": next_step.action,
                    "reasoning": f"继续执行下一步: {next_step.action}",
                    "parameters": next_step.parameters
                }
        
        return {
            "action": "complete",
            "reasoning": "没有更多步骤",
            "parameters": {}
        }
    
    def validate_plan(self, plan: ReActTaskPlan) -> Dict[str, Any]:
        """
        验证计划的合理性和完整性
        
        Args:
            plan: 任务计划
        
        Returns:
            验证结果
        """
        errors = []
        warnings = []
        
        # 检查执行路径
        if not plan.execution_path:
            errors.append("执行路径为空")
        
        # 检查步骤顺序
        step_types = [step.step_type for step in plan.execution_path]
        if "geometry" not in step_types and ("physics" in step_types or "mesh" in step_types):
            errors.append("几何建模必须在物理场和网格之前")
        
        if "physics" not in step_types and "study" in step_types:
            warnings.append("研究配置通常需要物理场")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def refine_plan(self, plan: ReActTaskPlan, feedback: str) -> ReActTaskPlan:
        """
        根据反馈改进计划
        
        Args:
            plan: 当前任务计划
            feedback: 反馈信息
        
        Returns:
            改进后的计划
        """
        logger.info(f"根据反馈改进计划: {feedback}")
        
        # 使用 LLM 分析反馈并生成改进建议
        try:
            prompt = f"""
当前任务计划执行遇到问题，请分析反馈并给出改进建议：

任务计划：
{json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)}

反馈信息：
{feedback}

请以 JSON 格式返回改进建议，包含：
- suggested_changes: 建议的变更
- new_steps: 需要添加的新步骤（如果有）
- modified_steps: 需要修改的步骤（如果有）
"""
            prompt = get_skill_injector().inject_into_prompt(feedback, prompt)
            response = self.llm.call(prompt, temperature=0.2)
            suggestions = self._extract_json(response)
            
            # 应用改进建议
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
            
            # 更新现有步骤
            if "modified_steps" in suggestions:
                for mod in suggestions["modified_steps"]:
                    step_id = mod.get("step_id")
                    for step in plan.execution_path:
                        if step.step_id == step_id:
                            if "parameters" in mod:
                                step.parameters.update(mod["parameters"])
                            break
            
        except Exception as e:
            logger.warning(f"改进计划失败: {e}")
        
        return plan
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取第一个 { ... } 块
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # 如果都失败，返回默认值
        logger.warning("无法从响应中提取 JSON，使用默认值")
        return {"task_type": "geometry", "required_steps": ["create_geometry"], "parameters": {}}
