"""
Base Worker definition and contract for all worker runtime types.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from workers.exceptions import InvalidWorkerLifecycleError
from workers.health import WorkerHealth
from workers.lifecycle import WorkerState, validate_worker_transition
from workers.context import ExecutionContext
from workers.report import WorkerReport


class BaseWorker(ABC):
    """
    Abstract Base Class that defines the worker attributes, thread-safe lifecycle
    operations, and health/heartbeat interfaces.
    """

    def __init__(
        self,
        worker_id: str,
        worker_type: str,
        supported_capability: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize the worker.

        Args:
            worker_id: Unique worker identifier.
            worker_type: e.g. "agent_worker", "standard_worker".
            supported_capability: Capability this worker can execute.
            metadata: Optional additional metadata.
        """
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.supported_capability = supported_capability
        self.metadata = metadata or {}
        
        now = datetime.now(timezone.utc)
        self.start_time = now
        self.last_activity = now
        self.current_task_id: str | None = None
        self.current_step_id: str | None = None
        
        self._state = WorkerState.OFFLINE
        self._health = WorkerHealth(last_heartbeat=now)
        self._lock = threading.RLock()
        self._logger = logging.getLogger(f"realtimex.worker.{worker_id}")

    @property
    def state(self) -> WorkerState:
        """Get the current worker lifecycle state."""
        with self._lock:
            return self._state

    def set_state(self, new_state: WorkerState) -> None:
        """
        Safely transition to a new state.

        Raises:
            InvalidWorkerLifecycleError: If transition is illegal.
        """
        with self._lock:
            validate_worker_transition(self._state, new_state)
            self._logger.debug("Worker State transition: %s -> %s", self._state.value, new_state.value)
            self._state = new_state
            self.last_activity = datetime.now(timezone.utc)
            
            # Keep health metrics aligned
            self._health.busy = (new_state in {WorkerState.ASSIGNED, WorkerState.RUNNING, WorkerState.REPORTING})
            self._health.failed = (new_state == WorkerState.FAILED)
            self._health.alive = (new_state != WorkerState.TERMINATED and new_state != WorkerState.OFFLINE)

    def heartbeat(self) -> None:
        """
        Record a heartbeat signal from the worker, updating timestamps.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            self._health.last_heartbeat = now
            self.last_activity = now
            self._logger.debug("Heartbeat received.")

    def terminate(self) -> None:
        """
        Transition worker to TERMINATED state.
        """
        with self._lock:
            self.set_state(WorkerState.TERMINATED)
            self._logger.info("Worker terminated.")

    def restart(self) -> None:
        """
        Recover/restart the worker from failure or termination.
        """
        with self._lock:
            self._health.restart_count += 1
            self._state = WorkerState.OFFLINE  # Reset lifecycle safely
            self.set_state(WorkerState.STARTING)
            self.set_state(WorkerState.IDLE)
            self._logger.info("Worker restarted. Restart count: %d", self._health.restart_count)

    def status(self) -> dict[str, Any]:
        """
        Expose status serialization.
        """
        with self._lock:
            return {
                "worker_id": self.worker_id,
                "worker_type": self.worker_type,
                "state": self.state.value,
                "supported_capability": self.supported_capability,
                "current_task_id": self.current_task_id,
                "current_step_id": self.current_step_id,
                "start_time": self.start_time.isoformat(),
                "last_activity": self.last_activity.isoformat(),
                "health": self._health.to_dict(),
                "metadata": self.metadata,
            }

    @abstractmethod
    def execute(self, context: ExecutionContext) -> WorkerReport:
        """
        Execute an execution step. Implementations should handle lifecycle state
        transitions, execution tasks, and report generations.
        """
        raise NotImplementedError
