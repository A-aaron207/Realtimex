"""
Workflow API — public lookup and query API for the Realtimex Workflow Engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workflow.manager import WorkflowManager
    from workflow.step import WorkflowStep
    from workflow.workflow import Workflow


class WorkflowAPI:
    """
    Public API exposing operations to create, update, validate, and track workflows.
    """

    def __init__(self, manager: WorkflowManager) -> None:
        """
        Initialize Workflow API.

        Args:
            manager: The WorkflowManager instance.
        """
        self._manager = manager

    def create_workflow(self, parent_task_id: str, goal: str) -> Workflow:
        """
        Create a new workflow based on user goal.
        """
        return self._manager.create_workflow(parent_task_id, goal)

    def load_workflow(self, workflow_id: str) -> Workflow:
        """
        Load an existing workflow.
        """
        return self._manager.load_workflow(workflow_id)

    def save_workflow(self, workflow: Workflow) -> None:
        """
        Save a workflow's state.
        """
        self._manager.save_workflow(workflow)

    def validate(self, workflow_id: str) -> bool:
        """
        Validate workflow graph structure.
        """
        return self._manager.validate(workflow_id)

    def add_step(self, workflow_id: str, step: WorkflowStep) -> Workflow:
        """
        Add a step to the workflow.
        """
        return self._manager.add_step(workflow_id, step)

    def remove_step(self, workflow_id: str, step_id: str) -> Workflow:
        """
        Remove a step from the workflow.
        """
        return self._manager.remove_step(workflow_id, step_id)

    def ready_steps(self, workflow_id: str) -> list[WorkflowStep]:
        """
        Transition pending steps to READY if their dependencies are completed.
        """
        return self._manager.ready_steps(workflow_id)

    def workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """
        Get workflow metrics and current status.

        Returns:
            Dictionary containing parent task, status, total nodes,
            dependencies count, and number of ready steps.
        """
        wf = self._manager.load_workflow(workflow_id)
        
        # Calculate total dependency edges
        dep_count = sum(len(s.dependencies) for s in wf.steps.values())
        
        # Count steps in READY state
        ready_count = sum(1 for s in wf.steps.values() if s.status == "READY")

        return {
            "workflow_id": workflow_id,
            "parent_task_id": wf.parent_task_id,
            "status": wf.status.value,
            "nodes": len(wf.steps),
            "dependencies": dep_count,
            "ready_steps": ready_count,
            "version": wf.version,
        }
