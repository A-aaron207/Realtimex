"""
Immutable execution context supplied to workers on execution start.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionContext:
    """
    Immutable block of metadata and data payload required for a worker to execute a step.
    """
    task_id: str
    workflow_id: str
    step_id: str
    capability: str
    input: dict[str, Any] = field(default_factory=dict)
    memory_reference: str = ""
    configuration: dict[str, Any] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    user_role: str = "admin"
    user_id: str = ""
    auth_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize context to dictionary."""
        return {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "capability": self.capability,
            "input": self.input,
            "memory_reference": self.memory_reference,
            "configuration": self.configuration,
            "permissions": self.permissions,
            "metadata": self.metadata,
            "user_role": self.user_role,
            "user_id": self.user_id,
            "auth_context": self.auth_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionContext:
        """Deserialize context from dictionary."""
        return cls(
            task_id=data["task_id"],
            workflow_id=data["workflow_id"],
            step_id=data["step_id"],
            capability=data["capability"],
            input=data.get("input", {}),
            memory_reference=data.get("memory_reference", ""),
            configuration=data.get("configuration", {}),
            permissions=data.get("permissions", {}),
            metadata=data.get("metadata", {}),
            user_role=data.get("user_role", "admin"),
            user_id=data.get("user_id", ""),
            auth_context=data.get("auth_context", {}),
        )
