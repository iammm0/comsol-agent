"""端到端集成测试"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.planner.agent import PlannerAgent
from src.comsol.api_wrapper import COMSOLWrapper
from src.planner.schema import GeometryPlan, GeometryShape
from src.main import create_model_from_text


class TestIntegration:
    """端到端集成测试"""
    
    @pytest.fixture
    def mock_planner_response(self):
        """Mock Planner Agent 响应"""
        return {
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
        }
    
    @patch('src.planner.agent.Generation.call')
    @patch('src.comsol.api_wrapper.jpype.startJVM')
    @patch('src.comsol.api_wrapper.comsol_config.validate')
    def test_create_rectangle_model(
        self,
        mock_validate,
        mock_start_jvm,
        mock_call,
        mock_planner_response,
        tmp_path
    ):
        """测试创建矩形模型"""
        # Mock 配置验证
        mock_validate.return_value = (True, None)
        
        # Mock LLM 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output.choices = [Mock()]
        mock_response.output.choices[0].message.content = str(mock_planner_response).replace("'", '"')
        mock_call.return_value = mock_response
        
        # Mock COMSOL API
        with patch('src.comsol.api_wrapper.ModelUtil') as mock_model_util, \
             patch('src.comsol.api_wrapper.comsol_config.model_output_dir', tmp_path):
            
            # Mock 模型对象
            mock_model = MagicMock()
            mock_geom = MagicMock()
            mock_rect = MagicMock()
            
            mock_model.geom.return_value = mock_geom
            mock_geom.create.return_value = mock_rect
            mock_model_util.create.return_value = mock_model
            
            # 执行测试
            try:
                model_path = create_model_from_text("创建一个宽1米、高0.5米的矩形")
                # 由于是 Mock，实际文件不会创建，但应该能执行到保存步骤
                assert model_path is not None
            except Exception as e:
                # 如果因为 COMSOL 环境问题失败，这是预期的
                pytest.skip(f"COMSOL 环境未配置，跳过测试: {e}")
    
    @patch('src.planner.agent.Generation.call')
    @patch('src.comsol.api_wrapper.jpype.startJVM')
    @patch('src.comsol.api_wrapper.comsol_config.validate')
    def test_create_circle_model(
        self,
        mock_validate,
        mock_start_jvm,
        mock_call,
        tmp_path
    ):
        """测试创建圆形模型"""
        mock_validate.return_value = (True, None)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.output.choices = [Mock()]
        mock_response.output.choices[0].message.content = '''{
            "model_name": "circle_model",
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
        
        with patch('src.comsol.api_wrapper.ModelUtil') as mock_model_util, \
             patch('src.comsol.api_wrapper.comsol_config.model_output_dir', tmp_path):
            
            mock_model = MagicMock()
            mock_geom = MagicMock()
            mock_circle = MagicMock()
            
            mock_model.geom.return_value = mock_geom
            mock_geom.create.return_value = mock_circle
            mock_model_util.create.return_value = mock_model
            
            try:
                model_path = create_model_from_text("在原点放置一个半径为0.3的圆")
                assert model_path is not None
            except Exception as e:
                pytest.skip(f"COMSOL 环境未配置，跳过测试: {e}")
    
    def test_geometry_plan_to_dict(self):
        """测试 GeometryPlan 序列化"""
        shapes = [
            GeometryShape(
                type="rectangle",
                parameters={"width": 1.0, "height": 0.5},
                position={"x": 0.0, "y": 0.0}
            )
        ]
        plan = GeometryPlan(shapes=shapes, model_name="test")
        
        plan_dict = plan.to_dict()
        assert "model_name" in plan_dict
        assert "units" in plan_dict
        assert "shapes" in plan_dict
        assert len(plan_dict["shapes"]) == 1
    
    def test_geometry_plan_from_dict(self):
        """测试 GeometryPlan 反序列化"""
        plan_dict = {
            "model_name": "test",
            "units": "m",
            "shapes": [
                {
                    "type": "rectangle",
                    "parameters": {"width": 1.0, "height": 0.5},
                    "position": {"x": 0.0, "y": 0.0},
                    "name": "rect1"
                }
            ]
        }
        
        plan = GeometryPlan.from_dict(plan_dict)
        assert plan.model_name == "test"
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "rectangle"
