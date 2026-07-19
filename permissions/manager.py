"""
Permission Manager implementation orchestrating security controls in Realtimex.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from events.event import Event, EventPriority
from events.event_types import PermissionEventType
from permissions.approvals import ApprovalPipeline
from permissions.cache import PermissionCache
from permissions.decision import PermissionDecision
from permissions.exceptions import PermissionValidationError, PermissionDeniedError
from permissions.persistence import PermissionPersistence
from permissions.policies import PermissionPolicy, PolicyEvaluator
from permissions.registry import PermissionRegistry, SecurityManifest
from permissions.request import PermissionRequest
from permissions.rules import RuleEngine
from permissions.trust import TrustManager


class PermissionManager:
    """
    Core security gateway of Realtimex. Validates actions before worker execution
    and coordinates rules, policies, trust scopes, caches, and user overrides.
    """

    def __init__(
        self,
        persistence: PermissionPersistence,
        event_bus: Any = None,
        policy: PermissionPolicy | None = None,
        cognitive_engine: Any = None,
        user_reviewer: Callable[[PermissionRequest], bool] | None = None,
        rule_engine_args: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.persistence = persistence
        self.event_bus = event_bus
        self.cognitive_engine = cognitive_engine
        self.user_reviewer = user_reviewer
        self.logger = logger or logging.getLogger("realtimex.permissions")

        # Subsystems
        self.registry = PermissionRegistry()
        self.cache_store = PermissionCache()
        self.trust_manager = TrustManager()
        
        self.policy = policy or PermissionPolicy()
        self.policy_evaluator = PolicyEvaluator(self.policy)
        
        rule_args = rule_engine_args or {}
        self.rule_engine = RuleEngine(**rule_args)

        self.pipeline = ApprovalPipeline(
            rule_engine=self.rule_engine,
            policy_evaluator=self.policy_evaluator,
            trust_manager=self.trust_manager,
            cognitive_engine=self.cognitive_engine,
            event_bus=self.event_bus,
            user_reviewer=self.user_reviewer,
            logger=self.logger,
        )

        # Pending manual review tracker (optional, for approve/deny by request_id)
        self._pending_requests: dict[str, PermissionRequest] = {}

        # Bootstrap trust levels and approvals
        self._bootstrap_states()

    def _bootstrap_states(self) -> None:
        """Load persisted trust ratings and persistent user decisions from disk."""
        # 1. Load Trust
        try:
            scores = self.persistence.load_trust_scores()
            for entity_id, score in scores.items():
                self.trust_manager.set_trust_score(entity_id, score)
        except Exception as e:
            self.logger.warning("Failed to bootstrap trust ratings: %s", e)

        # 2. Load Persistent Approvals
        try:
            approvals = self.persistence.load_persistent_approvals()
            for item in approvals:
                # Reconstruct request and decision
                req = PermissionRequest.from_dict(item["request"])
                dec = PermissionDecision.from_dict(item["decision"])
                
                # Verify not expired
                if dec.expiration is None or datetime.now(timezone.utc) < dec.expiration:
                    self.cache_store.set(req, dec)
        except Exception as e:
            self.logger.warning("Failed to bootstrap persistent approvals: %s", e)

    def _sync_persistent_state(self) -> None:
        """Synchronize active state changes back to persistent storage."""
        # 1. Save Trust
        try:
            scores = {}
            # TrustManager score dictionary is internal; we retrieve for registered keys
            # For simplicity, we can fetch all entities tracked
            with self.trust_manager._lock:
                scores = self.trust_manager._trust_scores.copy()
            self.persistence.save_trust_scores(scores)
        except Exception as e:
            self.logger.error("Failed to sync trust ratings: %s", e)

        # 2. Save Persistent Cache Approvals
        try:
            active_cache = self.cache_store.list_all()
            persistent_approvals = []
            
            # Since CacheEntry has the request details, we match the key.
            # In a production system, we'd persist the complete request/decision pair.
            # We can reconstruct or track them in the manager. Let's record them.
            # To preserve correct pairs, let's filter list_all for persistent types
            for key, dec in active_cache:
                if dec.cache_policy == "persistent":
                    # Search matching metadata or just construct dummy request info
                    # For a clean implementation, we can maintain a registry of persistent requests
                    req_data = dec.metadata.get("original_request")
                    if req_data:
                        persistent_approvals.append({
                            "request": req_data,
                            "decision": dec.to_dict(),
                        })
                        
            self.persistence.save_persistent_approvals(persistent_approvals)
        except Exception as e:
            self.logger.error("Failed to sync persistent approvals: %s", e)

    # --- Public API ---

    def request(
        self,
        task_id: str,
        worker_id: str,
        action: str,
        target: str,
        requested_capability: str,
        risk_level: str = "low",
        workflow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PermissionDecision:
        """
        Request permission to perform a privileged action.
        Checks cache first, then executes the evaluation pipeline.
        """
        req_meta = metadata or {}
        req = PermissionRequest(
            task_id=task_id,
            worker_id=worker_id,
            action=action,
            target=target,
            requested_capability=requested_capability,
            risk_level=risk_level,
            workflow_id=workflow_id,
            metadata=req_meta,
        )

        # 1. Pre-declaration Sandboxing manifest check
        # If the worker has a registered manifest, check if action is pre-declared
        manifest = self.registry.get_manifest(worker_id)
        if manifest is not None:
            if not self.registry.is_declared(worker_id, action, target):
                decision = PermissionDecision(
                    approved=False,
                    reason=(
                        f"Sandboxing violation: action '{action}' on target '{target}' "
                        f"is not pre-declared in worker's manifest."
                    ),
                    reviewer="policy_evaluator",
                )
                self._emit_event(PermissionEventType.PERMISSION_DENIED, task_id, decision.to_dict())
                return decision

        # 2. Check Permission Cache
        cached_decision = self.cache_store.get(req)
        if cached_decision is not None:
            self._emit_event(PermissionEventType.PERMISSION_CACHED, task_id, {
                "request_id": req.request_id,
                "cached": True,
                "approved": cached_decision.approved,
            })
            return cached_decision

        # 3. Track as pending request in case user review callback is not registered
        self._pending_requests[req.request_id] = req

        # 4. Evaluate Pipeline
        decision = self.pipeline.evaluate(req)

        # Remove from pending once decided
        if req.request_id in self._pending_requests:
            del self._pending_requests[req.request_id]

        # 5. Cache evaluated approvals based on policy settings
        if decision.approved and decision.cache_policy != "once":
            # If persistent, append original request to metadata so we can recover it on next startup
            if decision.cache_policy == "persistent":
                decision.metadata["original_request"] = req.to_dict()
                
            self.cache_store.set(req, decision)
            self._emit_event(PermissionEventType.PERMISSION_CACHED, task_id, {
                "request_id": req.request_id,
                "policy": decision.cache_policy,
            })
            
            # Sync back to disk
            if decision.cache_policy == "persistent":
                self._sync_persistent_state()

        return decision

    def approve(self, request_id: str) -> None:
        """
        Manually approve a pending request out-of-band.
        """
        req = self._pending_requests.get(request_id)
        if req is None:
            raise PermissionValidationError(f"Pending request with ID '{request_id}' not found.")

        # Reconstruct approval decision override
        decision = PermissionDecision(
            approved=True,
            reason="Manually approved by administrative override.",
            reviewer="user",
            cache_policy="session",
            expiration=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

        # Cache it and clear pending
        self.cache_store.set(req, decision)
        del self._pending_requests[request_id]

        self._emit_event(PermissionEventType.PERMISSION_APPROVED, req.task_id, decision.to_dict())

    def deny(self, request_id: str) -> None:
        """
        Manually deny a pending request out-of-band.
        """
        req = self._pending_requests.get(request_id)
        if req is None:
            raise PermissionValidationError(f"Pending request with ID '{request_id}' not found.")

        decision = PermissionDecision(
            approved=False,
            reason="Manually denied by administrative override.",
            reviewer="user",
        )

        del self._pending_requests[request_id]
        self._emit_event(PermissionEventType.PERMISSION_DENIED, req.task_id, decision.to_dict())

    def revoke(self, worker_id: str, action: str, target: str) -> None:
        """
        Invalidate a cached permission matching target attributes.
        """
        key = self.cache_store._generate_key(worker_id, action, target)
        with self.cache_store._lock:
            if key in self.cache_store._cache:
                del self.cache_store._cache[key]
                self._emit_event(
                    name=PermissionEventType.PERMISSION_EXPIRED,
                    task_id="",
                    payload={"worker_id": worker_id, "action": action, "target": target},
                )
        self._sync_persistent_state()

    def cache(self, request: PermissionRequest, decision: PermissionDecision) -> None:
        """
        Manually insert an evaluated decision into the cache.
        """
        self.cache_store.set(request, decision)
        if decision.cache_policy == "persistent":
            decision.metadata["original_request"] = request.to_dict()
            self._sync_persistent_state()

    def clear_cache(self) -> None:
        """
        Clear all cached approvals.
        """
        self.cache_store.clear()
        self._sync_persistent_state()

    def list_permissions(self) -> list[tuple[str, PermissionDecision]]:
        """
        List all currently active cached approvals.
        """
        return self.cache_store.list_all()

    def set_trust_score(self, entity_id: str, score: float) -> None:
        """Set the trust score of an entity and persist change to disk."""
        self.trust_manager.set_trust_score(entity_id, score)
        self._sync_persistent_state()

    # --- Internal Event Emitting ---

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="permissions.manager",
                        task_id=task_id,
                        priority=EventPriority.HIGH,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Event dispatch failed for %s: %s", name, e)
