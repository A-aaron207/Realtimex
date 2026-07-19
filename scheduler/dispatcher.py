"""
Dispatcher coordinating worker allocation, background step execution, and report handling.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from events.event import Event
from workers.context import ExecutionContext
from workflow.step import StepState

if TYPE_CHECKING:
    from scheduler.allocator import ResourceAllocator
    from scheduler.monitor import SchedulerMonitor
    from scheduler.retry import RetryManager
    from workflow.manager import WorkflowManager
    from workflow.step import WorkflowStep
    from tasks.task import TaskPriority


class Dispatcher:
    """
    Spawns background execution threads, allocates workers, builds ExecutionContext,
    executes capability code, updates task/step states, and triggers retries on failure.
    """

    def __init__(
        self,
        allocator: ResourceAllocator,
        workflow_manager: WorkflowManager,
        retry_manager: RetryManager,
        monitor: SchedulerMonitor,
        event_bus: Any,
        re_enqueue_fn: Callable[[WorkflowStep, datetime], None],
        logger: logging.Logger,
    ) -> None:
        """
        Initialize Dispatcher.

        Args:
            allocator: ResourceAllocator instance.
            workflow_manager: WorkflowManager instance.
            retry_manager: RetryManager instance.
            monitor: SchedulerMonitor instance.
            event_bus: Global EventBus.
            re_enqueue_fn: Re-enqueue callback.
            logger: Diagnostics logger.
        """
        self._allocator = allocator
        self._workflow_manager = workflow_manager
        self._retry_manager = retry_manager
        self._monitor = monitor
        self._event_bus = event_bus
        self._re_enqueue_fn = re_enqueue_fn
        self._logger = logger
        self._active_jobs_lock = threading.RLock()
        self._active_jobs: dict[str, threading.Thread] = {}

    def dispatch_async(
        self,
        step: WorkflowStep,
        priority: TaskPriority,
        queued_at: datetime,
    ) -> None:
        """
        Spawn a daemon thread to allocate a worker and execute the step asynchronously.
        """
        thread = threading.Thread(
            target=self._run_dispatch,
            args=(step, priority, queued_at),
            name=f"DispatchJob-{step.step_id}",
            daemon=True,
        )
        with self._active_jobs_lock:
            self._active_jobs[step.step_id] = thread
        thread.start()

    def is_job_running(self, step_id: str) -> bool:
        """Check if job is active."""
        with self._active_jobs_lock:
            return step_id in self._active_jobs

    def list_active_jobs(self) -> list[str]:
        """Return list of active step IDs currently running."""
        with self._active_jobs_lock:
            return list(self._active_jobs.keys())

    def _run_dispatch(
        self,
        step: WorkflowStep,
        priority: TaskPriority,
        queued_at: datetime,
    ) -> None:
        """
        Thread target: allocate worker, build context, execute, update status,
        and manage retries.
        """
        self._logger.info("Starting dispatch sequence for step %s...", step.step_id)

        # 1. Allocate worker
        allocation = self._allocator.allocate_worker(step.capability)
        if not allocation:
            # Re-enqueue and retry later: no idle worker available
            self._logger.debug("Re-enqueuing step %s due to worker unavailability", step.step_id)
            time.sleep(0.1)  # Throttle to avoid hot-loop thread thrashing
            self._re_enqueue_fn(step, datetime.now(timezone.utc))
            with self._active_jobs_lock:
                self._active_jobs.pop(step.step_id, None)
            return

        worker, provider_id = allocation
        worker_id = worker.worker_id

        # 2. Record dispatch stats
        now = datetime.now(timezone.utc)
        wait_time = (now - queued_at).total_seconds()
        self._monitor.record_dispatched(step.step_id, wait_time)

        # Emit StepDispatched
        self._event_bus.publish(
            Event(
                name="StepDispatched",
                source="scheduler.dispatcher",
                task_id=step.workflow_id,
                payload={"step_id": step.step_id, "worker_id": worker_id},
            )
        )

        # 3. Transition step status to RUNNING in WorkflowManager
        try:
            workflow = self._workflow_manager.load_workflow(step.workflow_id)
            self._workflow_manager.update_step_status(
                workflow_id=step.workflow_id,
                step_id=step.step_id,
                new_status=StepState.RUNNING,
            )
        except Exception as e:
            self._logger.exception("Failed to update step status to RUNNING: %s", e)
            self._allocator.release_worker(step.capability, worker_id)
            with self._active_jobs_lock:
                self._active_jobs.pop(step.step_id, None)
            return

        # 4. Generate Execution Context and run worker
        # Check permissions block
        permissions = {}
        if hasattr(worker, "_module_resolver"):
            loaded_mod = worker._module_resolver(provider_id)
            if loaded_mod and hasattr(loaded_mod, "manifest"):
                permissions = loaded_mod.manifest.permissions

        attempt = self._retry_manager.get_attempts(step.step_id)
        context = ExecutionContext(
            task_id=workflow.parent_task_id,
            workflow_id=step.workflow_id,
            step_id=step.step_id,
            capability=step.capability,
            input=step.input_data,
            configuration={"provider_id": provider_id},
            permissions=permissions,
            metadata={"attempt": attempt},
        )

        try:
            # Invoke execution on worker
            report = worker.execute(context)
            
            # Process WorkerReport
            if report.status.value == "SUCCESS":
                self._logger.info("Step %s completed successfully by %s", step.step_id, worker_id)
                
                # Update Workflow step to COMPLETED
                self._workflow_manager.update_step_status(
                    workflow_id=step.workflow_id,
                    step_id=step.step_id,
                    new_status=StepState.COMPLETED,
                    output_data=report.output,
                )

                # Record in monitor
                exec_time = report.metrics.get("execution_time", 0.0)
                self._monitor.record_completed(step.step_id, exec_time)
                self._retry_manager.clear(step.step_id)

                # Emit StepCompleted
                self._event_bus.publish(
                    Event(
                        name="StepCompleted",
                        source="scheduler.dispatcher",
                        task_id=step.workflow_id,
                        payload={"step_id": step.step_id, "worker_id": worker_id},
                    )
                )
            else:
                raise RuntimeError(report.error_message or "Worker execution failed.")

        except Exception as e:
            self._logger.error("Step %s failed execution on worker %s: %s", step.step_id, worker_id, e)
            self._monitor.record_failed(step.step_id)

            # Check if we should retry
            if self._retry_manager.should_retry(step):
                # Set step state back to WAITING or PENDING
                try:
                    self._workflow_manager.update_step_status(
                        workflow_id=step.workflow_id,
                        step_id=step.step_id,
                        new_status=StepState.WAITING,
                    )
                except Exception as ex:
                    self._logger.warning("Failed to reset step state during retry: %s", ex)

                # Schedule retry re-enqueue
                self._retry_manager.schedule_retry(step, self._re_enqueue_fn)
            else:
                # Max retries reached: set status to FAILED
                self._logger.error("Step %s has failed all retry attempts. Setting to FAILED.", step.step_id)
                try:
                    self._workflow_manager.update_step_status(
                        workflow_id=step.workflow_id,
                        step_id=step.step_id,
                        new_status=StepState.FAILED,
                    )
                except Exception as ex:
                    self._logger.exception("Failed to update step status to FAILED: %s", ex)

                # Emit StepFailed
                self._event_bus.publish(
                    Event(
                        name="StepFailed",
                        source="scheduler.dispatcher",
                        task_id=step.workflow_id,
                        payload={"step_id": step.step_id, "reason": str(e)},
                    )
                )

        finally:
            # 5. Clean up worker allocation and active jobs dictionary
            self._allocator.release_worker(step.capability, worker_id)
            with self._active_jobs_lock:
                self._active_jobs.pop(step.step_id, None)
