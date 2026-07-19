"""
Task data model and priority definitions for the Realtimex Task System.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from tasks.states import TaskState


class TaskPriority(IntEnum):
    """
    Priority levels for task execution.
    """
    LOW = 0
    NORMAL = 10
    HIGH = 20
    CRITICAL = 30


@dataclass(frozen=True)
class TaskHistoryEntry:
    """
    An entry in the task's execution history.
    """
    timestamp: datetime
    event_type: str  # e.g., "state_transition", "progress_update", "custom_event"
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskHistoryEntry:
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data["event_type"],
            description=data["description"],
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class Task:
    """
    Durable, immutable representation of a single unit of work in Realtimex.

    A Task serves as the single source of truth for execution goals, state,
    and associated artifacts. Because the Task object is frozen (immutable),
    updates are performed by creating a copy with modified fields.
    """
    goal: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = TaskState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: TaskPriority = TaskPriority.NORMAL
    progress: int = 0
    workflow: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[TaskHistoryEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Validate progress range
        if not (0 <= self.progress <= 100):
            raise ValueError(f"Task progress must be between 0 and 100. Got: {self.progress}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the task to a dictionary."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "priority": self.priority.value,
            "progress": self.progress,
            "workflow": self.workflow,
            "memory": self.memory,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "history": [entry.to_dict() for entry in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Deserialize a task from a dictionary."""
        return cls(
            task_id=data["task_id"],
            goal=data["goal"],
            state=TaskState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            priority=TaskPriority(data["priority"]),
            progress=data["progress"],
            workflow=data.get("workflow", {}),
            memory=data.get("memory", {}),
            artifacts=data.get("artifacts", []),
            metadata=data.get("metadata", {}),
            history=[TaskHistoryEntry.from_dict(h) for h in data.get("history", [])],
        )
