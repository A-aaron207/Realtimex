"""
Health Checks for Realtimex.

Defines health check classes and helpers for system components.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


class HealthStatus:
    """Standard health statuses for Realtimex components."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class HealthCheck:
    """Base class for component health checks."""

    def __init__(self, name: str) -> None:
        self.name = name

    def execute(self) -> tuple[str, str, Optional[dict[str, Any]]]:
        """
        Execute the health check.
        
        Returns:
            Tuple of (status, message, details)
        """
        raise NotImplementedError


class ResourceHealthCheck(HealthCheck):
    """Checks system resource health (e.g., Memory, Disk)."""

    def __init__(
        self,
        name: str,
        check_func: Callable[[], float],
        warn_threshold: float,
        fail_threshold: float,
    ) -> None:
        super().__init__(name)
        self.check_func = check_func
        self.warn_threshold = warn_threshold
        self.fail_threshold = fail_threshold

    def execute(self) -> tuple[str, str, Optional[dict[str, Any]]]:
        try:
            value = self.check_func()
            details = {"value": value, "warn_threshold": self.warn_threshold, "fail_threshold": self.fail_threshold}
            
            if value >= self.fail_threshold:
                return HealthStatus.FAILED, f"Resource {self.name} failed threshold: {value:.1f} >= {self.fail_threshold:.1f}", details
            elif value >= self.warn_threshold:
                return HealthStatus.DEGRADED, f"Resource {self.name} warning threshold: {value:.1f} >= {self.warn_threshold:.1f}", details
                
            return HealthStatus.HEALTHY, f"Resource {self.name} is healthy: {value:.1f}", details
        except Exception as e:
            return HealthStatus.FAILED, f"Health check failed with exception: {e}", None


class PingHealthCheck(HealthCheck):
    """Pings a component or provider using a check callable."""

    def __init__(self, name: str, ping_func: Callable[[], bool]) -> None:
        super().__init__(name)
        self.ping_func = ping_func

    def execute(self) -> tuple[str, str, Optional[dict[str, Any]]]:
        try:
            success = self.ping_func()
            if success:
                return HealthStatus.HEALTHY, f"Component {self.name} ping succeeded.", None
            return HealthStatus.FAILED, f"Component {self.name} ping returned False.", None
        except Exception as e:
            return HealthStatus.FAILED, f"Component {self.name} ping raised exception: {e}", None
