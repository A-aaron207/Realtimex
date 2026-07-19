"""
Permission Request models for the Realtimex Permission System.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PermissionRequest:
    """
    Representation of an action request requiring permission evaluation.
    """
    task_id: str
    worker_id: str
    action: str
    target: str
    requested_capability: str
    risk_level: str = "low"  # low, medium, high, critical
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "worker_id": self.worker_id,
            "action": self.action,
            "target": self.target,
            "requested_capability": self.requested_capability,
            "risk_level": self.risk_level,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionRequest:
        ts = data.get("timestamp")
        timestamp = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.now(timezone.utc)
        
        return cls(
            request_id=data["request_id"],
            task_id=data["task_id"],
            workflow_id=data.get("workflow_id"),
            worker_id=data["worker_id"],
            action=data["action"],
            target=data["target"],
            requested_capability=data["requested_capability"],
            risk_level=data.get("risk_level", "low"),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )
