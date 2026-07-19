"""
Health Reports for Realtimex.

Structures and formatting health reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class HealthReport:
    """Represents a structured health report snapshot."""

    def __init__(self, status: str, components: dict[str, Any]) -> None:
        """
        Initialize HealthReport.
        
        Args:
            status: Overall system health status
            components: Component-wise health details dictionary
        """
        self.status = status
        self.components = components
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary format."""
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "components": self.components,
        }
