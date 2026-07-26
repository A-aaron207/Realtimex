"""
Observer component for Executor 2.0.

Captures and inspects step execution outcomes, runtime outputs, side effects,
and exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ExecutionObservation:
    """
    Observation record capturing the raw runtime result and side effects of an action.
    """
    step_id: str
    capability: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    exit_code: int | None = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status.upper() in ("SUCCESS", "OK", "COMPLETED") and self.error is None


class ExecutionObserver:
    """
    Observes and parses execution results from workers and modules.
    """

    def observe(
        self,
        step_id: str,
        capability: str,
        raw_result: dict[str, Any] | None,
        exception: Exception | None = None,
        duration_ms: float = 0.0,
    ) -> ExecutionObservation:
        """
        Build an ExecutionObservation from a step execution result or exception.
        """
        if exception:
            return ExecutionObservation(
                step_id=step_id,
                capability=capability,
                status="FAILED",
                error=str(exception),
                execution_time_ms=duration_ms,
                metadata={"exception_class": type(exception).__name__},
            )

        if not raw_result or not isinstance(raw_result, dict):
            return ExecutionObservation(
                step_id=step_id,
                capability=capability,
                status="FAILED",
                error="Empty or non-dictionary execution result returned.",
                execution_time_ms=duration_ms,
            )

        status = raw_result.get("status", "SUCCESS")
        error_msg = raw_result.get("error") or raw_result.get("stderr")
        if status.upper() in ("FAILED", "ERROR") and not error_msg:
            error_msg = f"Step failed with status '{status}'."

        exit_code = raw_result.get("exit_code")

        return ExecutionObservation(
            step_id=step_id,
            capability=capability,
            status=status,
            output=raw_result,
            error=error_msg if (status.upper() in ("FAILED", "ERROR") or exit_code not in (None, 0)) else None,
            exit_code=exit_code,
            execution_time_ms=duration_ms,
            metadata=raw_result.get("metadata", {}),
        )
