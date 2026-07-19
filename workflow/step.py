"""
Workflow Step definitions, states, and validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from workflow.exceptions import InvalidStepStateTransitionError


class StepState(str, Enum):
    """
    State lifecycle of a single workflow step.
    """
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


# Valid transitions: current -> set of allowed target states
VALID_STEP_TRANSITIONS: dict[StepState, set[StepState]] = {
    StepState.PENDING: {StepState.READY, StepState.WAITING, StepState.SKIPPED, StepState.CANCELLED, StepState.RUNNING},
    StepState.WAITING: {StepState.READY, StepState.SKIPPED, StepState.CANCELLED, StepState.RUNNING},
    StepState.READY: {StepState.RUNNING, StepState.SKIPPED, StepState.CANCELLED, StepState.COMPLETED},
    StepState.RUNNING: {StepState.COMPLETED, StepState.FAILED, StepState.CANCELLED, StepState.SKIPPED},
    StepState.COMPLETED: set(),
    StepState.FAILED: set(),
    StepState.SKIPPED: set(),
    StepState.CANCELLED: set(),
}


def validate_step_transition(current: StepState, target: StepState) -> None:
    """
    Validate transition between step states.

    Raises:
        InvalidStepStateTransitionError: If transition is illegal.
    """
    if current == target:
        return
    allowed = VALID_STEP_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStepStateTransitionError(
            f"Invalid step state transition from {current.value} to {target.value}."
        )


@dataclass(frozen=True)
class WorkflowStep:
    """
    Immutable representation of a single node in a workflow execution graph.
    """
    step_id: str
    workflow_id: str
    capability: str
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    status: StepState = StepState.PENDING
    dependencies: frozenset[str] = field(default_factory=frozenset)
    estimated_cost: float = 0.0
    estimated_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize step to dictionary."""
        return {
            "step_id": self.step_id,
            "workflow_id": self.workflow_id,
            "capability": self.capability,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status.value,
            "dependencies": list(self.dependencies),
            "estimated_cost": self.estimated_cost,
            "estimated_time": self.estimated_time,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowStep:
        """Deserialize step from dictionary."""
        return cls(
            step_id=data["step_id"],
            workflow_id=data["workflow_id"],
            capability=data["capability"],
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            status=StepState(data["status"]),
            dependencies=frozenset(data.get("dependencies", [])),
            estimated_cost=data.get("estimated_cost", 0.0),
            estimated_time=data.get("estimated_time", 0.0),
            metadata=data.get("metadata", {}),
        )
