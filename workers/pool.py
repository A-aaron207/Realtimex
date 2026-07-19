"""
Worker Pool grouping workers by their supported capabilities.
"""

from __future__ import annotations

import threading
from typing import Any, TYPE_CHECKING

from workers.exceptions import WorkerPoolError
from workers.lifecycle import WorkerState

if TYPE_CHECKING:
    from workers.base import BaseWorker


class WorkerPool:
    """
    Manages a group of workers supporting a single capability.
    Provides thread-safe allocation and status tracking.
    """

    def __init__(self, capability: str) -> None:
        """
        Initialize the pool.

        Args:
            capability: The capability name (e.g. "web_search").
        """
        self.capability = capability
        self._workers: dict[str, BaseWorker] = {}
        self._lock = threading.RLock()

    def add_worker(self, worker: BaseWorker) -> None:
        """Add a worker to this pool."""
        if worker.supported_capability != self.capability:
            raise WorkerPoolError(
                f"Worker '{worker.worker_id}' supports capability '{worker.supported_capability}', "
                f"but this pool manages capability '{self.capability}'."
            )
        with self._lock:
            self._workers[worker.worker_id] = worker

    def remove_worker(self, worker_id: str) -> bool:
        """Remove a worker from this pool."""
        with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                return True
            return False

    def acquire_idle_worker(self) -> BaseWorker | None:
        """
        Acquire an idle worker from the pool, transitioning its state to ASSIGNED.

        Returns:
            The acquired worker or None if no idle workers are available.
        """
        with self._lock:
            for worker in self._workers.values():
                if worker.state == WorkerState.IDLE:
                    # Allocate worker
                    worker.set_state(WorkerState.ASSIGNED)
                    return worker
            return None

    def return_worker(self, worker_id: str) -> None:
        """
        Return an assigned/running worker back to the IDLE state.
        """
        with self._lock:
            worker = self._workers.get(worker_id)
            if worker is None:
                raise WorkerPoolError(f"Worker '{worker_id}' not found in pool.")
            if worker.state in {WorkerState.TERMINATED, WorkerState.OFFLINE}:
                return  # Don't make terminated/offline workers idle
            worker.set_state(WorkerState.IDLE)
            worker.current_task_id = None
            worker.current_step_id = None

    def statistics(self) -> dict[str, Any]:
        """
        Gather metrics on worker states in this pool.
        """
        with self._lock:
            total = len(self._workers)
            states = {state: 0 for state in WorkerState}
            for w in self._workers.values():
                states[w.state] += 1

            return {
                "capability": self.capability,
                "total_workers": total,
                "idle_workers": states[WorkerState.IDLE],
                "assigned_workers": states[WorkerState.ASSIGNED],
                "running_workers": states[WorkerState.RUNNING],
                "failed_workers": states[WorkerState.FAILED],
                "terminated_workers": states[WorkerState.TERMINATED],
            }
