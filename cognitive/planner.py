"""
Planner 2.0 component for the Realtimex Cognitive Engine.
Incorporates GoalGraph decomposition, ActionValidator pre-execution checks,
and auto-replanning.
"""

from __future__ import annotations

from typing import Any

from cognitive.action_validator import ActionValidator, ValidationResult
from cognitive.goal_graph import GoalGraph, GoalNode
from cognitive.reasoning import CognitiveRequest, CognitiveResponse
from cognitive.tool_intelligence import ToolCandidate, ToolIntelligenceEngine


class CognitivePlanner:
    """
    Planner 2.0 kernel helper.
    Formulates GoalGraph dependency models, executes pre-action validation,
    ranks tool candidates via ToolIntelligenceEngine, and supports auto-replanning.
    """

    def __init__(
        self,
        engine: Any,
        min_confidence_threshold: float = 0.70,
        tool_intelligence: ToolIntelligenceEngine | None = None,
    ) -> None:
        """
        Initialize CognitivePlanner.

        Args:
            engine: The CognitiveEngine instance.
            min_confidence_threshold: Minimum confidence score required to execute.
            tool_intelligence: ToolIntelligenceEngine instance for tool ranking.
        """
        self._engine = engine
        self.action_validator = ActionValidator(min_confidence_threshold=min_confidence_threshold)
        self.tool_intelligence = tool_intelligence or ToolIntelligenceEngine()

    def plan(
        self,
        task_id: str,
        objective: str,
        constraints: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Formulate a step-by-step workflow plan for a task objective.
        Uses GoalGraph decomposition to structure sub-goals.
        """
        ctx = additional_context or {}
        goal_graph = GoalGraph.decompose_objective(objective)
        ctx["goal_graph"] = goal_graph.to_dict()

        request = CognitiveRequest(
            task_id=task_id,
            objective=objective,
            constraints=constraints or [],
            current_context=ctx,
        )
        return self._engine.reason(request, decision_type="Workflow Planning")

    def plan_with_goal_graph(
        self,
        task_id: str,
        objective: str,
        constraints: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> tuple[CognitiveResponse, GoalGraph]:
        """
        Formulate a plan and return both the CognitiveResponse and the GoalGraph instance.
        """
        ctx = dict(additional_context or {})
        goal_graph = GoalGraph.decompose_objective(objective)
        ctx["goal_graph"] = goal_graph.to_dict()

        request = CognitiveRequest(
            task_id=task_id,
            objective=objective,
            constraints=constraints or [],
            current_context=ctx,
        )
        response = self._engine.reason(request, decision_type="Workflow Planning")
        return response, goal_graph

    def validate_action(
        self,
        step: dict[str, Any],
        context: dict[str, Any] | None = None,
        available_capabilities: list[str] | None = None,
        granted_permissions: set[str] | None = None,
        confidence_score: float = 1.0,
    ) -> ValidationResult:
        """
        Validate an action step immediately prior to execution using ActionValidator.
        """
        return self.action_validator.validate_action(
            step=step,
            context=context,
            available_capabilities=available_capabilities,
            granted_permissions=granted_permissions,
            confidence_score=confidence_score,
        )

    def replan_on_failure(
        self,
        task_id: str,
        objective: str,
        failed_step: dict[str, Any],
        failure_reason: str,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Automatically replan when an action step fails pre-execution validation or runtime.
        """
        ctx = dict(additional_context or {})
        ctx["failed_step"] = failed_step
        ctx["failure_reason"] = failure_reason
        ctx["replan_triggered"] = True

        request = CognitiveRequest(
            task_id=task_id,
            objective=f"Replan task objective '{objective}' after failure: {failure_reason}",
            constraints=["avoid_failed_step_configuration"],
            current_context=ctx,
        )
        return self._engine.reason(request, decision_type="Workflow Planning")

    def rank_tools(
        self,
        intent: str,
        candidates: list[ToolCandidate],
        latency_budget_ms: float = 1000.0,
    ) -> list[ToolCandidate]:
        """
        Rank candidate tools for a target task intent or step capability request.
        """
        return self.tool_intelligence.rank_candidates(intent, candidates, latency_budget_ms)

    def select_best_tool(
        self,
        intent: str,
        candidates: list[ToolCandidate],
        latency_budget_ms: float = 1000.0,
    ) -> ToolCandidate | None:
        """
        Select the highest ranked tool candidate.
        """
        return self.tool_intelligence.select_best_tool(intent, candidates, latency_budget_ms)

    def optimize_workflow(
        self,
        task_id: str,
        objective: str,
        workflow_id: str,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Suggest optimization rules or order improvements for an existing workflow.
        """
        request = CognitiveRequest(
            task_id=task_id,
            objective=objective,
            workflow_id=workflow_id,
            current_context=additional_context or {},
        )
        return self._engine.reason(request, decision_type="Workflow Planning")
