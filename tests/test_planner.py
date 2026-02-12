"""Planner Agent 单元测试（使用 agent 包）。"""
import pytest
from unittest.mock import Mock, patch

from schemas.geometry import GeometryPlan, GeometryShape


class TestPlannerAgent:
    """Planner（GeometryAgent）测试类"""

    @pytest.fixture
    def planner(self):
        with patch("agent.planner.geometry_agent.LLMClient") as mock_llm_cls:
            mock_llm_cls.return_value.call = Mock(return_value="")
            from agent.planner.geometry_agent import GeometryAgent
            return GeometryAgent(backend="dashscope", api_key="test_key")

    def test_extract_json_from_response(self, planner):
        """测试从响应中提取 JSON"""
        response1 = '{"model_name": "test", "units": "m", "shapes": [{"type": "rectangle", "parameters": {"width": 1.0, "height": 0.5}, "position": {"x": 0.0, "y": 0.0}, "name": "r1"}]}'
        result1 = planner._extract_json_from_response(response1)
        assert result1["model_name"] == "test"

        response2 = '```json\n{"model_name": "test2", "units": "m", "shapes": [{"type": "rectangle", "parameters": {"width": 1.0, "height": 0.5}, "position": {"x": 0.0, "y": 0.0}, "name": "r1"}]}\n```'
        result2 = planner._extract_json_from_response(response2)
        assert result2["model_name"] == "test2"

        response3 = '文字 {"model_name": "test3", "units": "m", "shapes": [{"type": "rectangle", "parameters": {"width": 1.0, "height": 0.5}, "position": {"x": 0.0, "y": 0.0}, "name": "r1"}]} 结束'
        result3 = planner._extract_json_from_response(response3)
        assert result3["model_name"] == "test3"

    def test_parse_rectangle(self, planner):
        planner.llm = Mock()
        planner.llm.call = Mock(return_value="""{
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
        }""")
        plan = planner.parse("创建一个宽1米、高0.5米的矩形")
        assert isinstance(plan, GeometryPlan)
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "rectangle"
        assert plan.shapes[0].parameters["width"] == 1.0
        assert plan.shapes[0].parameters["height"] == 0.5

    def test_parse_circle(self, planner):
        planner.llm = Mock()
        planner.llm.call = Mock(return_value="""{
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
        }""")
        plan = planner.parse("在原点放置一个半径为0.3米的圆")
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "circle"
        assert plan.shapes[0].parameters["radius"] == 0.3

    def test_parse_ellipse(self, planner):
        planner.llm = Mock()
        planner.llm.call = Mock(return_value="""{
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
        }""")
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
        shape = GeometryShape(
            type="rectangle",
            parameters={"width": 1.0, "height": 0.5},
            position={"x": 0.0, "y": 0.0},
        )
        assert shape.type == "rectangle"
        assert shape.parameters["width"] == 1.0
        assert shape.parameters["height"] == 0.5

    def test_circle_shape(self):
        shape = GeometryShape(
            type="circle",
            parameters={"radius": 0.3},
            position={"x": 0.0, "y": 0.0},
        )
        assert shape.type == "circle"
        assert shape.parameters["radius"] == 0.3

    def test_ellipse_shape(self):
        shape = GeometryShape(
            type="ellipse",
            parameters={"a": 1.0, "b": 0.6},
            position={"x": 0.5, "y": 0.5},
        )
        assert shape.type == "ellipse"
        assert shape.parameters["a"] == 1.0
        assert shape.parameters["b"] == 0.6

    def test_invalid_rectangle(self):
        with pytest.raises(ValueError):
            GeometryShape(
                type="rectangle",
                parameters={"width": 1.0},
                position={"x": 0.0, "y": 0.0},
            )

    def test_invalid_circle(self):
        with pytest.raises(ValueError):
            GeometryShape(
                type="circle",
                parameters={},
                position={"x": 0.0, "y": 0.0},
            )

    def test_geometry_plan(self):
        shapes = [
            GeometryShape(
                type="rectangle",
                parameters={"width": 1.0, "height": 0.5},
                position={"x": 0.0, "y": 0.0},
            )
        ]
        plan = GeometryPlan(shapes=shapes, model_name="test_model")
        assert len(plan.shapes) == 1
        assert plan.model_name == "test_model"
        assert plan.units == "m"

    def test_empty_plan(self):
        with pytest.raises(ValueError):
            GeometryPlan(shapes=[], model_name="test_model")
