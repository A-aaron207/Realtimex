"""
Reasoning pipeline implementation for the Realtimex Cognitive Engine.
"""

from __future__ import annotations

import logging
from typing import Any

from cognitive.context import ContextBuilder
from cognitive.exceptions import ValidationError, ReasoningError
from cognitive.reasoning import CognitiveRequest, CognitiveResponse, ReasoningProvider
from cognitive.validator import CognitiveValidator
from events.event import Event, EventPriority
from events.event_types import CognitiveEventType


class ReasoningPipeline:
    """
    Executes the standard Realtimex reasoning flow:
    Context Collection -> Reasoning -> Validation -> Decision -> Confidence Score -> Response
    """

    def __init__(
        self,
        provider: ReasoningProvider,
        context_builder: ContextBuilder,
        validator: CognitiveValidator,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize the ReasoningPipeline.

        Args:
            provider: Concrete reasoning provider (LLM wrapper or rule-based mock).
            context_builder: The builder to gather context parameters.
            validator: The validator to inspect decisions.
            event_bus: The kernel EventBus to emit cognitive states.
            logger: The logger to log events.
        """
        self.provider = provider
        self.context_builder = context_builder
        self.validator = validator
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.cognitive")

    def execute(self, request: CognitiveRequest, decision_type: str) -> CognitiveResponse:
        """
        Execute the pipeline for a cognitive request.

        Args:
            request: The request parameters.
            decision_type: The type of decision category.

        Returns:
            The validated CognitiveResponse.

        Raises:
            ValidationError: If the recommendation fails validation.
            ReasoningError: If the provider fails or returns invalid results.
        """
        self.logger.info(
            "Executing reasoning pipeline for Task %s, Decision type: %s",
            request.task_id,
            decision_type,
        )

        # 1. Emit ReasoningStarted event
        self._emit_event(
            name=CognitiveEventType.REASONING_STARTED,
            task_id=request.task_id,
            payload={
                "task_id": request.task_id,
                "workflow_id": request.workflow_id,
                "decision_type": decision_type,
                "objective": request.objective,
            },
        )

        # 2. Context Collection
        context = self.context_builder.build_context(
            task_id=request.task_id,
            workflow_id=request.workflow_id,
            additional_context=request.current_context,
        )

        # Merge request-level constraints and capabilities into context for downstream usage
        if request.constraints:
            context["constraints"] = request.constraints
        if request.available_capabilities:
            context["available_capabilities"] = request.available_capabilities

        # 3. Reasoning
        try:
            raw_outcome = self.provider.reason(request, context, decision_type)
        except Exception as e:
            self.logger.error("Reasoning provider raised an exception: %s", e)
            raise ReasoningError(f"Reasoning provider failed: {e}") from e

        # Ensure raw outcome contains the required fields
        required_keys = {"recommendation", "confidence", "reasoning_summary"}
        if not all(key in raw_outcome for key in required_keys):
            missing = required_keys - set(raw_outcome.keys())
            raise ReasoningError(
                f"Reasoning provider returned incomplete response. Missing fields: {missing}"
            )

        recommendation = raw_outcome["recommendation"]
        confidence = raw_outcome["confidence"]
        reasoning_summary = raw_outcome["reasoning_summary"]
        risks = raw_outcome.get("risks", [])
        suggested_actions = raw_outcome.get("suggested_actions", [])
        metadata = raw_outcome.get("metadata", {})

        # 4. Validation
        try:
            self.validator.validate(recommendation, decision_type, context)
        except ValidationError as e:
            self.logger.warning(
                "Validation failed for reasoning request (Task %s, Decision %s): %s",
                request.task_id,
                decision_type,
                e,
            )
            # Emit ValidationFailed event
            self._emit_event(
                name=CognitiveEventType.VALIDATION_FAILED,
                task_id=request.task_id,
                payload={
                    "task_id": request.task_id,
                    "workflow_id": request.workflow_id,
                    "decision_type": decision_type,
                    "reason": str(e),
                },
            )
            raise

        # 5. Build Response (Decision + Confidence Score)
        response = CognitiveResponse(
            recommendation=recommendation,
            confidence=confidence,
            reasoning_summary=reasoning_summary,
            risks=risks,
            suggested_actions=suggested_actions,
            metadata=metadata,
        )

        # 6. Emit DecisionGenerated event
        self._emit_event(
            name=CognitiveEventType.DECISION_GENERATED,
            task_id=request.task_id,
            payload={
                "task_id": request.task_id,
                "workflow_id": request.workflow_id,
                "decision_type": decision_type,
                "confidence": confidence,
                "recommendation": recommendation,
                "risks": risks,
            },
        )

        # 7. Emit ReasoningCompleted event
        self._emit_event(
            name=CognitiveEventType.REASONING_COMPLETED,
            task_id=request.task_id,
            payload={
                "task_id": request.task_id,
                "workflow_id": request.workflow_id,
                "decision_type": decision_type,
            },
        )

        return response

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        """Helper to emit event to EventBus if present."""
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="cognitive.pipeline",
                        task_id=task_id,
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Failed to emit event %s: %s", name, e)
