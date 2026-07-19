"""
Planner component for the Realtimex Cognitive Engine.
"""

from __future__ import annotations

from typing import Any

from cognitive.reasoning import CognitiveRequest, CognitiveResponse


class CognitivePlanner:
    """
    Subsystem helper that assists the workflow engine with workflow generation,
    step ordering, and optimization.
    """

    def __init__(self, engine: Any) -> None:
        """
        Initialize the CognitivePlanner.

        Args:
            engine: The CognitiveEngine instance.
        """
        self._engine = engine

    def plan(
        self,
        task_id: str,
        objective: str,
        constraints: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Formulate a step-by-step workflow plan for a task objective.

        Args:
            task_id: The ID of the task to plan for.
            objective: The goal of the task.
            constraints: List of task/execution constraints.
            additional_context: Explicit context passed by caller.

        Returns:
            CognitiveResponse containing the step plan.
        """
        request = CognitiveRequest(
            task_id=task_id,
            objective=objective,
            constraints=constraints or [],
            current_context=additional_context or {},
        )
        return self._engine.reason(request, decision_type="Workflow Planning")

    def optimize_workflow(
        self,
        task_id: str,
        objective: str,
        workflow_id: str,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Suggest optimization rules or order improvements for an existing workflow.

        Args:
            task_id: The ID of the task.
            objective: The task objective.
            workflow_id: The ID of the workflow to optimize.
            additional_context: Explicit context passed by caller.

        Returns:
            CognitiveResponse containing optimization recommendations.
        """
        request = CognitiveRequest(
            task_id=task_id,
            objective=objective,
            workflow_id=workflow_id,
            current_context=additional_context or {},
        )
        return self._engine.reason(request, decision_type="Workflow Planning")
