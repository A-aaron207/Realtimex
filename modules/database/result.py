"""
Structured result object returned by every Database Module capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionResult:
    """
    Unified result envelope for all database operations.

    Attributes:
        status:         "SUCCESS" or "FAILED"
        rows:           Result rows as a list of dicts (SELECT / RETURNING).
        row_count:      Affected/returned row count.
        last_insert_id: Row ID of the last INSERT (if applicable).
        error:          Human-readable error message on failure.
        metadata:       Extra contextual data (query, backend, latency, etc.).
    """

    status: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    last_insert_id: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for capability return values."""
        return {
            "status": self.status,
            "rows": self.rows,
            "row_count": self.row_count,
            "last_insert_id": self.last_insert_id,
            "error": self.error,
            "metadata": self.metadata,
        }

    @staticmethod
    def success(
        rows: list[dict[str, Any]] | None = None,
        row_count: int = 0,
        last_insert_id: int | None = None,
        **metadata: Any,
    ) -> "ExecutionResult":
        return ExecutionResult(
            status="SUCCESS",
            rows=rows or [],
            row_count=row_count,
            last_insert_id=last_insert_id,
            metadata=metadata,
        )

    @staticmethod
    def failure(error: str, **metadata: Any) -> "ExecutionResult":
        return ExecutionResult(status="FAILED", error=error, metadata=metadata)
