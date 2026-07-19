"""
Health Monitor for Realtimex.

Handles monitoring component statuses, performing checks, and alerting.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from observability.health.checks import HealthCheck, HealthStatus
from observability.health.reports import HealthReport
from observability.exceptions import HealthError


class HealthMonitor:
    """
    Central health manager for Realtimex.
    
    Registers checks for modules, memory, schedulers, and workers,
    aggregates results, and emits notifications upon state transitions.
    """

    def __init__(
        self,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Health Monitor.
        
        Args:
            event_bus: Optional Event Bus for emitting HealthChanged events
            logger: Optional logger instance
        """
        self.bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.observability.health")
        self._checks: dict[str, list[HealthCheck]] = {}  # component -> list of checks
        self._statuses: dict[str, str] = {}  # component -> status
        self._lock = threading.RLock()

    def register_check(self, component: str, check: HealthCheck) -> None:
        """Register a health check for a component."""
        with self._lock:
            if component not in self._checks:
                self._checks[component] = []
                self._statuses[component] = HealthStatus.HEALTHY
            self._checks[component].append(check)
            self.logger.debug("Health check '%s' registered for component: %s", check.name, component)

    def unregister_check(self, component: str) -> None:
        """Deregister health checks for a component."""
        with self._lock:
            self._checks.pop(component, None)
            self._statuses.pop(component, None)
            self.logger.debug("Component health checks unregistered: %s", component)

    def get_status(self, component: str) -> str:
        """Get status of a component."""
        with self._lock:
            return self._statuses.get(component, HealthStatus.HEALTHY)

    def check_health(self) -> HealthReport:
        """
        Run all registered checks and aggregate the results.
        
        Returns:
            HealthReport object
        """
        with self._lock:
            components_detail = {}
            overall_status = HealthStatus.HEALTHY
            
            for component, checks in self._checks.items():
                comp_status = HealthStatus.HEALTHY
                comp_messages = []
                comp_details = {}
                
                for check in checks:
                    try:
                        status, message, details = check.execute()
                    except Exception as e:
                        status, message, details = HealthStatus.FAILED, f"Check execution raised error: {e}", None
                        
                    comp_messages.append(message)
                    if details:
                        comp_details[check.name] = details
                        
                    # Precedence: FAILED > DEGRADED > HEALTHY
                    if status == HealthStatus.FAILED:
                        comp_status = HealthStatus.FAILED
                    elif status == HealthStatus.DEGRADED and comp_status != HealthStatus.FAILED:
                        comp_status = HealthStatus.DEGRADED
                        
                # Update overall status
                if comp_status == HealthStatus.FAILED:
                    overall_status = HealthStatus.FAILED
                elif comp_status == HealthStatus.DEGRADED and overall_status != HealthStatus.FAILED:
                    overall_status = HealthStatus.DEGRADED
                    
                old_status = self._statuses.get(component, HealthStatus.HEALTHY)
                if old_status != comp_status:
                    self._statuses[component] = comp_status
                    self._emit_health_changed(component, old_status, comp_status)
                    
                components_detail[component] = {
                    "status": comp_status,
                    "messages": comp_messages,
                    "details": comp_details,
                }
                
            return HealthReport(overall_status, components_detail)

    def _emit_health_changed(self, component: str, old_status: str, new_status: str) -> None:
        """Emit HealthChanged event when component status transitions."""
        msg = f"Component {component} health state transitioned from {old_status} to {new_status}"
        self.logger.warning(msg)
        
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name="HealthChanged",
                        source="observability.health",
                        payload={
                            "component": component,
                            "old_status": old_status,
                            "new_status": new_status,
                        },
                        priority=EventPriority.HIGH if new_status == HealthStatus.FAILED else EventPriority.NORMAL,
                    )
                )
            except Exception as e:
                self.logger.error("Failed to emit HealthChanged event: %s", e)
