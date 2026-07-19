"""
Recovery Manager placeholder for Milestone 1.

The Recovery Manager will eventually be responsible for detecting
failures in workers, services, and workflows, and orchestrating
recovery strategies (retries, restarts, failover). For Milestone 1 it
only tracks whether recovery is enabled and provides a hook for
recording incidents, with no recovery strategies implemented yet.
"""

from __future__ import annotations

from typing import Any


class RecoveryManager:
    """
    Placeholder for future failure-detection and recovery orchestration.

    Responsibilities (Milestone 1):
        - Track whether recovery handling is enabled.
        - Record incidents in memory for later inspection.

    Future milestones will add retry policies, health checks, and
    failover strategies on top of this foundation.
    """

    def __init__(self, enabled: bool = True) -> None:
        """
        Initialize the Recovery Manager.

        Args:
            enabled: Whether recovery handling is active for this Kernel instance.
        """
        self._enabled = enabled
        self._incidents: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        """Whether recovery handling is currently enabled."""
        return self._enabled

    def record_incident(self, description: str, details: dict[str, Any] | None = None) -> None:
        """
        Record an incident for future recovery analysis.

        Args:
            description: A short human-readable description of the incident.
            details: Optional structured details about the incident.
        """
        self._incidents.append({"description": description, "details": details or {}})

    def incidents(self) -> list[dict[str, Any]]:
        """Return a copy of all incidents recorded since startup."""
        return list(self._incidents)
