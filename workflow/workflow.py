"""
Workflow Object representation and status definitions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from workflow.step import WorkflowStep


class WorkflowStatus(str, Enum):
    """
    Lifecycle status of a Workflow.
    """
    PLANNING = "PLANNING"
    PLANNING_COMPLETE = "PLANNING_COMPLETE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Workflow:
    """
    Durable, immutable execution plan representing a directed acyclic graph (DAG) of steps.
    """
    parent_task_id: str
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: WorkflowStatus = WorkflowStatus.PLANNING
    root_step_id: str | None = None
    steps: dict[str, WorkflowStep] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize workflow to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "parent_task_id": self.parent_task_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "root_step_id": self.root_step_id,
            "steps": {step_id: step.to_dict() for step_id, step in self.steps.items()},
            "metadata": self.metadata,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workflow:
        """Deserialize workflow from dictionary."""
        return cls(
            workflow_id=data["workflow_id"],
            parent_task_id=data["parent_task_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=WorkflowStatus(data["status"]),
            root_step_id=data.get("root_step_id"),
            steps={step_id: WorkflowStep.from_dict(step_data) for step_id, step_data in data.get("steps", {}).items()},
            metadata=data.get("metadata", {}),
            version=data.get("version", 1),
        )
