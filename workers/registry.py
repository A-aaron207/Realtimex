"""
Registry for registering, tracking, and looking up active workers.
"""

from __future__ import annotations

import threading

from workers.lifecycle import WorkerState

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workers.base import BaseWorker


class WorkerRegistry:
    """
    Thread-safe registry mapping worker IDs to instantiated BaseWorker records.
    """

    def __init__(self) -> None:
        self._workers: dict[str, BaseWorker] = {}
        self._lock = threading.RLock()

    def register(self, worker: BaseWorker) -> None:
        """Register a worker in the system."""
        with self._lock:
            self._workers[worker.worker_id] = worker

    def unregister(self, worker_id: str) -> bool:
        """Unregister a worker by ID."""
        with self._lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                return True
            return False

    def get(self, worker_id: str) -> BaseWorker | None:
        """Retrieve a worker by ID."""
        with self._lock:
            return self._workers.get(worker_id)

    def list_all(self) -> list[BaseWorker]:
        """Return list of all registered workers."""
        with self._lock:
            return list(self._workers.values())

    def list_idle(self) -> list[BaseWorker]:
        """Return list of all IDLE workers."""
        with self._lock:
            return [w for w in self._workers.values() if w.state == WorkerState.IDLE]

    def list_by_capability(self, capability: str) -> list[BaseWorker]:
        """Return list of workers supporting a specific capability."""
        with self._lock:
            return [w for w in self._workers.values() if w.supported_capability == capability]
