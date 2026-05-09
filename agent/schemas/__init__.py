"""Schemas - Agent 数据结构定义"""
from agent.schemas.geometry import GeometryShape, GeometryPlan, GeometryOperation
from agent.schemas.material import MaterialProperty, MaterialDefinition, MaterialAssignment, MaterialPlan
from agent.schemas.physics import (
    PhysicsField, PhysicsPlan,
    BoundaryCondition, DomainCondition, InitialCondition, CouplingDefinition,
)
from agent.schemas.study import StudyType, StudyPlan, ParametricSweep
from agent.schemas.mesh import MeshPlan, RefinementRegion
from agent.schemas.message import AgentMessage

__all__ = [
    "GeometryShape", "GeometryPlan", "GeometryOperation",
    "MaterialProperty", "MaterialDefinition", "MaterialAssignment", "MaterialPlan",
    "PhysicsField", "PhysicsPlan",
    "BoundaryCondition", "DomainCondition", "InitialCondition", "CouplingDefinition",
    "StudyType", "StudyPlan", "ParametricSweep",
    "MeshPlan", "RefinementRegion",
    "AgentMessage",
]
