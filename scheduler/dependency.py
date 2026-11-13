"""
Dependency Resolver verifying all execution pre-conditions for workflow steps.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tasks.states import TaskState
from workflow.step import StepState

if TYPE_CHECKING:
    from capabilities.registry import CapabilityRegistry
    from tasks.manager import TaskManager
    from workflow.manager import WorkflowManager
    from workflow.step import WorkflowStep
    from workers.manager import WorkerManager


class DependencyResolver:
    """
    Evaluates step dependencies, parent task status, capability registries,
    and pool availability before execution dispatching.
    """

    def __init__(
        self,
        task_manager: TaskManager,
        workflow_manager: WorkflowManager,
        capability_registry: CapabilityRegistry,
        worker_manager: WorkerManager,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize Dependency Resolver.

        Args:
            task_manager: TaskManager.
            workflow_manager: WorkflowManager.
            capability_registry: CapabilityRegistry.
            worker_manager: WorkerManager.
            logger: Logger.
        """
        self._task_manager = task_manager
        self._workflow_manager = workflow_manager
        self._capability_registry = capability_registry
        self._worker_manager = worker_manager
        self._logger = logger

    def can_dispatch(self, step: WorkflowStep) -> bool:
        """
        Verify if a step satisfies all constraints to be scheduled.

        Args:
            step: WorkflowStep to evaluate.

        Returns:
            True if ready, False otherwise.
        """
        # 1. Resolve parent task ID from workflow
        try:
            workflow = self._workflow_manager.load_workflow(step.workflow_id)
            task = self._task_manager.get_task(workflow.parent_task_id)
        except Exception as e:
            self._logger.debug("Failed to resolve task for step %s: %s", step.step_id, e)
            return False

        # 2. Check task state
        if task.state not in {TaskState.RUNNING, TaskState.RETRYING, TaskState.QUEUED}:
            self._logger.debug(
                "Cannot dispatch step %s: Parent task %s is in state %s",
                step.step_id,
                task.task_id,
                task.state.value,
            )
            return False

        # 3. Check step dependencies are completed or skipped
        for dep_id in step.dependencies:
            dep_step = workflow.steps.get(dep_id)
            if dep_step is None:
                self._logger.debug("Step %s depends on missing step %s", step.step_id, dep_id)
                return False
            if dep_step.status not in {StepState.COMPLETED, StepState.SKIPPED}:
                self._logger.debug(
                    "Cannot dispatch step %s: Dependency %s is in status %s",
                    step.step_id,
                    dep_id,
                    dep_step.status.value,
                )
                return False

        # 4. Check capability registered
        providers = self._capability_registry.providers(step.capability)
        if not providers:
            self._logger.debug("No capability providers registered for step %s capability '%s'", step.step_id, step.capability)
            return False

        # 5. Check worker availability via public WorkerManager API
        if not self._worker_manager.has_idle_worker(step.capability):
            self._logger.debug("No idle workers currently available for step %s capability '%s'", step.step_id, step.capability)
            return False

        return True
