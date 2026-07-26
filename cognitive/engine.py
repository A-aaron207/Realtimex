"""
Cognitive Engine core interface for the Realtimex kernel.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from cognitive.analyzer import CognitiveAnalyzer
from cognitive.cache import CognitiveCache
from cognitive.context import ContextBuilder
from cognitive.exceptions import CognitiveError
from cognitive.planner import CognitivePlanner
from cognitive.pipeline import ReasoningPipeline
from cognitive.reasoning import CognitiveRequest, CognitiveResponse, ReasoningProvider, MockReasoningProvider
from cognitive.validator import CognitiveValidator
from events.event import Event, EventPriority
from events.event_types import CognitiveEventType


class CognitiveEngine:
    """
    The reasoning and decision assistance layer of the Realtimex kernel.
    Stateless, thread-safe, event-driven, and model provider-agnostic.
    """

    def __init__(
        self,
        reasoning_provider: ReasoningProvider | None = None,
        task_manager: Any = None,
        workflow_manager: Any = None,
        capability_registry: Any = None,
        event_manager: Any = None,
        loaded_modules_provider: Callable[[], list[Any]] | None = None,
        config: dict[str, Any] | None = None,
        cache_ttl: float = 300.0,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize the CognitiveEngine.

        Args:
            reasoning_provider: Provider for raw reasoning execution. Defaults to MockReasoningProvider.
            task_manager: System task manager.
            workflow_manager: System workflow manager.
            capability_registry: System capability registry.
            event_manager: System event manager/history.
            loaded_modules_provider: Provider to fetch loaded modules list.
            config: Kernel configurations.
            cache_ttl: Cache duration (TTL) in seconds.
            logger: Standard logger.
        """
        self._logger = logger or logging.getLogger("realtimex.cognitive")
        
        # Core sub-components
        self.provider = reasoning_provider or MockReasoningProvider()
        self.context_builder = ContextBuilder(
            task_manager=task_manager,
            workflow_manager=workflow_manager,
            capability_registry=capability_registry,
            event_manager=event_manager,
            loaded_modules_provider=loaded_modules_provider,
            config=config,
        )
        self.validator = CognitiveValidator()
        self.cache = CognitiveCache(default_ttl=cache_ttl)
        self.event_bus = getattr(event_manager, "event_bus", None) if event_manager is not None else None

        self.pipeline = ReasoningPipeline(
            provider=self.provider,
            context_builder=self.context_builder,
            validator=self.validator,
            event_bus=self.event_bus,
            logger=self._logger,
        )

        # Helper interfaces
        self.planner = CognitivePlanner(engine=self)
        self.analyzer = CognitiveAnalyzer(engine=self)

    # --- Public API ---

    def reason(self, request: CognitiveRequest, decision_type: str) -> CognitiveResponse:
        """
        Execute general reasoning pipeline with caching support.

        Args:
            request: Structured reasoning request parameters.
            decision_type: The category of decision being processed.

        Returns:
            The validated CognitiveResponse.
        """
        # Check cache
        cached_response = self.cache.get(request, decision_type)
        if cached_response is not None:
            self._logger.debug(
                "Cache hit for reasoning request (Task %s, Decision %s)",
                request.task_id,
                decision_type,
            )
            return cached_response

        # Execute reasoning pipeline
        response = self.pipeline.execute(request, decision_type)

        # Save to cache
        self.cache.set(request, decision_type, response)
        return response

    def plan(
        self,
        task_id: str,
        objective: str,
        constraints: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Formulate a step-by-step workflow plan for a task objective.
        """
        return self.planner.plan(
            task_id=task_id,
            objective=objective,
            constraints=constraints,
            additional_context=additional_context,
        )

    def analyze(
        self,
        task_id: str,
        objective: str,
        analysis_type: str,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Run specialized analytics (e.g. Risk Analysis, Permission Review).

        Supported analysis_types:
            - Risk Analysis
            - Permission Review
            - Conflict Resolution
            - Capability Selection
            - Recovery Recommendation
        """
        analysis_type_lower = analysis_type.lower()
        if "risk" in analysis_type_lower:
            constraints = []
            if additional_context and "constraints" in additional_context:
                constraints = additional_context["constraints"]
            return self.analyzer.analyze_risks(
                task_id=task_id,
                objective=objective,
                constraints=constraints,
                additional_context=additional_context,
            )
        elif "permission" in analysis_type_lower:
            req_perms = []
            if additional_context and "required_permissions" in additional_context:
                req_perms = additional_context["required_permissions"]
            return self.analyzer.review_permissions(
                task_id=task_id,
                objective=objective,
                required_permissions=req_perms,
                additional_context=additional_context,
            )
        elif "conflict" in analysis_type_lower:
            workflow_id = None
            if additional_context and "workflow_id" in additional_context:
                workflow_id = additional_context["workflow_id"]
            return self.analyzer.resolve_conflicts(
                task_id=task_id,
                objective=objective,
                workflow_id=workflow_id,
                additional_context=additional_context,
            )
        elif "capability" in analysis_type_lower:
            caps = []
            if additional_context and "available_capabilities" in additional_context:
                caps = additional_context["available_capabilities"]
            return self.analyzer.select_capability(
                task_id=task_id,
                objective=objective,
                available_capabilities=caps,
                additional_context=additional_context,
            )
        elif "recovery" in analysis_type_lower:
            reason = "unknown"
            if additional_context:
                # Support flat key: {"failure_reason": "..."} 
                if "failure_reason" in additional_context:
                    reason = additional_context["failure_reason"]
                # Support nested path: {"task": {"metadata": {"failure_reason": "..."}}}
                elif (
                    isinstance(additional_context.get("task"), dict)
                    and isinstance(additional_context["task"].get("metadata"), dict)
                    and "failure_reason" in additional_context["task"]["metadata"]
                ):
                    reason = additional_context["task"]["metadata"]["failure_reason"]
            return self.analyzer.recommend_recovery(
                task_id=task_id,
                objective=objective,
                failure_reason=reason,
                additional_context=additional_context,
            )
        else:
            # Fallback to general reasoning
            request = CognitiveRequest(
                task_id=task_id,
                objective=objective,
                current_context=additional_context or {},
            )
            return self.reason(request, decision_type=analysis_type)

    def validate(self, recommendation: Any, decision_type: str, context: dict[str, Any]) -> bool:
        """
        Validate a recommendation against business and capability checks.
        """
        return self.validator.validate(recommendation, decision_type, context)

    def recommend(
        self,
        task_id: str,
        decision_type: str,
        objective: str,
        additional_context: dict[str, Any] | None = None,
    ) -> CognitiveResponse:
        """
        Generate structured advice/recommendations.
        """
        request = CognitiveRequest(
            task_id=task_id,
            objective=objective,
            current_context=additional_context or {},
        )
        return self.reason(request, decision_type)

    def build_context(
        self,
        task_id: str,
        workflow_id: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Gather context for external or downstream consumers.
        """
        return self.context_builder.build_context(task_id, workflow_id, additional_context)

    # --- Kernel Action Logging ---

    def accept_recommendation(
        self,
        task_id: str,
        recommendation: Any,
        decision_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record that a proposed recommendation was approved by the Kernel.
        """
        self._emit_event(
            name=CognitiveEventType.RECOMMENDATION_ACCEPTED,
            task_id=task_id,
            payload={
                "task_id": task_id,
                "decision_type": decision_type,
                "recommendation": recommendation,
                "metadata": metadata or {},
            },
        )

    def reject_recommendation(
        self,
        task_id: str,
        recommendation: Any,
        decision_type: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Record that a proposed recommendation was rejected by the Kernel.
        """
        self._emit_event(
            name=CognitiveEventType.RECOMMENDATION_REJECTED,
            task_id=task_id,
            payload={
                "task_id": task_id,
                "decision_type": decision_type,
                "recommendation": recommendation,
                "reason": reason,
                "metadata": metadata or {},
            },
        )

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        """Internal helper to publish a transaction event."""
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="cognitive.engine",
                        task_id=task_id,
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as e:
                self._logger.warning("Failed to emit cognitive kernel event %s: %s", name, e)
