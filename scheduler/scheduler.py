"""
Scheduler — central coordinator of execution timing, step queues, dependencies, and retries.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from events.event import Event
from scheduler.allocator import ResourceAllocator
from scheduler.dependency import DependencyResolver
from scheduler.dispatcher import Dispatcher
from scheduler.exceptions import SchedulerError
from scheduler.monitor import SchedulerMonitor
from scheduler.policies import PriorityPolicy
from scheduler.queue import DispatchQueue
from scheduler.retry import RetryManager

if TYPE_CHECKING:
    from capabilities.registry import CapabilityRegistry
    from tasks.manager import TaskManager
    from workflow.manager import WorkflowManager
    from workers.manager import WorkerManager
    from workflow.step import WorkflowStep
    from scheduler.policies import SchedulingPolicy


class Scheduler:
    """
    Orchestrates the background scheduling thread loop, matching ready steps
    to idle workers in pools while respecting dependency and priority rules.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        workflow_manager: WorkflowManager,
        capability_registry: CapabilityRegistry,
        worker_manager: WorkerManager,
        event_bus: Any,
        logger: logging.Logger,
        default_policy: SchedulingPolicy | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """
        Initialize the Scheduler.

        Args:
            task_manager: TaskManager.
            workflow_manager: WorkflowManager.
            capability_registry: CapabilityRegistry.
            worker_manager: WorkerManager.
            event_bus: Global EventBus.
            logger: Centralized logger.
            default_policy: Pluggable SchedulingPolicy. Defaults to PriorityPolicy.
            max_retries: Maximum retries for failed steps.
            retry_delay: Delay in seconds between retries.
        """
        self._task_manager = task_manager
        self._workflow_manager = workflow_manager
        self._capability_registry = capability_registry
        self._worker_manager = worker_manager
        self._event_bus = event_bus
        self._logger = logger
        
        self._policy = default_policy or PriorityPolicy()
        self._queue = DispatchQueue(event_bus=event_bus)
        self._monitor = SchedulerMonitor()
        
        self._retry_manager = RetryManager(
            event_bus=event_bus,
            logger=logger,
            max_retries=max_retries,
            base_delay=retry_delay,
        )

        self._allocator = ResourceAllocator(
            capability_registry=capability_registry,
            worker_manager=worker_manager,
            event_bus=event_bus,
            logger=logger,
        )

        self._resolver = DependencyResolver(
            task_manager=task_manager,
            workflow_manager=workflow_manager,
            capability_registry=capability_registry,
            worker_manager=worker_manager,
            logger=logger,
        )

        self._dispatcher = Dispatcher(
            allocator=self._allocator,
            workflow_manager=workflow_manager,
            retry_manager=self._retry_manager,
            monitor=self._monitor,
            event_bus=event_bus,
            re_enqueue_fn=self._re_enqueue,
            logger=logger,
        )

        self._running = False
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._scheduling_loop,
                name="Scheduler-Loop",
                daemon=True,
            )
            self._thread.start()
            self._logger.info("Scheduler started.")

            # Emit SchedulerStarted
            self._event_bus.publish(
                Event(
                    name="SchedulerStarted",
                    source="scheduler",
                    payload={},
                )
            )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background scheduler thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        # Signal blocking queue popped reader to wakeup
        self._queue._condition.acquire()
        self._queue._condition.notify_all()
        self._queue._condition.release()

        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._logger.info("Scheduler stopped.")

        # Cancel active retry timers to prevent thread leak
        try:
            self._retry_manager.cancel_all()
        except Exception:
            pass

        # Emit SchedulerStopped
        self._event_bus.publish(
            Event(
                name="SchedulerStopped",
                source="scheduler",
                payload={},
            )
        )

    @property
    def is_running(self) -> bool:
        """Whether the scheduler loop is active."""
        with self._lock:
            return self._running

    # ------------------------------------------------------------------
    # Public scheduling API
    # ------------------------------------------------------------------

    def schedule(self, step: WorkflowStep) -> None:
        """
        Schedule a step for execution.
        Looks up parent task's priority and enqueues the step.

        Args:
            step: WorkflowStep to execute.
        """
        try:
            workflow = self._workflow_manager.load_workflow(step.workflow_id)
            task = self._task_manager.get_task(workflow.parent_task_id)
            priority = task.priority
        except Exception as e:
            self._logger.error("Failed to schedule step %s: parent task resolve failed: %s", step.step_id, e)
            raise SchedulerError(f"Failed to schedule step {step.step_id}: {e}") from e

        self._queue.push(step, priority)

    def cancel(self, step_id: str) -> bool:
        """
        Cancel a step currently in the queue.

        Args:
            step_id: ID of step to cancel.

        Returns:
            True if cancelled, False if not found.
        """
        return self._queue.remove(step_id)

    def retry(self, step: WorkflowStep) -> None:
        """
        Reset retry count and schedule execution immediately.
        """
        self._retry_manager.clear(step.step_id)
        self.schedule(step)

    def queue_status(self) -> dict[str, Any]:
        """Get queue stats."""
        return self._queue.statistics()

    def active_jobs(self) -> list[str]:
        """Get active step IDs."""
        return self._dispatcher.list_active_jobs()

    def metrics(self) -> dict[str, Any]:
        """Get performance metrics."""
        return self._monitor.metrics(
            queue_length=self._queue.statistics()["length"],
            worker_counts_provider=self._get_worker_counts,
        )

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _re_enqueue(self, step: WorkflowStep, ready_at: datetime) -> None:
        """Internal callback to re-enqueue steps for retries or delay."""
        try:
            workflow = self._workflow_manager.load_workflow(step.workflow_id)
            task = self._task_manager.get_task(workflow.parent_task_id)
            priority = task.priority
            self._queue.push(step, priority, ready_at=ready_at)
        except Exception as e:
            self._logger.error("Failed to re-enqueue step %s: %s", step.step_id, e)

    def _get_worker_counts(self) -> tuple[int, int]:
        """Returns tuple of (idle_workers_count, busy_workers_count)."""
        health = self._worker_manager.health()
        return health["idle_workers"], health["busy_workers"]

    def _scheduling_loop(self) -> None:
        """Background thread main loop."""
        while self._running:
            # Blocking pop with timeout to check running flag periodically
            item = self._queue.pop(policy=self._policy, timeout=0.5)
            if item is None:
                continue

            step = item.step

            # Evaluate execution readiness
            if self._resolver.can_dispatch(step):
                self._logger.info("Scheduling dependencies satisfied for step %s. Dispatching...", step.step_id)
                self._dispatcher.dispatch_async(step, item.priority, item.queued_at)
            else:
                # Re-enqueue the step and then wait (event-driven) for a worker
                # to become available — eliminates the busy-poll / sleep(0.05) pattern
                # that burned CPU under saturation (Architecture Audit CRITICAL #2).
                self._logger.debug("Step %s cannot be scheduled yet. Re-enqueuing and waiting for idle worker.", step.step_id)
                self._re_enqueue(step, datetime.now(timezone.utc))
                self._worker_manager.wait_for_idle_worker(timeout=1.0)
