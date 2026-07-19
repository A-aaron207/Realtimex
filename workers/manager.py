"""
Worker Manager — top-level coordinator of worker pools, allocations, heartbeats, and executions.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from events.event import Event
from workers.exceptions import WorkerNotFoundError, WorkerPoolError
from workers.lifecycle import WorkerState
from workers.pool import WorkerPool
from workers.registry import WorkerRegistry
from workers.runtime import WorkerRuntime

if TYPE_CHECKING:
    from events.bus import EventBus
    from loader.loader import LoadedModule
    from workers.context import ExecutionContext
    from workers.report import WorkerReport


class WorkerManager:
    """
    Manages pools of workers grouped by capability, tracks worker heartbeats,
    coordinates step execution assignments, and registers/terminates workers.
    """

    def __init__(
        self,
        event_bus: EventBus,
        loaded_modules_provider: Callable[[], list[LoadedModule]],
        logger: logging.Logger,
    ) -> None:
        """
        Initialize the Worker Manager.

        Args:
            event_bus: EventBus instance.
            loaded_modules_provider: Callback that returns the list of LoadedModule instances currently in the Kernel.
            logger: Centralized logger.
        """
        self._event_bus = event_bus
        self._loaded_modules_provider = loaded_modules_provider
        self._logger = logger
        self._registry = WorkerRegistry()
        self._pools: dict[str, WorkerPool] = {}
        self._lock = threading.RLock()

        # Initialize defaults
        self._initialize_pools_and_workers()

    def _module_resolver(self, module_id: str) -> LoadedModule | None:
        """Resolve module ID to instance."""
        loaded_modules = self._loaded_modules_provider()
        for lm in loaded_modules:
            if lm.manifest.module_id == module_id:
                return lm
        return None

    def _initialize_pools_and_workers(self) -> None:
        """Create worker pools and pre-populate with workers for demonstration."""
        capabilities = [
            "plan_task",
            "web_search",
            "generate_image",
            "write_file",
            "read_file",
            "summarize_text",
        ]

        for cap in capabilities:
            pool = WorkerPool(cap)
            self._pools[cap] = pool

            # Pre-register 1 worker per capability
            worker_id = f"{cap}_worker_01"
            worker = WorkerRuntime(
                worker_id=worker_id,
                worker_type="agent_worker",
                supported_capability=cap,
                event_bus=self._event_bus,
                module_resolver=self._module_resolver,
                metadata={"pool": cap},
            )

            # Move from OFFLINE to STARTING to IDLE
            worker.set_state(WorkerState.STARTING)
            worker.set_state(WorkerState.IDLE)

            self._registry.register(worker)
            pool.add_worker(worker)

            # Emit WorkerStarted
            self._event_bus.publish(
                Event(
                    name="WorkerStarted",
                    source="workers.manager",
                    payload={"worker_id": worker_id, "capability": cap},
                )
            )

    def execute(self, context: ExecutionContext) -> WorkerReport:
        """
        Acquire an idle worker supporting the requested capability and execute the step.

        Args:
            context: Execution context containing step details.

        Returns:
            The execution report.

        Raises:
            WorkerPoolError: If no worker matches capability or no idle workers are available.
        """
        cap = context.capability
        with self._lock:
            pool = self._pools.get(cap)
            if not pool:
                raise WorkerPoolError(f"No worker pool registered for capability '{cap}'.")

            # Try to acquire an idle worker
            worker = pool.acquire_idle_worker()
            if not worker:
                raise WorkerPoolError(f"No idle workers available in pool for capability '{cap}'.")

        try:
            # Let the worker execute the context
            report = worker.execute(context)
            return report
        finally:
            # Release worker back to the pool
            pool.return_worker(worker.worker_id)

    def heartbeat(self, worker_id: str) -> None:
        """Record heartbeat and emit event."""
        with self._lock:
            worker = self._registry.get(worker_id)
            if not worker:
                raise WorkerNotFoundError(f"Worker '{worker_id}' not found.")

            worker.heartbeat()

            # Emit HeartbeatReceived event
            self._event_bus.publish(
                Event(
                    name="HeartbeatReceived",
                    source="workers.manager",
                    payload={"worker_id": worker_id, "timestamp": datetime.now(timezone.utc).isoformat()},
                )
            )

    def terminate(self, worker_id: str) -> None:
        """Terminate worker lifecycle and emit event."""
        with self._lock:
            worker = self._registry.get(worker_id)
            if not worker:
                raise WorkerNotFoundError(f"Worker '{worker_id}' not found.")

            worker.terminate()

            # Emit WorkerTerminated event
            self._event_bus.publish(
                Event(
                    name="WorkerTerminated",
                    source="workers.manager",
                    payload={"worker_id": worker_id},
                )
            )

    def restart(self, worker_id: str) -> None:
        """Restart worker and emit event."""
        with self._lock:
            worker = self._registry.get(worker_id)
            if not worker:
                raise WorkerNotFoundError(f"Worker '{worker_id}' not found.")

            worker.restart()

            # Emit WorkerRecovered event
            self._event_bus.publish(
                Event(
                    name="WorkerRecovered",
                    source="workers.manager",
                    payload={"worker_id": worker_id},
                )
            )

    def status(self, worker_id: str) -> dict[str, Any]:
        """Fetch worker status metadata."""
        with self._lock:
            worker = self._registry.get(worker_id)
            if not worker:
                raise WorkerNotFoundError(f"Worker '{worker_id}' not found.")
            return worker.status()

    def health(self) -> dict[str, Any]:
        """
        Aggregate system-wide worker diagnostics.
        """
        with self._lock:
            workers = self._registry.list_all()
            total = len(workers)
            busy_count = 0
            failed_count = 0
            idle_count = 0
            terminated_count = 0

            for w in workers:
                if w.state == WorkerState.IDLE:
                    idle_count += 1
                elif w.state in {WorkerState.ASSIGNED, WorkerState.RUNNING, WorkerState.REPORTING}:
                    busy_count += 1
                elif w.state == WorkerState.FAILED:
                    failed_count += 1
                elif w.state == WorkerState.TERMINATED:
                    terminated_count += 1

            pool_stats = {cap: pool.statistics() for cap, pool in self._pools.items()}

            return {
                "total_workers": total,
                "idle_workers": idle_count,
                "busy_workers": busy_count,
                "failed_workers": failed_count,
                "terminated_workers": terminated_count,
                "pools": pool_stats,
            }
