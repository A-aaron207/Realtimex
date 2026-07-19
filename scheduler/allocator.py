"""
Resource Allocator matching steps to pools and acquiring idle workers.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from events.event import Event
from scheduler.exceptions import AllocationError

if TYPE_CHECKING:
    from capabilities.registry import CapabilityRegistry
    from workers.manager import WorkerManager
    from workers.base import BaseWorker


class ResourceAllocator:
    """
    Coordinates capability lookups in registries and worker acquisitions from manager pools.
    """

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        worker_manager: WorkerManager,
        event_bus: Any,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize Resource Allocator.

        Args:
            capability_registry: CapabilityRegistry instance.
            worker_manager: WorkerManager instance.
            event_bus: Global EventBus.
            logger: Diagnostics logger.
        """
        self._capability_registry = capability_registry
        self._worker_manager = worker_manager
        self._event_bus = event_bus
        self._logger = logger
        self._lock = threading.RLock()

    def allocate_worker(self, capability: str) -> tuple[BaseWorker, str] | None:
        """
        Identify a provider for a capability, locate the worker pool, and acquire an idle worker.

        Args:
            capability: The capability required.

        Returns:
            Tuple of (BaseWorker, provider_id) if successful, None if unavailable.
        """
        with self._lock:
            try:
                # 1. Query Capability Registry
                descriptor = self._capability_registry.find(capability)
                provider_id = descriptor.provider_id
            except Exception as e:
                self._logger.warning("No capability provider registered for '%s': %s", capability, e)
                return None

            # 2. Query Worker Pool
            pool = self._worker_manager._pools.get(capability)
            if not pool:
                self._logger.warning("No worker pool exists for capability '%s'", capability)
                return None

            # 3. Acquire Idle Worker
            worker = pool.acquire_idle_worker()
            if not worker:
                return None

            self._logger.info("Allocated worker %s for capability %s", worker.worker_id, capability)

            # Emit WorkerAllocated
            self._event_bus.publish(
                Event(
                    name="WorkerAllocated",
                    source="scheduler.allocator",
                    payload={"worker_id": worker.worker_id, "capability": capability},
                )
            )

            return worker, provider_id

    def release_worker(self, capability: str, worker_id: str) -> None:
        """
        Release worker back to pool.
        """
        with self._lock:
            pool = self._worker_manager._pools.get(capability)
            if pool:
                pool.return_worker(worker_id)
                self._logger.info("Released worker %s", worker_id)

                # Emit WorkerReleased
                self._event_bus.publish(
                    Event(
                        name="WorkerReleased",
                        source="scheduler.allocator",
                        payload={"worker_id": worker_id, "capability": capability},
                    )
                )
