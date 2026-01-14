"""Planner Agent - 将自然语言解析为结构化 JSON"""
import json
import re
from typing import Optional

import dashscope
from dashscope import Generation
from loguru import logger

from src.planner.schema import GeometryPlan, GeometryShape
from src.utils.config import settings


class PlannerAgent:
    """Planner Agent - 解析自然语言为结构化 JSON"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Planner Agent
        
        Args:
            api_key: Dashscope API Key，如果为 None 则从配置读取
        """
        self.api_key = api_key or settings.dashscope_api_key
        if not self.api_key:
            raise ValueError("Dashscope API Key 未配置，请设置 DASHSCOPE_API_KEY")
        
        dashscope.api_key = self.api_key
    
    def _create_prompt(self, user_input: str) -> str:
        """创建 LLM Prompt"""
        schema_example = {
            "model_name": "geometry_model",
            "units": "m",
            "shapes": [
                {
                    "type": "rectangle",
                    "parameters": {"width": 1.0, "height": 0.5},
                    "position": {"x": 0.0, "y": 0.0},
                    "name": "rect1"
                },
                {
                    "type": "circle",
                    "parameters": {"radius": 0.3},
                    "position": {"x": 0.0, "y": 0.0},
                    "name": "circ1"
                },
                {
                    "type": "ellipse",
                    "parameters": {"a": 1.0, "b": 0.6},
                    "position": {"x": 0.5, "y": 0.5},
                    "name": "ell1"
                }
            ]
        }
        
        prompt = f"""你是一个专业的几何建模助手。请将用户的自然语言描述转换为结构化的 JSON 格式。

支持的几何形状类型：
1. rectangle（矩形）：需要 width（宽度）和 height（高度）参数
2. circle（圆形）：需要 radius（半径）参数
3. ellipse（椭圆）：需要 a（长轴）和 b（短轴）参数

位置参数 position 包含 x 和 y 坐标，默认为 (0.0, 0.0)。

单位默认为米（m）。

用户输入：{user_input}

请严格按照以下 JSON 格式输出，只输出 JSON，不要包含其他文字说明：
{json.dumps(schema_example, ensure_ascii=False, indent=2)}

注意：
- 如果用户没有指定位置，使用默认位置 (0.0, 0.0)
- 如果用户没有指定单位，使用 "m"（米）
- 确保所有数值都是浮点数
- 形状名称可以自动生成（如 rect1, circ1, ell1 等）
"""
        return prompt
    
    def _extract_json_from_response(self, response_text: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取第一个 { ... } 块
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"无法从响应中提取有效的 JSON: {response_text[:200]}")
    
    def parse(self, user_input: str, max_retries: int = 3) -> GeometryPlan:
        """
        解析自然语言输入为结构化 JSON
        
        Args:
            user_input: 用户自然语言描述
            max_retries: 最大重试次数
        
        Returns:
            GeometryPlan 对象
        
        Raises:
            ValueError: 解析失败
        """
        logger.info(f"解析用户输入: {user_input}")
        
        prompt = self._create_prompt(user_input)
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"尝试第 {attempt + 1} 次调用 LLM")
                
                # 调用 Qwen API
                response = Generation.call(
                    model=Generation.Models.qwen_turbo,
                    prompt=prompt,
                    result_format='message',
                    temperature=0.1,  # 降低温度以获得更稳定的输出
                )
                
                if response.status_code != 200:
                    raise ValueError(f"API 调用失败: {response.message}")
                
                # 提取响应内容
                response_text = response.output.choices[0].message.content
                logger.debug(f"LLM 响应: {response_text[:200]}...")
                
                # 提取 JSON
                json_data = self._extract_json_from_response(response_text)
                
                # 验证并创建 GeometryPlan
                plan = GeometryPlan.from_dict(json_data)
                
                logger.info(f"解析成功: {len(plan.shapes)} 个形状")
                return plan
                
            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次尝试失败: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"解析失败，已重试 {max_retries} 次")
                    raise ValueError(f"解析失败: {e}") from e
        
        raise ValueError("解析失败，已达到最大重试次数")
