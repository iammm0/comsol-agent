"""Task schemas used by planning and ReAct execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator  # type: ignore[import-not-found]

from schemas.geometry import GeometryPlan
from schemas.material import MaterialPlan
from schemas.mesh import MeshPlan
from schemas.physics import PhysicsPlan
from schemas.study import StudyPlan


class GlobalDefinitionPlan(BaseModel):
    """A single global parameter definition."""

    name: str = Field(..., description="Parameter name")
    value: str = Field(..., description="Expression/value used by COMSOL param()")
    unit: Optional[str] = Field(default=None, description="Optional unit")
    description: Optional[str] = Field(default=None, description="Optional description")


class ExecutionStep(BaseModel):
    """A step in the executable path."""

    step_id: str = Field(..., description="Step id")
    step_type: Literal[
        "geometry",
        "global",
        "material",
        "physics",
        "mesh",
        "study",
        "solve",
        "selection",
        "geometry_io",
        "postprocess",
        "java_api",
    ] = Field(..., description="Step type")
    action: str = Field(..., description="Action name")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    status: Literal["pending", "running", "warning", "completed", "failed", "skipped"] = Field(
        default="pending", description="Execution status"
    )
    result: Optional[Dict[str, Any]] = Field(default=None, description="Step result")


class ReasoningCheckpoint(BaseModel):
    """A reasoning checkpoint for validation/verification."""

    checkpoint_id: str = Field(..., description="Checkpoint id")
    checkpoint_type: Literal["validation", "verification", "optimization"] = Field(
        ..., description="Checkpoint type"
    )
    description: str = Field(..., description="Checkpoint description")
    criteria: Dict[str, Any] = Field(default_factory=dict, description="Checkpoint criteria")
    status: Literal["pending", "passed", "failed"] = Field(
        default="pending", description="Checkpoint status"
    )
    feedback: Optional[str] = Field(default=None, description="Checkpoint feedback")


class Observation(BaseModel):
    """Observation generated after step execution."""

    observation_id: str = Field(..., description="Observation id")
    step_id: str = Field(..., description="Related step id")
    timestamp: datetime = Field(default_factory=datetime.now, description="Observation time")
    status: Literal["success", "warning", "error"] = Field(..., description="Observation status")
    message: str = Field(..., description="Observation message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Observation data")


class IterationRecord(BaseModel):
    """Iteration history entry."""

    iteration_id: int = Field(..., description="Iteration index")
    timestamp: datetime = Field(default_factory=datetime.now, description="Iteration time")
    reason: str = Field(..., description="Iteration reason")
    changes: Dict[str, Any] = Field(default_factory=dict, description="Plan changes")
    observations: List[Observation] = Field(default_factory=list, description="Iteration observations")


class ErrorAnalysisResult(BaseModel):
    """Error analysis output used by iteration controller."""

    error_type: str = Field(..., description="Error category")
    suggested_agent: Optional[Literal["geometry", "material", "physics", "study"]] = Field(
        default=None, description="Suggested planner agent"
    )
    suggested_rollback_step_id: Optional[str] = Field(
        default=None, description="Suggested rollback step id"
    )
    suggested_reason: Optional[str] = Field(default=None, description="Suggested reason")
    suggest_reorchestrate: bool = Field(
        default=False, description="Whether planner re-orchestration is suggested"
    )
    raw_message: Optional[str] = Field(default=None, description="Raw error message")


class ClarifyingOption(BaseModel):
    """One option in a clarifying question."""

    id: str = Field(..., description="Option id")
    label: str = Field(..., description="Option label")
    value: str = Field(..., description="Semantic value")
    recommended: bool = Field(default=False, description="Recommended option flag")


class ClarifyingQuestion(BaseModel):
    """Clarifying question generated during planning."""

    id: str = Field(..., description="Question id")
    text: str = Field(..., description="Question text")
    source: Optional[str] = Field(
        default=None, description="Source trace, for example: unknowns:heat_transfer_coefficient"
    )
    type: Literal["single", "multi"] = Field(default="single", description="Question type")
    options: List[ClarifyingOption] = Field(default_factory=list, description="Question options")

    @model_validator(mode="after")
    def ensure_supplement_option(self) -> "ClarifyingQuestion":
        supplement_id = "opt_supplement"
        has_supplement = any((opt.id or "").strip() == supplement_id for opt in self.options)
        if not has_supplement:
            self.options.append(
                ClarifyingOption(
                    id=supplement_id,
                    label="其他（请补充）",
                    value="supplement",
                )
            )
        return self


class ClarifyingAnswer(BaseModel):
    """Answer submitted by user for clarifying questions."""

    question_id: str = Field(..., description="Question id")
    selected_option_ids: List[str] = Field(default_factory=list, description="Selected options")
    supplement_text: Optional[str] = Field(default=None, description="Supplement text")


class DiscussionCard(BaseModel):
    """Structured output of the discussion stage."""

    card_id: str = Field(default_factory=lambda: f"discussion-{uuid4().hex[:12]}")
    physical_principles: List[str] = Field(default_factory=list)
    target_metrics: List[str] = Field(default_factory=list)
    known_inputs: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    candidate_solutions: List[str] = Field(default_factory=list)
    finalized: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def touch(self) -> None:
        self.updated_at = datetime.now()


class ModelOperationCase(BaseModel):
    """Structured case extracted from a .mph model."""

    case_id: str
    source_model_path: str
    summary: str
    physical_principles: List[str] = Field(default_factory=list)
    expected_behaviors: List[str] = Field(default_factory=list)
    global_definitions: List[GlobalDefinitionPlan] = Field(default_factory=list)
    workflow_steps: List[Dict[str, Any]] = Field(default_factory=list)
    physics_setup: List[Dict[str, Any]] = Field(default_factory=list)
    study_setup: List[Dict[str, Any]] = Field(default_factory=list)
    postprocess_setup: List[Dict[str, Any]] = Field(default_factory=list)
    reusable_user_prompt: str = ""
    extracted_at: datetime = Field(default_factory=datetime.now)


class TaskPlan(BaseModel):
    """Planner output before converting to ReAct plan."""

    geometry: Optional[GeometryPlan] = Field(default=None, description="Geometry plan")
    material: Optional[MaterialPlan] = Field(default=None, description="Material plan")
    physics: Optional[PhysicsPlan] = Field(default=None, description="Physics plan")
    mesh: Optional[MeshPlan] = Field(default=None, description="Mesh plan")
    study: Optional[StudyPlan] = Field(default=None, description="Study plan")
    global_definitions: List[GlobalDefinitionPlan] = Field(default_factory=list)

    def has_geometry(self) -> bool:
        return self.geometry is not None

    def has_material(self) -> bool:
        return self.material is not None

    def has_physics(self) -> bool:
        return self.physics is not None

    def has_mesh(self) -> bool:
        return self.mesh is not None

    def has_study(self) -> bool:
        return self.study is not None


class ReActTaskPlan(BaseModel):
    """Full ReAct task plan."""

    task_id: str = Field(..., description="Task id")
    model_name: str = Field(..., description="Model name")
    user_input: str = Field(..., description="User input")
    dimension: int = Field(default=2, description="Model dimension")

    execution_path: List[ExecutionStep] = Field(default_factory=list, description="Execution path")
    current_step_index: int = Field(default=0, description="Current step index")
    reasoning_path: List[ReasoningCheckpoint] = Field(
        default_factory=list, description="Reasoning path"
    )
    observations: List[Observation] = Field(default_factory=list, description="Observations")
    iterations: List[IterationRecord] = Field(default_factory=list, description="Iteration history")

    status: Literal["planning", "executing", "observing", "iterating", "completed", "failed"] = (
        Field(default="planning", description="Task status")
    )

    model_path: Optional[str] = Field(default=None, description="Current model path")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    error: Optional[str] = Field(default=None, description="Error message")
    integration_suggestions: Optional[str] = Field(
        default=None, description="Suggested COMSOL API integrations"
    )
    plan_description: Optional[str] = Field(default=None, description="Readable plan description")
    stop_after_step: Optional[str] = Field(default=None, description="Stop-after action")

    clarifying_questions: Optional[List[ClarifyingQuestion]] = Field(
        default=None, description="Planning clarifying questions"
    )
    clarifying_answers: Optional[List[ClarifyingAnswer]] = Field(
        default=None, description="Planning clarifying answers"
    )
    case_library_suggestions: Optional[List[Dict[str, str]]] = Field(
        default=None, description="Suggested official case links"
    )

    discussion_card_ref: Optional[str] = Field(default=None, description="Discussion card id")
    global_definitions: List[GlobalDefinitionPlan] = Field(
        default_factory=list, description="Global definitions to apply"
    )
    plan_confirmed: bool = Field(default=False, description="Whether plan is confirmed")

    # Dynamic sub-plans injected by action executor/reasoning.
    geometry_plan: Optional[Any] = None
    material_plan: Optional[Any] = None
    physics_plan: Optional[Any] = None
    mesh_plan: Optional[Any] = None
    study_plan: Optional[Any] = None

    def get_current_step(self) -> Optional[ExecutionStep]:
        if 0 <= self.current_step_index < len(self.execution_path):
            return self.execution_path[self.current_step_index]
        return None

    def add_observation(self, observation: Observation) -> None:
        self.observations.append(observation)

    def add_iteration(self, iteration: IterationRecord) -> None:
        self.iterations.append(iteration)

    def is_complete(self) -> bool:
        return self.status == "completed"

    def has_failed(self) -> bool:
        return self.status == "failed"

