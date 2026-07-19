"""
Scheduler API — public control and monitoring API for the Scheduler subsystem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scheduler.scheduler import Scheduler
    from workflow.step import WorkflowStep


class SchedulerAPI:
    """
    Public lookup interface to manage scheduler execution, cancel steps,
    and monitor active queue stats and dashboard metrics.
    """

    def __init__(self, scheduler: Scheduler) -> None:
        """
        Initialize the Scheduler API.

        Args:
            scheduler: The Scheduler instance.
        """
        self._scheduler = scheduler

    def start(self) -> None:
        """Start the Scheduler."""
        self._scheduler.start()

    def stop(self) -> None:
        """Stop the Scheduler."""
        self._scheduler.stop()

    def schedule(self, step: WorkflowStep) -> None:
        """Schedule a workflow step for execution."""
        self._scheduler.schedule(step)

    def cancel(self, step_id: str) -> bool:
        """Cancel a step in the scheduling queue."""
        return self._scheduler.cancel(step_id)

    def retry(self, step: WorkflowStep) -> None:
        """Reset retry parameters and schedule step execution immediately."""
        self._scheduler.retry(step)

    def queue_status(self) -> dict[str, Any]:
        """Retrieve queue stats breakdown."""
        return self._scheduler.queue_status()

    def active_jobs(self) -> list[str]:
        """Retrieve list of currently executing step IDs."""
        return self._scheduler.active_jobs()

    def metrics(self) -> dict[str, Any]:
        """Retrieve aggregated scheduler metrics."""
        return self._scheduler.metrics()
