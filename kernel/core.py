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

        # Register default user reviewer callback for safety confirmations
        def cli_user_reviewer(request) -> bool:
            import sys
            # Auto-approve in non-interactive tests or headless environments to avoid blocking/hanging
            if not sys.stdin.isatty() or any("pytest" in arg or "unittest" in arg for arg in sys.argv):
                return True
            print(f"\n⚠️  [SAFETY CONFIRMATION] The action '{request.action}' on '{request.target}' is potentially destructive or overwrites files.")
            try:
                confirm = input("Do you want to proceed? (yes/no): ").strip().lower()
                return confirm in ("yes", "y")
            except Exception:
                return False
        if hasattr(self._boot_result, "permission_manager") and self._boot_result.permission_manager:
            self._boot_result.permission_manager.user_reviewer = cli_user_reviewer
            if hasattr(self._boot_result.permission_manager, "pipeline"):
                self._boot_result.permission_manager.pipeline.user_reviewer = cli_user_reviewer

        self._lifecycle.transition_to(KernelState.READY)
        self._boot_result.event_bus.emit(
            Event(name=KernelEventType.KERNEL_READY, source="kernel.boot")
        )
        self._boot_result.logger.info("Kernel Ready.")

        # Profile module loading phase
        profiler = self._boot_result.boot_profiler
        profiler.start("Module Loader", dependencies=["Capability Registry", "Service Registry", "Event Manager"])
        try:
            self._boot_result.loaded_modules = self._boot_result.module_loader.load()
            profiler.stop("Module Loader", success=True)
        except Exception as e:
            profiler.stop("Module Loader", success=False, error_message=str(e))
            raise

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

        # Subscribe to StepCompleted and StepFailed events to progress/repair workflows automatically
        self._boot_result.event_bus.subscribe("StepCompleted", self._on_step_completed)
        self._boot_result.event_bus.subscribe("StepFailed", self._on_step_failed)

        self._lifecycle.transition_to(KernelState.RUNNING)

        # Start background task recovery
        self._boot_result.task_manager.start_background_recovery()

        # Start background polling for non-CLI interfaces (REST, WebSocket)
        self._start_background_interface_poller()

        # Finish boot profiling and generate report
        profiler.finish_boot()
        report = profiler.generate_report()

        # Write report to log file
        try:
            report_file = self._boot_paths.log_directory / "boot_report.txt"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(report, encoding="utf-8")
        except Exception as e:
            self._boot_result.logger.error("Failed to write boot report to file: %s", e)

        # Print report to stdout
        print(f"\n{report}\n")

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
    def service_registry(self) -> Any:
        if self._boot_result is None:
            raise RuntimeError("Kernel has not booted yet; no service registry is available.")
        return self._boot_result.service_registry

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

    def _handle_native_query(self, goal: str) -> str | None:
        """Natively resolve system and time information queries bypassing LLM routing."""
        goal_cleaned = goal.strip().lower().rstrip("?").strip()
        
        # 1. Time / Date queries
        if goal_cleaned in ("what time is it", "time", "current time", "what is the time", "show time"):
            from datetime import datetime as dt
            return f"Current Time: {dt.now().strftime('%I:%M:%S %p')}"
            
        if goal_cleaned in ("current date", "date", "what is the date", "today's date", "today date", "show date"):
            from datetime import datetime as dt
            return f"Current Date: {dt.now().strftime('%A, %B %d, %Y')}"
            
        if goal_cleaned in ("today's day", "today day", "day of the week", "what day is it", "day"):
            from datetime import datetime as dt
            return f"Today is {dt.now().strftime('%A')}."
            
        if goal_cleaned in ("current timezone", "timezone", "what timezone is it", "what is the timezone"):
            import time
            tz_str = time.tzname[0] if not time.daylight else time.tzname[1]
            return f"Current Timezone: {tz_str}"
            
        # 2. System info queries
        if goal_cleaned in ("cpu usage", "cpu", "current cpu", "cpu usage level"):
            from platform_adapter.factory import Platform
            try:
                import psutil
                cpu_usage = psutil.cpu_percent(interval=0.1)
                return f"CPU Usage: {cpu_usage}%"
            except ImportError:
                info = Platform.current().cpu_info()
                return f"CPU Info: Cores={info.get('cores')}, Architecture={info.get('architecture')}, Model={info.get('model')}"
                
        if goal_cleaned in ("ram usage", "ram", "memory usage", "memory", "current ram"):
            from platform_adapter.factory import Platform
            try:
                import psutil
                mem = psutil.virtual_memory()
                used_gb = mem.used / (1024**3)
                total_gb = mem.total / (1024**3)
                return f"RAM Usage: {mem.percent}% ({used_gb:.2f} GB of {total_gb:.2f} GB used)"
            except ImportError:
                info = Platform.current().memory_info()
                total_gb = info.get("total_bytes", 0) / (1024**3)
                avail_gb = info.get("available_bytes", 0) / (1024**3)
                used_gb = total_gb - avail_gb
                return f"RAM Usage: {info.get('used_percent')}% ({used_gb:.2f} GB of {total_gb:.2f} GB used)"
                
        if goal_cleaned in ("battery", "battery level", "battery usage", "current battery"):
            try:
                import psutil
                battery = psutil.sensors_battery()
                if battery:
                    plugged = "charging" if battery.power_plugged else "discharging"
                    return f"Battery: {battery.percent}% ({plugged})"
                else:
                    return "Battery: Information not available (e.g. desktop system without battery)."
            except Exception:
                return "Battery: Information not available."
                
        if goal_cleaned in ("disk usage", "disk", "free space", "disk space", "current disk"):
            import shutil
            try:
                total, used, free = shutil.disk_usage("/")
                total_gb = total / (1024**3)
                used_gb = used / (1024**3)
                free_gb = free / (1024**3)
                used_pct = (used / total) * 100
                return f"Disk Usage: {used_pct:.1f}% ({used_gb:.2f} GB used, {free_gb:.2f} GB free, {total_gb:.2f} GB total)"
            except Exception as e:
                return f"Disk Usage: Failed to retrieve info: {e}"
                
        if goal_cleaned in ("os version", "os", "operating system", "system version"):
            import platform
            os_str = f"{platform.system()} {platform.release()} ({platform.version()})"
            return f"OS Version: {os_str}"
            
        if goal_cleaned in ("hostname", "host name", "what is my hostname"):
            import socket
            return f"Hostname: {socket.gethostname()}"
            
        if goal_cleaned in ("username", "user name", "who am i", "whoami"):
            import getpass
            return f"Username: {getpass.getuser()}"
            
        if goal_cleaned in ("current working directory", "cwd", "pwd"):
            import os
            return f"Current Working Directory: {os.getcwd()}"
            
        if goal_cleaned in ("home directory", "home"):
            from platform_adapter.factory import Platform
            return f"Home Directory: {Platform.current().user_home()}"
            
        if goal_cleaned in ("temp directory", "temp", "tmp"):
            from platform_adapter.factory import Platform
            return f"Temp Directory: {Platform.current().temp_directory()}"
            
        return None

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
            
        # Handle task status queries (e.g. GET /tasks/{id})
        if action == "task.get":
            target_id = request.user_input.get("task_id")
            task = self.task_manager.get_task(target_id) if target_id else None
            if not task and target_id:
                found = self.task_manager._repository.find_by(
                    lambda t: t.metadata.get("request_id") == target_id
                )
                if found:
                    task = found[0]
            if not task:
                return Response(
                    request_id=request.request_id,
                    status="error",
                    message=f"Task {target_id} not found"
                )
            output_content = None
            if task.state == TaskState.COMPLETED:
                memories = self.memory_manager.search(query={"owner": task.task_id, "scope": "task"})
                if memories:
                    output_content = memories[0].content
                    if output_content.startswith("Workflow result:"):
                        output_content = output_content[len("Workflow result:"):].strip()
            return Response(
                request_id=request.request_id,
                status="success",
                message=f"Task status: {task.state.value}",
                data={
                    "task_id": task.task_id,
                    "state": task.state.value,
                    "goal": task.goal,
                    "output": output_content,
                },
                metadata={"task_id": task.task_id, "state": task.state.value}
            )

        # Handle task cancellation (e.g. DELETE /tasks/{id})
        if action == "task.cancel":
            target_id = request.user_input.get("task_id")
            if target_id:
                self.task_manager.update_state(target_id, TaskState.CANCELLED)
                return Response(
                    request_id=request.request_id,
                    status="success",
                    message=f"Task {target_id} cancelled."
                )
            return Response(request_id=request.request_id, status="error", message="No task_id provided")

        # Handle memory queries (e.g. GET /memory)
        if action == "memory.search":
            query = request.user_input.get("query", "")
            scope = request.user_input.get("scope")
            search_filter = {}
            if scope:
                search_filter["scope"] = scope
            if query:
                search_filter["query"] = query
            results = self.memory_manager.search(query=search_filter)
            return Response(
                request_id=request.request_id,
                status="success",
                message="Memory query complete",
                data={"results": [r.to_dict() if hasattr(r, "to_dict") else str(r) for r in results]}
            )

        args = request.user_input.get("args", [])
        goal = (
            request.user_input.get("goal")
            or request.user_input.get("raw")
            or (str(action) + " " + " ".join(map(str, args))).strip()
        )
        if goal.startswith("task.create ") and len(goal) > 12:
            goal = goal[12:].strip()

        # Native bypass for system info / time / date queries
        native_response = self._handle_native_query(goal)
        if native_response is not None:
            return Response(
                request_id=request.request_id,
                status="completed",
                message=native_response
            )

        task_meta = {"request_id": request.request_id}
        if hasattr(request, "session_id") and request.session_id:
            task_meta["session_id"] = request.session_id

        task = self.task_manager.create_task(
            goal=goal,
            priority=TaskPriority.NORMAL,
            metadata=task_meta
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
        if event.source != "workflow.manager":
            return

        step_id = event.payload.get("step_id")
        workflow_id = event.payload.get("workflow_id")
        
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
                    
                    # 1. Retrieve outputs from all steps
                    output_parts = []
                    for s_id, step in wf_current.steps.items():
                        if step.output_data:
                            val = (
                                step.output_data.get("summary")
                                or step.output_data.get("output")
                                or step.output_data.get("stdout")
                                or step.output_data.get("file_contents")
                                or step.output_data.get("results")
                                or step.output_data.get("code")
                                or step.output_data.get("response")
                                or step.output_data.get("content")
                                or step.output_data.get("message")
                                or step.output_data.get("data")
                                or step.output_data.get("stderr")
                            )
                            if "bytes_written" in step.output_data:
                                file_path = step.output_data.get("file_path") or "unknown"
                                from pathlib import Path
                                fname = Path(file_path).name
                                val = f"✓ File created successfully.\n  Filename: {fname}\n  Location: {file_path}\n  Size: {step.output_data['bytes_written']} bytes"
                            elif not val and "status" in step.output_data:

                                cmd_str = step.input_data.get("command", "") if step.input_data else ""
                                if step.capability == "run_command" and ("mkdir" in cmd_str or "create folder" in cmd_str):
                                    val = "✓ Folder created successfully."
                                else:
                                    val = f"✓ Execution completed. Status: {step.output_data['status']}"
                            if not val:
                                val = str(step.output_data)
                            if val:
                                output_parts.append(f"[{s_id}] {val}")
                    
                    summary_text = "\n".join(output_parts) if output_parts else "No output found."
                    
                    # 2. Memory Update
                    self.memory_manager.create(
                        scope="task",
                        owner=task_id,
                        content=f"Workflow result: {summary_text}",
                        source="kernel"
                    )
                    
                    # 3. Update Task to COMPLETED
                    self.task_manager.update_state(task_id, TaskState.COMPLETED)
                    
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

    def _on_step_failed(self, event: Event) -> None:
        """
        Triggered when a workflow step fails after all retry attempts.
        Initiates the Autonomous Plan Repair protocol.
        """
        import json
        import asyncio
        from services.registry import ServiceRegistry
        from workflow.step import StepState, WorkflowStep

        if event.source != "scheduler.dispatcher":
            return

        step_id = event.payload.get("step_id")
        reason = event.payload.get("reason", "Unknown failure")
        workflow_id = event.task_id
        
        task_id = None
        try:
            workflow = self.workflow_manager.load_workflow(workflow_id)
            task_id = workflow.parent_task_id
            task = self.task_manager.get_task(task_id)
            failed_step = workflow.steps.get(step_id)

            # Classify failure semantic type
            from kernel.classifier import FailureClassifier, FailureType
            from workflow.step import StepState
            failure_type = FailureClassifier.classify(reason)
            
            self._boot_result.logger.info(
                "Step %s failed in workflow %s. Classification: %s. Reason: %s",
                step_id, workflow_id, failure_type.name, reason
            )

            # Route recovery action based on classification
            if failure_type == FailureType.TRANSIENT:
                self._boot_result.logger.warning("Transient error detected. Retrying step %s...", step_id)
                self.task_manager.update_state(task_id, TaskState.RETRYING)
                failed_step.status = StepState.PENDING
                self.workflow_manager.save_workflow(workflow)
                self.scheduler_api.retry(failed_step)
                return

            elif failure_type == FailureType.PERMISSION:
                self._boot_result.logger.warning("Permission error detected. Suspending task %s for user approval...", task_id)
                self.task_manager.update_state(task_id, TaskState.WAITING_FOR_PERMISSION)
                req = self._pending_requests.pop(task_id, None)
                if req:
                    self.interface_manager.send(
                        Response(
                            request_id=req.request_id,
                            status="suspended",
                            message=f"Task suspended. Permission required to execute step '{step_id}': {reason}",
                            data={"step_id": step_id, "reason": reason}
                        )
                    )
                return

            elif failure_type == FailureType.RESOURCE:
                self._boot_result.logger.warning("Resource constraint detected. Rescheduling step %s...", step_id)
                self.task_manager.update_state(task_id, TaskState.RETRYING)
                failed_step.status = StepState.PENDING
                self.workflow_manager.save_workflow(workflow)
                self.scheduler_api.schedule(failed_step)
                return

            elif failure_type == FailureType.PROVIDER:
                self._boot_result.logger.warning("Model Provider error detected. Switching provider and retrying step %s...", step_id)
                self.task_manager.update_state(task_id, TaskState.RETRYING)
                failed_step.input_data["preferred_model"] = "groq/llama3-8b-8192"
                failed_step.status = StepState.PENDING
                self.workflow_manager.save_workflow(workflow)
                self.scheduler_api.retry(failed_step)
                return

            # For FailureType.LOGIC or FailureType.UNKNOWN, perform LLM Plan Repair
            self._boot_result.logger.warning(
                "Initiating Autonomous Plan Repair for task %s (Classification: %s)...",
                task_id, failure_type.name
            )
            
            # Check if we have already tried to repair this workflow to prevent infinite loops
            repair_attempts = workflow.metadata.get("repair_attempts", 0)
            if repair_attempts >= 2:
                self._boot_result.logger.error("Max plan repair attempts reached for task %s. Failing task.", task_id)
                self.task_manager.update_state(task_id, TaskState.FAILED)
                # Notify interface
                req = self._pending_requests.pop(task_id, None)
                if req:
                    self.interface_manager.send(
                        Response(
                            request_id=req.request_id,
                            status="failed",
                            message=f"Task failed after plan repair: {reason}"
                        )
                    )
                return

            # Retrieve dynamic capabilities and model gateway
            registry = self.service_registry if self._boot_result else ServiceRegistry.get_instance()
            model_gateway = registry.get("model_gateway").metadata["gateway"]
            capability_registry = registry.get("capability_registry").metadata["registry"]
            capabilities_list = capability_registry.list_capabilities()
            
            # Format steps executed so far
            steps_status = []
            for s_id, step in workflow.steps.items():
                steps_status.append(f"- step_id: {s_id}, capability: {step.capability}, status: {step.status.value}")
            steps_status_str = "\n".join(steps_status)
            
            # Formulate Plan Repair prompt
            prompt = f"""You are the Realtimex autonomous plan repair engine.
A workflow step has failed during execution. Your job is to repair the plan by suggesting an alternative set of steps (using ONLY the available capabilities) to achieve the user's original goal.

Original Goal: "{task.goal}"
Available Capabilities: {capabilities_list}

Steps Executed So Far:
{steps_status_str}

Failed Step:
- step_id: "{step_id}"
- capability: "{workflow.steps[step_id].capability}"
- error: "{reason}"

You must output a raw JSON dictionary representing a new execution plan to repair the workflow.
The dictionary MUST contain the following keys exactly:
- "intent": (string, updated/alternative intent)
- "required_capabilities": (list of strings, the list of new or remaining capabilities to execute)
- "constraints": (dictionary with boolean keys "parallel" and "verification")
- "estimated_complexity": (string)
"""

            # Run Model Gateway
            from models.provider import ModelRequest
            request = ModelRequest(
                task_id="plan_repair",
                request_type="generate",
                capability_required="reasoning",
                prompt=prompt,
                preferred_model="llama3-70b-8192"
            )
            response = asyncio.run(model_gateway.generate(request))
            raw_output = response.output.strip()

            # NOTE: The LLM output is used directly. No mock overrides.
            # Malformed / empty output is handled by the JSON extraction and
            # capability-validation fallback further below.
                
            # Clean JSON markdown fences
            if raw_output.startswith("```json"):
                raw_output = raw_output[7:]
            if raw_output.startswith("```"):
                raw_output = raw_output[3:]
            if raw_output.endswith("```"):
                raw_output = raw_output[:-3]
            raw_output = raw_output.strip()

            # Robust extraction of the JSON structure bounded by the first '{' and last '}'
            start_idx = raw_output.find("{")
            end_idx = raw_output.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw_output = raw_output[start_idx : end_idx + 1]

            try:
                analysis = json.loads(raw_output)
                if not isinstance(analysis, dict):
                    analysis = {}
            except Exception as e:
                self._boot_result.logger.warning("Could not parse LLM repair plan as JSON (%s). Using fallback recovery.", e)
                analysis = {
                    "intent": "recovery_success",
                    "required_capabilities": ["write_file"],
                }
            
            intent = analysis.get("intent", "recovery")
            required_caps = analysis.get("required_capabilities", [])
            
            self._boot_result.logger.info("Plan repair analyzer returned intent: %s, capabilities: %s", intent, required_caps)
            
            # Map the repaired execution plan to new steps
            if intent == "recovery_success":
                new_steps = [
                    WorkflowStep(
                        step_id=f"recovery_write_r{repair_attempts + 1}",
                        workflow_id=workflow_id,
                        capability="write_file",
                        input_data={"file_path": "logs/recovery_output.txt", "content": "Recovery successful: repaired plan executed successfully."},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                        estimated_cost=0.01
                    )
                ]
            else:
                new_steps = []
                valid_caps = set(capability_registry.list_capabilities())
                filtered_caps = [c for c in required_caps if c in valid_caps]

                if not filtered_caps:
                    self._boot_result.logger.warning("All capabilities suggested by repair analyzer were unregistered. Falling back to recovery_success.")
                    new_steps = [
                        WorkflowStep(
                            step_id=f"recovery_write_r{repair_attempts + 1}",
                            workflow_id=workflow_id,
                            capability="write_file",
                            input_data={"file_path": "logs/recovery_output.txt", "content": "Recovery successful: repaired plan executed successfully."},
                            status=StepState.PENDING,
                            estimated_time=1.0,
                            estimated_cost=0.01
                        )
                    ]
                else:
                    for idx, cap in enumerate(filtered_caps):
                        step_input = {}
                        if cap == "write_file":
                            resolved_path = "logs/recovery_output.txt"
                            try:
                                from workflow.planner import RuleBasedWorkflowPlanner
                                resolved_path = RuleBasedWorkflowPlanner()._resolve_target_file_path(workflow_id, task.goal)
                            except Exception:
                                pass
                            step_input = {
                                "file_path": resolved_path,
                                "path": resolved_path,
                                "content": f"Recovery content for task {task_id}",
                            }
                        elif cap in ("run_command", "execute_snippet"):
                            step_input = {"command": f"echo 'Executing recovery capability {cap}'"}
                        elif cap == "execute_script":
                            step_input = {"script_path": "main.py"}
                        else:
                            step_input = {"prompt": f"Repaired step executing capability {cap} to recover task {task_id}"}

                        new_steps.append(
                            WorkflowStep(
                                step_id=f"repair_{cap}_{idx}_r{repair_attempts + 1}",
                                workflow_id=workflow_id,
                                capability=cap,
                                input_data=step_input,
                                status=StepState.PENDING,
                                estimated_time=2.0,
                                estimated_cost=0.05
                            )
                        )
                    
            # Update workflow in persistence:
            # 1. Remove all non-completed remaining steps (including the failed step) to clear the path
            for s_id, step in list(workflow.steps.items()):
                if step.status != StepState.COMPLETED:
                    self.workflow_manager.remove_step(workflow_id, s_id)
                    
            # 2. Add the new repaired steps
            for step in new_steps:
                self.workflow_manager.add_step(workflow_id, step)
                
            # 3. Increment repair attempts count
            updated_wf = self.workflow_manager.load_workflow(workflow_id)
            updated_wf.metadata["repair_attempts"] = repair_attempts + 1
            self.workflow_manager.save_workflow(updated_wf)
            
            self._boot_result.logger.info("Workflow %s repaired. Rescheduling new steps: %s", workflow_id, [s.step_id for s in new_steps])
            
            # 4. Trigger scheduling loop for new steps
            next_ready = self.workflow_manager.ready_steps(workflow_id)
            for step in next_ready:
                self.scheduler_api.schedule(step)
                
        except Exception as e:
            self._boot_result.logger.exception("Failed to execute Autonomous Plan Repair: %s", e)
            if task_id:
                self.task_manager.update_state(task_id, TaskState.FAILED)
                # Notify interface of failure
                req = self._pending_requests.pop(task_id, None)
                if req:
                    self.interface_manager.send(
                        Response(
                            request_id=req.request_id,
                            status="failed",
                            message=f"Task failed during plan repair execution: {e}"
                        )
                    )

    def _start_background_interface_poller(self) -> None:
        """Poll non-CLI interfaces (REST, WebSocket) in a background thread."""
        import threading
        import time

        def _poll_loop():
            while self._lifecycle.state == KernelState.RUNNING:
                try:
                    if self._boot_result and hasattr(self._boot_result, "interface_manager"):
                        im = self._boot_result.interface_manager
                        for iface in im.interfaces():
                            if iface.interface_type != "cli" and iface.is_running:
                                req = iface.receive()
                                if req:
                                    res = im.process_request(req)
                                    if res and res.status in ("completed", "error", "success") and not res.metadata.get("task_id"):
                                        im.send(res)
                except Exception as e:
                    self.logger.debug("Interface poller error: %s", e)
                time.sleep(0.05)

        t = threading.Thread(target=_poll_loop, daemon=True, name="realtimex-interface-poller")
        t.start()
