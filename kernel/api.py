"""
Public Kernel API.

Exposes the Kernel's control surface -- boot, shutdown, restart, and
status -- as a stable entry point for embedding applications (such as
main.py) and, eventually, external interfaces (CLI, HTTP, RPC).

This module deliberately contains no orchestration logic of its own;
it delegates entirely to `kernel.core.Kernel`, keeping the public
surface area decoupled from the internal implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from events.manager import EventManager
    from tasks.api import TaskAPI
    from tasks.manager import TaskManager
    from workflow.manager import WorkflowManager
    from capabilities.registry import CapabilityRegistry
    from workers.api import WorkerAPI
    from workers.manager import WorkerManager
    from scheduler.api import SchedulerAPI
    from scheduler.scheduler import Scheduler

from kernel.core import Kernel


class KernelAPI:
    """
    Thin public-facing wrapper around the Kernel core.

    Responsibilities:
        - Construct and hold a single Kernel instance.
        - Expose boot(), shutdown(), restart(), and status() as the
          only supported ways to control the Kernel from outside.

    Task execution, workflow orchestration, and worker management are
    explicitly not implemented here; they belong to future milestones.
    """

    def __init__(self, config_path: Path, log_directory: Path, modules_root: Path) -> None:
        """
        Initialize the Kernel API.

        Args:
            config_path: Path to the Kernel's configuration JSON file.
            log_directory: Directory in which log files should be written.
            modules_root: Directory under which module subdirectories live.
        """
        self._kernel = Kernel(config_path=config_path, log_directory=log_directory, modules_root=modules_root)

    def boot(self) -> None:
        """Boot the Kernel, running its full initialization sequence."""
        self._kernel.boot()

    def shutdown(self) -> None:
        """Shut down the Kernel cleanly."""
        self._kernel.shutdown()

    def restart(self) -> None:
        """Restart the Kernel (shutdown followed by boot)."""
        self._kernel.restart()

    def status(self) -> dict[str, object]:
        """
        Retrieve the Kernel's current status.

        Returns:
            A dictionary describing lifecycle state and, once booted,
            component summary information.
        """
        return self._kernel.status()

    def find_capability_provider(self, capability: str) -> str:
        """
        Ask the Kernel which module provides a given capability.

        Args:
            capability: The capability name to look up (e.g. "summarize_text").

        Returns:
            The module_id of the first registered provider.
        """
        return self._kernel.find_capability_provider(capability)

    def log_status(self) -> None:
        """Log the Kernel's current status through its own logger."""
        self._kernel.logger.info("Kernel status: %s", self._kernel.status())

    @property
    def event_manager(self) -> EventManager:
        """
        Access the Kernel's Event Manager.

        Returns:
            The EventManager instance managing the full event
            infrastructure (bus, history, persistence, replay).

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.event_manager

    @property
    def task_manager(self) -> TaskManager:
        """
        Access the Kernel's Task Manager.

        Returns:
            The TaskManager instance managing task lifecycle and state.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.task_manager

    @property
    def task_api(self) -> TaskAPI:
        """
        Access the Kernel's Task Search API.

        Returns:
            The TaskAPI instance for querying tasks.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.task_api

    @property
    def loaded_modules(self) -> list[LoadedModule]:
        """
        Access the list of successfully loaded modules.

        Returns:
            List of LoadedModule instances.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.loaded_modules

    @property
    def capability_registry(self) -> CapabilityRegistry:
        """
        Access the CapabilityRegistry.

        Returns:
            The CapabilityRegistry instance.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.capability_registry

    @property
    def workflow_manager(self) -> WorkflowManager:
        """
        Access the Kernel's Workflow Manager.

        Returns:
            The WorkflowManager instance.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.workflow_manager

    @property
    def workflow_api(self) -> WorkflowAPI:
        """
        Access the Kernel's Workflow API.

        Returns:
            The WorkflowAPI instance for managing workflows.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.workflow_api

    @property
    def worker_manager(self) -> WorkerManager:
        """
        Access the Kernel's Worker Manager.

        Returns:
            The WorkerManager instance managing pools and worker health.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.worker_manager

    @property
    def worker_api(self) -> WorkerAPI:
        """
        Access the Kernel's Worker API.

        Returns:
            The WorkerAPI instance for execution and monitoring.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.worker_api

    @property
    def scheduler(self) -> Scheduler:
        """
        Access the Kernel's Scheduler.

        Returns:
            The Scheduler instance managing step queues and allocations.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.scheduler

    @property
    def scheduler_api(self) -> SchedulerAPI:
        """
        Access the Kernel's Scheduler API.

        Returns:
            The SchedulerAPI instance for monitoring and control.

        Raises:
            RuntimeError: If the Kernel has not booted yet.
        """
        return self._kernel.scheduler_api

    @property
    def config_manager(self) -> Any:
        return self._kernel.config_manager

    @property
    def dependency_container(self) -> Any:
        return self._kernel.dependency_container

    @property
    def service_registry(self) -> Any:
        return self._kernel.service_registry


    @property
    def observability(self) -> Any:
        return self._kernel.observability

    @property
    def policy_manager(self) -> Any:
        return self._kernel.policy_manager

    @property
    def security_manager(self) -> Any:
        return self._kernel.security_manager

    @property
    def interface_manager(self) -> Any:
        return self._kernel.interface_manager

    @property
    def memory_manager(self) -> Any:
        return self._kernel.memory_manager

    @property
    def model_gateway(self) -> Any:
        return self._kernel.model_gateway

    @property
    def cognitive_engine(self) -> Any:
        return self._kernel.cognitive_engine

    @property
    def permission_manager(self) -> Any:
        return self._kernel.permission_manager


