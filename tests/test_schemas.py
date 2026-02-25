"""Schemas 单元测试：geometry / physics / study / task 的序列化、反序列化与校验。"""
import pytest
from pydantic import ValidationError

from schemas.geometry import GeometryPlan, GeometryShape
from schemas.physics import PhysicsPlan, PhysicsField
from schemas.study import StudyPlan, StudyType
from schemas.task import (
    ExecutionStep,
    ReasoningCheckpoint,
    Observation,
    IterationRecord,
    TaskPlan,
    ReActTaskPlan,
)


class TestGeometryShape:
    """GeometryShape 校验与序列化"""

    def test_rectangle_valid(self):
        s = GeometryShape(
            type="rectangle",
            parameters={"width": 1.0, "height": 0.5},
            position={"x": 0.0, "y": 0.0},
            name="r1",
        )
        assert s.type == "rectangle"
        assert s.parameters["width"] == 1.0
        assert s.parameters["height"] == 0.5

    def test_rectangle_missing_params(self):
        with pytest.raises(ValidationError):
            GeometryShape(type="rectangle", parameters={})

    def test_circle_valid(self):
        s = GeometryShape(type="circle", parameters={"radius": 0.3}, name="c1")
        assert s.type == "circle"
        assert s.parameters["radius"] == 0.3

    def test_ellipse_valid(self):
        s = GeometryShape(
            type="ellipse",
            parameters={"a": 1.0, "b": 0.6},
            position={"x": 0.5, "y": 0.5},
        )
        assert s.parameters["a"] == 1.0
        assert s.parameters["b"] == 0.6


class TestGeometryPlan:
    """GeometryPlan 序列化与反序列化"""

    def test_to_dict(self):
        plan = GeometryPlan(
            model_name="test",
            units="m",
            shapes=[
                GeometryShape(
                    type="rectangle",
                    parameters={"width": 1.0, "height": 0.5},
                    position={"x": 0.0, "y": 0.0},
                    name="rect1",
                )
            ],
        )
        d = plan.to_dict()
        assert d["model_name"] == "test"
        assert d["units"] == "m"
        assert len(d["shapes"]) == 1
        assert d["shapes"][0]["type"] == "rectangle"
        assert d["shapes"][0]["parameters"]["width"] == 1.0

    def test_from_dict(self):
        d = {
            "model_name": "test",
            "units": "m",
            "shapes": [
                {
                    "type": "circle",
                    "parameters": {"radius": 0.3},
                    "position": {"x": 0.0, "y": 0.0},
                    "name": "c1",
                }
            ],
        }
        plan = GeometryPlan.from_dict(d)
        assert plan.model_name == "test"
        assert len(plan.shapes) == 1
        assert plan.shapes[0].type == "circle"
        assert plan.shapes[0].parameters["radius"] == 0.3


class TestPhysicsPlan:
    """PhysicsPlan / PhysicsField"""

    def test_physics_plan_to_dict(self):
        plan = PhysicsPlan(
            fields=[
                PhysicsField(type="heat", parameters={"boundary_conditions": {}}),
            ]
        )
        d = plan.model_dump()
        assert "fields" in d
        assert len(d["fields"]) == 1
        assert d["fields"][0]["type"] == "heat"

    def test_physics_field_types(self):
        for t in ("heat", "electromagnetic", "structural", "fluid"):
            f = PhysicsField(type=t, parameters={})
            assert f.type == t


class TestStudyPlan:
    """StudyPlan / StudyType"""

    def test_study_plan_to_dict(self):
        plan = StudyPlan(
            studies=[
                StudyType(type="stationary", parameters={}),
                StudyType(type="time_dependent", parameters={"t_range": [0, 1]}),
            ]
        )
        d = plan.model_dump()
        assert len(d["studies"]) == 2
        assert d["studies"][0]["type"] == "stationary"
        assert d["studies"][1]["type"] == "time_dependent"


class TestTaskPlan:
    """TaskPlan / ReActTaskPlan / ExecutionStep / Observation 等"""

    def test_execution_step(self):
        step = ExecutionStep(
            step_id="step_1",
            step_type="geometry",
            action="create_geometry",
            status="pending",
        )
        assert step.step_type == "geometry"
        assert step.action == "create_geometry"

    def test_react_task_plan_get_current_step(self):
        plan = ReActTaskPlan(
            task_id="t1",
            model_name="m1",
            user_input="创建一个矩形",
            execution_path=[
                ExecutionStep(step_id="s1", step_type="geometry", action="create_geometry"),
                ExecutionStep(step_id="s2", step_type="physics", action="add_physics"),
            ],
            current_step_index=0,
        )
        current = plan.get_current_step()
        assert current is not None
        assert current.step_id == "s1"
        plan.current_step_index = 1
        assert plan.get_current_step().step_id == "s2"
        plan.current_step_index = 10
        assert plan.get_current_step() is None

    def test_react_task_plan_add_observation(self):
        plan = ReActTaskPlan(task_id="t1", model_name="m1", user_input="test")
        obs = Observation(
            observation_id="o1",
            step_id="s1",
            status="success",
            message="ok",
        )
        plan.add_observation(obs)
        assert len(plan.observations) == 1
        assert plan.observations[0].message == "ok"
