"""
Approval Pipeline implementation executing permission request evaluations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from events.event import Event, EventPriority
from events.event_types import PermissionEventType
from permissions.decision import PermissionDecision
from permissions.request import PermissionRequest
from permissions.rules import RuleEngine
from permissions.policies import PolicyEvaluator
from permissions.trust import TrustManager
from cognitive.reasoning import CognitiveRequest


class ApprovalPipeline:
    """
    Executes the sequential evaluation stages of a permission request:
    Rule Engine -> Cognitive Analysis -> Policy Evaluation -> User Review -> Decision -> Cache.
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        policy_evaluator: PolicyEvaluator,
        trust_manager: TrustManager,
        cognitive_engine: Any = None,
        event_bus: Any = None,
        user_reviewer: Callable[[PermissionRequest], bool] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.rule_engine = rule_engine
        self.policy_evaluator = policy_evaluator
        self.trust_manager = trust_manager
        self.cognitive_engine = cognitive_engine
        self.event_bus = event_bus
        self.user_reviewer = user_reviewer
        self.logger = logger or logging.getLogger("realtimex.permissions.pipeline")

    def evaluate(self, request: PermissionRequest) -> PermissionDecision:
        """
        Evaluate a permission request through all sequence stages.
        """
        self._emit_event(PermissionEventType.PERMISSION_REQUESTED, request.task_id, request.to_dict())

        # Mutable metadata reference so stages can append flags (e.g. user review flags)
        metadata = request.metadata

        # --- Stage 1: Rule Engine ---
        rule_decision = self.rule_engine.evaluate(request)
        self._emit_event(PermissionEventType.RULE_EVALUATED, request.task_id, {
            "request_id": request.request_id,
            "evaluated": rule_decision is not None,
            "outcome": rule_decision.approved if rule_decision else None,
        })
        
        if rule_decision is not None:
            # Rule matched explicitly (e.g., Sudo check or Path restrictions)
            if not rule_decision.approved:
                self._emit_event(PermissionEventType.PERMISSION_DENIED, request.task_id, rule_decision.to_dict())
                return rule_decision
            # If approved by rule engine, we still feed through policy checks just in case!

        # --- Stage 2: Cognitive Analysis ---
        # Consult Cognitive Engine if registered to estimate security risk
        if self.cognitive_engine is not None:
            try:
                # We construct a CognitiveRequest mock risk analyzer decision
                cog_req = CognitiveRequest(
                    task_id=request.task_id,
                    objective=(
                        f"Risk analysis for action '{request.action}' targeted on target '{request.target}' "
                        f"requested by worker '{request.worker_id}'."
                    ),
                    constraints=[],
                    current_context={"risk_level": request.risk_level, "worker_id": request.worker_id},
                )
                cog_resp = self.cognitive_engine.reason(
                    cog_req,
                    decision_type="risk analysis",
                )
                
                # Check for high risk recommendation
                rec = cog_resp.recommendation
                risk_level = rec.get("risk_level", "low") if isinstance(rec, dict) else "low"
                if risk_level == "high" or risk_level == "critical":
                    metadata["user_confirmation_required"] = True
                    metadata["cognitive_warning"] = "Cognitive Engine identified high operational risk."
            except Exception as e:
                self.logger.warning("Cognitive Analysis bypassed due to evaluation failure: %s", e)

        # --- Stage 3: Policy Evaluation ---
        policy_decision = self.policy_evaluator.evaluate(request)
        self._emit_event(PermissionEventType.POLICY_MATCHED, request.task_id, {
            "request_id": request.request_id,
            "matched": policy_decision is not None,
            "outcome": policy_decision.approved if policy_decision else None,
        })

        if policy_decision is not None:
            if not policy_decision.approved:
                self._emit_event(PermissionEventType.PERMISSION_DENIED, request.task_id, policy_decision.to_dict())
                return policy_decision

        # --- Stage 4: User Review (if required) ---
        # User confirmation is required if:
        # - Policy Evaluator flagged it (e.g., sudo required user confirmation flag)
        # - Cognitive Engine flagged it (high risk)
        # - Request risk level is critical
        # - Trust level of requesting worker is below safety threshold (e.g. 0.3)
        trust_score = self.trust_manager.get_trust_score(request.worker_id)
        if (
            metadata.get("user_confirmation_required")
            or request.risk_level in ("critical", "high")
            or trust_score < 0.3
        ):
            if self.user_reviewer is not None:
                # Prompt user callback
                user_approved = self.user_reviewer(request)
                if not user_approved:
                    decision = PermissionDecision(
                        approved=False,
                        reason="Explicitly rejected by user review.",
                        reviewer="user",
                    )
                    self._emit_event(PermissionEventType.PERMISSION_DENIED, request.task_id, decision.to_dict())
                    return decision
                else:
                    # User approved! Mark cache policy as persistent/session based on request risk
                    cache_policy = "persistent" if request.risk_level == "low" else "session"
                    decision = PermissionDecision(
                        approved=True,
                        reason="Approved via interactive User Review override.",
                        reviewer="user",
                        cache_policy=cache_policy,
                        expiration=datetime.now(timezone.utc) + timedelta(minutes=15),
                    )
                    self._emit_event(PermissionEventType.PERMISSION_APPROVED, request.task_id, decision.to_dict())
                    return decision
            else:
                # Headless mode with required user review and no callback -> Secure Denial!
                decision = PermissionDecision(
                    approved=False,
                    reason="Action requires interactive User Review confirmation but no reviewer interface is registered.",
                    reviewer="policy_evaluator",
                )
                self._emit_event(PermissionEventType.PERMISSION_DENIED, request.task_id, decision.to_dict())
                return decision

        # --- Stage 5: Final Decision (Default Resolution) ---
        # If we got this far and wasn't denied, we default approve if trust is sufficient
        if trust_score >= 0.5:
            decision = PermissionDecision(
                approved=True,
                reason="Default approval based on rules check and sufficient entity trust rating.",
                reviewer="policy_evaluator",
                cache_policy="task",  # default cache for task duration
                expiration=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            self._emit_event(PermissionEventType.PERMISSION_APPROVED, request.task_id, decision.to_dict())
            return decision
        else:
            decision = PermissionDecision(
                approved=False,
                reason="Default denial: insufficient entity trust rating.",
                reviewer="policy_evaluator",
            )
            self._emit_event(PermissionEventType.PERMISSION_DENIED, request.task_id, decision.to_dict())
            return decision

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="permissions.pipeline",
                        task_id=task_id,
                        priority=EventPriority.HIGH,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Pipeline event dispatch failed for %s: %s", name, e)
