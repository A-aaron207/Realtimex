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

        # Signalled whenever any worker returns to IDLE so the scheduler
        # can wake up instead of busy-polling (fixes audit CRITICAL #2).
        self._worker_available = threading.Event()
        self._worker_available.set()  # Initially workers are available (pools not yet saturated)

        # Initialize defaults
        self._initialize_pools_and_workers()

        # Listen for dynamically loaded modules to expand pools automatically
        try:
            self._event_bus.subscribe("ModuleLoaded", self._on_module_loaded)
        except Exception as e:
            self._logger.warning("Could not subscribe WorkerManager to ModuleLoaded: %s", e)

    def _module_resolver(self, module_id: str) -> LoadedModule | None:
        """Resolve module ID to instance."""
        loaded_modules = self._loaded_modules_provider()
        for lm in loaded_modules:
            if lm.manifest.module_id == module_id:
                return lm
        return None

    def _on_module_loaded(self, event: Event) -> None:
        """
        Event handler for KernelEventType.MODULE_LOADED ("ModuleLoaded").
        Automatically registers worker pools for all capabilities declared by newly loaded modules.
        """
        capabilities = event.payload.get("capabilities", [])
        if isinstance(capabilities, list):
            for cap in capabilities:
                if isinstance(cap, str) and cap:
                    self.register_capability(cap)

    def register_capability(self, capability: str, initial_workers: int = 1) -> WorkerPool:
        """
        Register a worker pool for a capability and spin up initial workers.

        If a pool already exists for the capability, returns the existing pool.
        This provides dynamic capability expansion when new modules are loaded.
        """
        with self._lock:
            if capability in self._pools:
                return self._pools[capability]

            pool = WorkerPool(capability)
            self._pools[capability] = pool

            for i in range(1, max(1, initial_workers) + 1):
                worker_id = f"{capability}_worker_{i:02d}"
                worker = WorkerRuntime(
                    worker_id=worker_id,
                    worker_type="agent_worker",
                    supported_capability=capability,
                    event_bus=self._event_bus,
                    module_resolver=self._module_resolver,
                    metadata={"pool": capability},
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
                        payload={"worker_id": worker_id, "capability": capability},
                    )
                )

            self._worker_available.set()
            self._logger.info("Registered worker pool for capability '%s' with %d worker(s)", capability, initial_workers)
            return pool

    def has_idle_worker(self, capability: str) -> bool:
        """
        Check whether at least one idle worker is available for the given capability.
        Encapsulates WorkerPool state so external components don't inspect pools directly.
        """
        with self._lock:
            pool = self._pools.get(capability)
            return pool.has_idle_worker() if pool else False

    def _initialize_pools_and_workers(self) -> None:
        """Create worker pools and pre-populate with workers."""
        capabilities = [
            "plan_task",
            "web_search",
            "generate_image",
            "write_file",
            "read_file",
            "summarize_text",
            "generate_text",
            "generate_code",
            "permission_check",
        ]

        for cap in capabilities:
            self.register_capability(cap)

        # Also initialize pools for any modules already loaded
        try:
            for lm in self._loaded_modules_provider():
                if hasattr(lm, "manifest") and lm.manifest and hasattr(lm.manifest, "capabilities"):
                    for cap in lm.manifest.capabilities:
                        if isinstance(cap, str) and cap:
                            self.register_capability(cap)
        except Exception:
            pass

    def get_pool(self, capability: str) -> WorkerPool | None:
        """
        Retrieve the WorkerPool for a given capability, dynamically registering it
        and spawning a worker if it doesn't exist yet.
        """
        with self._lock:
            if capability not in self._pools:
                try:
                    return self.register_capability(capability)
                except Exception as e:
                    self._logger.exception("Failed to dynamically register pool/worker for capability '%s': %s", capability, e)
                    return None
            return self._pools.get(capability)

    def list_workers(self) -> list[BaseWorker]:
        """Return a flat list of all workers across all capability pools."""
        workers: list[BaseWorker] = []
        with self._lock:
            for pool in self._pools.values():
                workers.extend(pool.list_workers())
        return workers

    def wait_for_idle_worker(self, timeout: float = 1.0) -> bool:
        """
        Block until at least one idle worker becomes available across any pool,
        or until *timeout* seconds elapse.

        This replaces the scheduler's busy-poll / sleep(0.05) pattern.
        The event is set by execute() whenever a worker is returned to IDLE.

        Args:
            timeout: Maximum seconds to wait. Defaults to 1.0.

        Returns:
            True if a worker became available within the timeout, False otherwise.
        """
        return self._worker_available.wait(timeout=timeout)

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
            pool = self.get_pool(cap)
            if not pool:
                raise WorkerPoolError(f"No worker pool registered for capability '{cap}'.")

            # Try to acquire an idle worker
            worker = pool.acquire_idle_worker()
            if not worker:
                raise WorkerPoolError(f"No idle workers available in pool for capability '{cap}'.")

            # If no idle workers remain across ALL pools, clear the event so
            # the scheduler knows to wait before re-checking.
            if not any(p.has_idle_worker() for p in self._pools.values()):
                self._worker_available.clear()

        try:
            # Let the worker execute the context
            report = worker.execute(context)
            return report
        finally:
            # Release worker back to the pool, then signal availability
            pool.return_worker(worker.worker_id)
            self._worker_available.set()


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
