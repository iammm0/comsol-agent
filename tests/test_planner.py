"""Planner Agent 单元测试"""
import pytest
from unittest.mock import Mock, patch

from src.planner.agent import PlannerAgent
from src.planner.schema import GeometryPlan, GeometryShape


class TestPlannerAgent:
    """Planner Agent 测试类"""
    
    @pytest.fixture
    def planner(self):
        """创建 Planner Agent 实例"""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "test_key"}):
            return PlannerAgent(api_key="test_key")
    
    def test_extract_json_from_response(self, planner):
        """测试从响应中提取 JSON"""
        # 测试直接 JSON
        response1 = '{"model_name": "test", "units": "m", "shapes": []}'
        result1 = planner._extract_json_from_response(response1)
        assert result1["model_name"] == "test"
        
        # 测试代码块中的 JSON
        response2 = '```json\n{"model_name": "test2", "units": "m", "shapes": []}\n```'
        result2 = planner._extract_json_from_response(response2)
        assert result2["model_name"] == "test2"
        
        # 测试包含其他文字的响应
        response3 = '这是响应内容 {"model_name": "test3", "units": "m", "shapes": []} 结束'
        result3 = planner._extract_json_from_response(response3)
        assert result3["model_name"] == "test3"
    
    @patch('src.planner.agent.Generation.call')
    def test_parse_rectangle(self, mock_call, planner):
        """测试解析矩形描述"""
        # Mock LLM 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output.choices = [Mock()]
        mock_response.output.choices[0].message.content = '''{
            "model_name": "test_model",
            "units": "m",
            "shapes": [
                {
                    "type": "rectangle",
                    "parameters": {"width": 1.0, "height": 0.5},
                    "position": {"x": 0.0, "y": 0.0},
                    "name": "rect1"
                }
            ]
        }'''
        mock_call.return_value = mock_response
        
        # 测试解析
        plan = planner.parse("创建一个宽1米、高0.5米的矩形")
        
        assert isinstance(plan, GeometryPlan)
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "rectangle"
        assert plan.shapes[0].parameters["width"] == 1.0
        assert plan.shapes[0].parameters["height"] == 0.5
    
    @patch('src.planner.agent.Generation.call')
    def test_parse_circle(self, mock_call, planner):
        """测试解析圆形描述"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output.choices = [Mock()]
        mock_response.output.choices[0].message.content = '''{
            "model_name": "test_model",
            "units": "m",
            "shapes": [
                {
                    "type": "circle",
                    "parameters": {"radius": 0.3},
                    "position": {"x": 0.0, "y": 0.0},
                    "name": "circ1"
                }
            ]
        }'''
        mock_call.return_value = mock_response
        
        plan = planner.parse("在原点放置一个半径为0.3米的圆")
        
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "circle"
        assert plan.shapes[0].parameters["radius"] == 0.3
    
    @patch('src.planner.agent.Generation.call')
    def test_parse_ellipse(self, mock_call, planner):
        """测试解析椭圆描述"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output.choices = [Mock()]
        mock_response.output.choices[0].message.content = '''{
            "model_name": "test_model",
            "units": "m",
            "shapes": [
                {
                    "type": "ellipse",
                    "parameters": {"a": 1.0, "b": 0.6},
                    "position": {"x": 0.5, "y": 0.5},
                    "name": "ell1"
                }
            ]
        }'''
        mock_call.return_value = mock_response
        
        plan = planner.parse("创建一个长轴1米、短轴0.6米的椭圆，中心在(0.5, 0.5)")
        
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "ellipse"
        assert plan.shapes[0].parameters["a"] == 1.0
        assert plan.shapes[0].parameters["b"] == 0.6
        assert plan.shapes[0].position["x"] == 0.5
        assert plan.shapes[0].position["y"] == 0.5


class TestGeometrySchema:
    """几何数据结构测试"""
    
    def test_rectangle_shape(self):
        """测试矩形形状验证"""
        shape = GeometryShape(
            type="rectangle",
            parameters={"width": 1.0, "height": 0.5},
            position={"x": 0.0, "y": 0.0}
        )
        assert shape.type == "rectangle"
        assert shape.parameters["width"] == 1.0
        assert shape.parameters["height"] == 0.5
    
    def test_circle_shape(self):
        """测试圆形形状验证"""
        shape = GeometryShape(
            type="circle",
            parameters={"radius": 0.3},
            position={"x": 0.0, "y": 0.0}
        )
        assert shape.type == "circle"
        assert shape.parameters["radius"] == 0.3
    
    def test_ellipse_shape(self):
        """测试椭圆形状验证"""
        shape = GeometryShape(
            type="ellipse",
            parameters={"a": 1.0, "b": 0.6},
            position={"x": 0.5, "y": 0.5}
        )
        assert shape.type == "ellipse"
        assert shape.parameters["a"] == 1.0
        assert shape.parameters["b"] == 0.6
    
    def test_invalid_rectangle(self):
        """测试无效矩形参数"""
        with pytest.raises(ValueError):
            GeometryShape(
                type="rectangle",
                parameters={"width": 1.0},  # 缺少 height
                position={"x": 0.0, "y": 0.0}
            )
    
    def test_invalid_circle(self):
        """测试无效圆形参数"""
        with pytest.raises(ValueError):
            GeometryShape(
                type="circle",
                parameters={},  # 缺少 radius
                position={"x": 0.0, "y": 0.0}
            )
    
    def test_geometry_plan(self):
        """测试几何计划"""
        shapes = [
            GeometryShape(
                type="rectangle",
                parameters={"width": 1.0, "height": 0.5},
                position={"x": 0.0, "y": 0.0}
            )
        ]
        plan = GeometryPlan(shapes=shapes, model_name="test_model")
        assert len(plan.shapes) == 1
        assert plan.model_name == "test_model"
        assert plan.units == "m"
    
    def test_empty_plan(self):
        """测试空计划（应该失败）"""
        with pytest.raises(ValueError):
            GeometryPlan(shapes=[], model_name="test_model")
