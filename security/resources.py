"""
Resource Monitor for Realtimex.

Tracks task execution durations, CPU, and memory limits, and raises errors on violations.
"""

from __future__ import annotations

import time
from typing import Any

from security.policies import SecurityContext
from security.exceptions import ResourceLimitExceededError


class ResourceMonitor:
    """Enforces limits on CPU, memory, and duration of active execution contexts."""

    def __init__(self) -> None:
        self._task_start_times: dict[str, float] = {}

    def register_task(self, task_id: str) -> None:
        """Register starting timestamp for execution duration tracking."""
        self._task_start_times[task_id] = time.time()

    def deregister_task(self, task_id: str) -> None:
        """Clear task duration timestamp tracker."""
        self._task_start_times.pop(task_id, None)

    def check_task_limits(
        self,
        task_id: str,
        current_memory_mb: float,
        current_cpu_percent: float,
        context: SecurityContext,
    ) -> None:
        """
        Check if active usage exceeds defined limits in context.
        
        Args:
            task_id: Active task identifier
            current_memory_mb: Estimated memory usage in MB
            current_cpu_percent: CPU usage percentage
            context: SecurityContext with resource_limits
            
        Raises:
            ResourceLimitExceededError: If resource constraints are violated
        """
        limits = context.resource_limits
        if not limits:
            return

        # 1. Enforce duration limit
        max_duration = limits.get("max_duration_sec", 0.0)
        if max_duration > 0.0 and task_id in self._task_start_times:
            elapsed = time.time() - self._task_start_times[task_id]
            if elapsed > max_duration:
                raise ResourceLimitExceededError(
                    f"Task {task_id} exceeded maximum duration: {elapsed:.1f}s > {max_duration:.1f}s"
                )

        # 2. Enforce memory usage limit
        max_memory = limits.get("max_memory_mb", 0.0)
        if max_memory > 0.0 and current_memory_mb > max_memory:
            raise ResourceLimitExceededError(
                f"Task {task_id} exceeded memory limit: {current_memory_mb:.1f}MB > {max_memory:.1f}MB"
            )

        # 3. Enforce CPU usage limit
        max_cpu = limits.get("max_cpu_percent", 0.0)
        if max_cpu > 0.0 and current_cpu_percent > max_cpu:
            raise ResourceLimitExceededError(
                f"Task {task_id} exceeded CPU limit: {current_cpu_percent:.1f}% > {max_cpu:.1f}%"
            )
