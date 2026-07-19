"""
Worker Report returned upon completion of step execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkerReportStatus(str, Enum):
    """Execution status result."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class WorkerReport:
    """
    Structured results, warnings, metric data, and generated artifacts returned by a Worker.
    """
    status: WorkerReportStatus
    worker_id: str
    task_id: str
    step_id: str
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "status": self.status.value,
            "worker_id": self.worker_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "output": self.output,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerReport:
        """Deserialize report from dictionary."""
        return cls(
            status=WorkerReportStatus(data["status"]),
            worker_id=data["worker_id"],
            task_id=data["task_id"],
            step_id=data["step_id"],
            output=data.get("output", {}),
            artifacts=data.get("artifacts", []),
            warnings=data.get("warnings", []),
            metrics=data.get("metrics", {}),
            error_message=data.get("error_message"),
        )
