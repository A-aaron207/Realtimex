"""
Worker API — public control and lookup API for the Worker Runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workers.context import ExecutionContext
    from workers.manager import WorkerManager
    from workers.report import WorkerReport


class WorkerAPI:
    """
    Public lookup interface to execute steps, retrieve health, send heartbeats,
    and monitor/restart workers.
    """

    def __init__(self, manager: WorkerManager) -> None:
        """
        Initialize the Worker API.

        Args:
            manager: The WorkerManager instance.
        """
        self._manager = manager

    def execute(self, context: ExecutionContext) -> WorkerReport:
        """
        Execute an execution context step using an idle worker from the appropriate pool.
        """
        return self._manager.execute(context)

    def health(self) -> dict[str, Any]:
        """
        Get aggregated worker runtime health diagnostics and pool metrics.
        """
        return self._manager.health()

    def heartbeat(self, worker_id: str) -> None:
        """
        Send a heartbeat signal for a worker to log activity.
        """
        self._manager.heartbeat(worker_id)

    def terminate(self, worker_id: str) -> None:
        """
        Terminate a worker.
        """
        self._manager.terminate(worker_id)

    def restart(self, worker_id: str) -> None:
        """
        Restart or recover a worker.
        """
        self._manager.restart(worker_id)

    def status(self, worker_id: str) -> dict[str, Any]:
        """
        Retrieve state and configuration status details of a specific worker.
        """
        return self._manager.status(worker_id)

    def register_capability(self, capability: str, initial_workers: int = 1) -> Any:
        """
        Register a new worker pool for a capability.
        """
        return self._manager.register_capability(capability, initial_workers)

    def has_idle_worker(self, capability: str) -> bool:
        """
        Check whether an idle worker is available for a capability.
        """
        return self._manager.has_idle_worker(capability)

    def list_workers(self) -> list[Any]:
        """
        Return a list of all workers across all pools.
        """
        return self._manager.list_workers()

