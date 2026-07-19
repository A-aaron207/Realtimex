"""
Kernel Core.

The Kernel is the central orchestrator of the Realtimex runtime. It
never performs business logic itself; it only coordinates other
components -- the Event Manager, Service Registry, Capability
Registry, and Recovery Manager -- through a well-defined lifecycle.

This class is intentionally thin. Its job is composition, not
computation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from events.manager import EventManager
    from tasks.api import TaskAPI
    from tasks.manager import TaskManager
    from workflow.api import WorkflowAPI
    from workflow.manager import WorkflowManager
    from capabilities.registry import CapabilityRegistry
    from workers.api import WorkerAPI
    from workers.manager import WorkerManager
    from scheduler.api import SchedulerAPI
    from scheduler.scheduler import Scheduler

import time
from events.event import Event
from events.event_types import KernelEventType
from kernel.boot import BootPaths, BootResult, run_boot_sequence
from kernel.lifecycle import KernelState, LifecycleManager
from kernel.shutdown import run_shutdown_sequence
from interfaces.base import Request, Response
from tasks.states import TaskState
from tasks.task import TaskPriority



class Kernel:
    """
    The Realtimex Kernel: a modular, event-driven orchestrator.

    Responsibilities:
        - Own the Kernel's lifecycle state.
        - Coordinate the boot and shutdown sequences.
        - Provide a stable public API (boot, shutdown, restart, status)
          for embedding applications such as main.py.

    The Kernel does not implement AI models, LLM integration, workers,
    scheduling, memory management, workflow execution, or permission
    enforcement. Those are the responsibility of future components
    this Kernel will one day orchestrate.
    """

    def __init__(self, config_path: Path, log_directory: Path, modules_root: Path) -> None:
        """
        Initialize a Kernel instance in the OFFLINE state.

        No I/O or component initialization happens here -- that only
        occurs once `boot()` is called.

        Args:
            config_path: Path to the Kernel's configuration JSON file.
            log_directory: Directory in which log files should be written.
            modules_root: Directory under which module subdirectories live.
        """
        self._boot_paths = BootPaths(
            config_path=config_path, log_directory=log_directory, modules_root=modules_root
        )
        self._lifecycle = LifecycleManager(initial_state=KernelState.OFFLINE)
        self._boot_result: BootResult | None = None
        self._pending_requests: dict[str, Request] = {}

    @property
    def state(self) -> KernelState:
        """The Kernel's current lifecycle state."""
        return self._lifecycle.state

    @property
    def logger(self) -> logging.Logger:
        """
        The Kernel's configured logger.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no logger is available.")
        return self._boot_result.logger

    def boot(self) -> None:
        """
        Run the Kernel's boot sequence and transition into RUNNING.

        Progresses the Kernel through OFFLINE -> BOOTING ->
        INITIALIZING -> READY -> RUNNING. Core component
        initialization (configuration, logger, event bus, registries,
        recovery manager) happens before READY. Once READY, the Kernel
        discovers, validates, imports, and registers every module
        under the modules directory before announcing itself
        operational and transitioning into RUNNING.

        A failure in any individual module never aborts boot -- it is
        isolated, logged, and reported via a ModuleFailed event.

        Raises:
            InvalidStateTransition: If called when the Kernel is not
                currently OFFLINE.
        """
        self._lifecycle.transition_to(KernelState.BOOTING)
        self._lifecycle.transition_to(KernelState.INITIALIZING)

        self._boot_result = run_boot_sequence(self._boot_paths)

        self._lifecycle.transition_to(KernelState.READY)
        self._boot_result.event_bus.emit(
            Event(name=KernelEventType.KERNEL_READY, source="kernel.boot")
        )
        self._boot_result.logger.info("Kernel Ready.")

        self._boot_result.loaded_modules = self._boot_result.module_loader.load()

        self._boot_result.event_bus.emit(
            Event(
                name=KernelEventType.KERNEL_OPERATIONAL,
                source="kernel.boot",
                payload={"loaded_modules": len(self._boot_result.loaded_modules)},
            )
        )
        self._boot_result.logger.info(
            "Kernel Operational. Loaded modules: %d", len(self._boot_result.loaded_modules)
        )

        # Register request handler on interface manager
        self._boot_result.interface_manager.set_request_handler(self.handle_request)

        # Subscribe to StepCompleted event to progress workflows automatically
        self._boot_result.event_bus.subscribe("StepCompleted", self._on_step_completed)

        self._lifecycle.transition_to(KernelState.RUNNING)

    @property
    def event_manager(self) -> EventManager:
        """
        The Kernel's Event Manager.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no event manager is available.")
        return self._boot_result.event_manager

    @property
    def loaded_modules(self) -> list[LoadedModule]:
        """
        The list of modules successfully loaded into the Kernel.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no loaded modules are available.")
        return self._boot_result.loaded_modules

    @property
    def capability_registry(self) -> CapabilityRegistry:
        """
        The Capability Registry.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no capability registry is available.")
        return self._boot_result.capability_registry

    @property
    def task_manager(self) -> TaskManager:
        """
        The Kernel's Task Manager.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no task manager is available.")
        return self._boot_result.task_manager

    @property
    def task_api(self) -> TaskAPI:
        """
        The Kernel's Task Search API.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no task API is available.")
        return self._boot_result.task_api

    @property
    def workflow_manager(self) -> WorkflowManager:
        """
        The Kernel's Workflow Manager.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no workflow manager is available.")
        return self._boot_result.workflow_manager

    @property
    def workflow_api(self) -> WorkflowAPI:
        """
        The Kernel's Workflow API.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no workflow API is available.")
        return self._boot_result.workflow_api

    @property
    def worker_manager(self) -> WorkerManager:
        """
        The Kernel's Worker Manager.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no worker manager is available.")
        return self._boot_result.worker_manager

    @property
    def worker_api(self) -> WorkerAPI:
        """
        The Kernel's Worker API.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no worker API is available.")
        return self._boot_result.worker_api

    @property
    def scheduler(self) -> Scheduler:
        """
        The Kernel's Scheduler.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no scheduler is available.")
        return self._boot_result.scheduler

    @property
    def scheduler_api(self) -> SchedulerAPI:
        """
        The Kernel's Scheduler API.

        Raises:
            RuntimeError: If accessed before the Kernel has booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no scheduler API is available.")
        return self._boot_result.scheduler_api

    @property
    def config_manager(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no config manager is available.")
        return self._boot_result.config_manager

    @property
    def dependency_container(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no dependency container is available.")
        return self._boot_result.dependency_container


    @property
    def observability(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no observability is available.")
        return self._boot_result.observability

    @property
    def policy_manager(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no policy manager is available.")
        return self._boot_result.policy_manager

    @property
    def security_manager(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no security manager is available.")
        return self._boot_result.security_manager

    @property
    def interface_manager(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no interface manager is available.")
        return self._boot_result.interface_manager

    @property
    def memory_manager(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no memory manager is available.")
        return self._boot_result.memory_manager

    @property
    def model_gateway(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no model gateway is available.")
        return self._boot_result.model_gateway

    @property
    def cognitive_engine(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no cognitive engine is available.")
        return self._boot_result.cognitive_engine

    @property
    def permission_manager(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no permission manager is available.")
        return self._boot_result.permission_manager

    def shutdown(self) -> None:
        """
        Run the Kernel's shutdown sequence and return to OFFLINE.

        Progresses the Kernel through RUNNING -> SHUTTING_DOWN ->
        OFFLINE.

        Raises:
            InvalidStateTransition: If called when the Kernel is not
                currently RUNNING.
            RuntimeError: If the Kernel never successfully booted.
        """
        if self._boot_result is None:
            raise RuntimeError("Cannot shut down a Kernel that has not booted.")

        self._lifecycle.transition_to(KernelState.SHUTTING_DOWN)
        
        # Stop new background threads
        try:
            self._boot_result.config_manager.shutdown()
        except Exception:
            pass
        try:
            self._boot_result.observability.metrics_mgr.stop_export_loop()
        except Exception:
            pass
        try:
            self._boot_result.interface_manager.stop_all()
        except Exception:
            pass
            
        run_shutdown_sequence(self._boot_result.event_bus, self._boot_result.logger)
        self._boot_result.scheduler.stop()
        self._boot_result.event_manager.shutdown()
        self._lifecycle.transition_to(KernelState.OFFLINE)

    def restart(self) -> None:
        """
        Shut down and re-boot the Kernel.

        Equivalent to calling `shutdown()` followed by `boot()`. Any
        in-memory placeholder state (registries, recovery incidents)
        is reset, since new component instances are created during
        the subsequent boot sequence.

        Raises:
            InvalidStateTransition: If called when the Kernel is not
                currently RUNNING.
        """
        if self._boot_result is not None:
            self._boot_result.event_bus.emit(
                Event(name=KernelEventType.KERNEL_RESTART_REQUESTED, source="kernel.api")
            )
        self.shutdown()
        self.boot()

    def find_capability_provider(self, capability: str) -> str:
        """
        Ask the Capability Registry which module provides a capability.

        Example: `kernel.find_capability_provider("summarize_text")`
        answers "who can summarize text?" by returning the module_id
        of the first registered provider. The Kernel never executes
        the capability itself -- that belongs to a future Task
        Manager / Scheduler milestone.

        Args:
            capability: The capability name to look up.

        Returns:
            The module_id of the first registered provider.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
            CapabilityNotFoundError: If no provider is registered for
                this capability.
        """
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no capabilities are registered.")
        return self._boot_result.capability_registry.find(capability).provider_id

    def status(self) -> dict[str, object]:
        """
        Report the Kernel's current status.

        Returns:
            A dictionary describing the Kernel's lifecycle state and,
            once booted, summary information about its components.
        """
        summary: dict[str, object] = {"state": str(self.state)}

        if self._boot_result is not None:
            summary.update(
                {
                    "kernel_name": self._boot_result.config.kernel_name,
                    "version": self._boot_result.config.version,
                    "environment": self._boot_result.config.environment,
                    "registered_services": self._boot_result.service_registry.list_services(),
                    "registered_capabilities": self._boot_result.capability_registry.list_capabilities(),
                    "loaded_modules": [
                        loaded.manifest.module_id for loaded in self._boot_result.loaded_modules
                    ],
                    "module_failures": [
                        {"module": failure.module_path, "stage": failure.stage, "reason": failure.reason}
                        for failure in self._boot_result.module_loader.failures()
                    ],
                    "recovery_enabled": self._boot_result.recovery_manager.enabled,
                    "events_emitted": len(self._boot_result.event_bus.history()),
                    "event_history_size": self._boot_result.event_manager.history_size,
                    "event_subscribers": self._boot_result.event_manager.subscriber_count,
                    "active_tasks": len(self._boot_result.task_manager.list_tasks(active_only=True)),
                    "completed_tasks": len(self._boot_result.task_manager.list_tasks(completed_only=True)),
                    "workflows_total": len(self._boot_result.workflow_manager._cache),
                    "workers_total": self._boot_result.worker_manager.health().get("total_workers", 0),
                    "scheduler_queue_length": self._boot_result.scheduler.queue_status()["length"],
                    "scheduler_active_jobs": len(self._boot_result.scheduler.active_jobs()),
                }
            )

        return summary

    def handle_request(self, request: Request) -> Response:
        """
        Handle incoming requests from interfaces.
        """
        action = request.user_input.get("action")
        if not action:
            return Response(
                request_id=request.request_id,
                status="error",
                message="No action provided."
            )
            
        args = request.user_input.get("args", [])
        goal = request.user_input.get("raw") or (str(action) + " " + " ".join(map(str, args))).strip()

        # 1. Task Created
        task = self.task_manager.create_task(
            goal=goal,
            priority=TaskPriority.NORMAL
        )
        
        # Map task ID to Request
        self._pending_requests[task.task_id] = request
        
        # Progress Task lifecycle
        self.task_manager.update_state(task.task_id, TaskState.PLANNING)
        self.task_manager.update_state(task.task_id, TaskState.QUEUED)
        self.task_manager.update_state(task.task_id, TaskState.RUNNING)
        
        # 2. Workflow Generated
        wf = self.workflow_manager.create_workflow(task.task_id, task.goal)
        
        # 3. Schedule initial steps
        ready_steps = self.workflow_manager.ready_steps(wf.workflow_id)
        for step in ready_steps:
            self.scheduler_api.schedule(step)
            
        return Response(
            request_id=request.request_id,
            status="running",
            message=f"Task {task.task_id} is running.",
            metadata={"task_id": task.task_id}
        )

    def _on_step_completed(self, event: Event) -> None:
        """
        Triggered when a workflow step completes. Progresses the workflow.
        """
        step_id = event.payload.get("step_id")
        workflow_id = event.task_id  # Event task_id stores workflow_id for steps
        
        try:
            # Give a tiny time for DB/cache state to align
            time.sleep(0.05)
            
            workflow = self.workflow_manager.load_workflow(workflow_id)
            task_id = workflow.parent_task_id
            
            # Fetch next ready steps
            next_ready = self.workflow_manager.ready_steps(workflow_id)
            if next_ready:
                for step in next_ready:
                    self.scheduler_api.schedule(step)
            else:
                # No more ready steps. Check if workflow completed.
                wf_current = self.workflow_manager.load_workflow(workflow_id)
                from workflow.step import StepState
                if all(s.status == StepState.COMPLETED for s in wf_current.steps.values()):
                    # Workflow is complete!
                    # 1. Update Task to COMPLETED
                    self.task_manager.update_state(task_id, TaskState.COMPLETED)
                    
                    # 2. Retrieve outputs from all steps
                    output_parts = []
                    for s_id, step in wf_current.steps.items():
                        if step.output_data:
                            val = step.output_data.get("summary") or step.output_data.get("output") or step.output_data.get("file_contents") or step.output_data.get("results") or step.output_data.get("code")
                            if not val and "bytes_written" in step.output_data:
                                val = f"Wrote {step.output_data['bytes_written']} bytes to {step.output_data.get('file_path')}."
                            if not val and step.output_data.get("status") == "SUCCESS":
                                val = "SUCCESS"
                            if val:
                                output_parts.append(f"[{s_id}] {val}")
                    
                    summary_text = "\n".join(output_parts) if output_parts else "No output found."
                    
                    # 3. Memory Update
                    self.memory_manager.create(
                        scope="task",
                        owner=task_id,
                        content=f"Workflow result: {summary_text}",
                        source="kernel"
                    )
                    
                    # 4. Response Returned to Interface
                    req = self._pending_requests.pop(task_id, None)
                    if req:
                        final_res = Response(
                            request_id=req.request_id,
                            status="completed",
                            message=summary_text,
                            data={"output": summary_text}
                        )
                        self.interface_manager.send(final_res)
        except Exception as e:
            self.logger.error("Error in automatic workflow progression: %s", e)

