"""
Policy Manager for Realtimex.

The central orchestrator for evaluating, loading, registering, and validating policies.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional, Tuple

from policy.registry import PolicyRegistry
from policy.evaluator import PolicyEvaluator
from policy.compiler import RuleCompiler
from policy.validator import PolicyValidator
from policy.loader import PolicyLoader
from policy.versioning import PolicyVersionManager
from policy.cache import PolicyCache
from policy.exceptions import PolicyError, PolicyValidationError


class PolicyManager:
    """
    Central orchestration service for Realtimex operational policies.
    
    Exposes unified public API contract:
    - evaluate()
    - load()
    - reload()
    - register()
    - validate()
    - rollback()
    - list_policies()
    """

    def __init__(
        self,
        event_bus: Any = None,
        policy_dir: Optional[str] = None,
        resolution_strategy: str = "priority",  # priority, deny_override, first_match
    ) -> None:
        """
        Initialize PolicyManager.
        
        Args:
            event_bus: Optional Event Bus for event-driven updates
            policy_dir: Optional default directory to load policies from
            resolution_strategy: Default conflict resolution strategy
        """
        self.bus = event_bus
        self.policy_dir = policy_dir
        
        self.registry = PolicyRegistry()
        self.compiler = RuleCompiler()
        self.cache = PolicyCache()
        self.evaluator = PolicyEvaluator(
            registry=self.registry,
            compiler=self.compiler,
            cache=self.cache,
            resolution_strategy=resolution_strategy,
        )
        self.validator = PolicyValidator()
        self.loader = PolicyLoader()
        self.versions = PolicyVersionManager()
        self._lock = threading.RLock()

        if self.policy_dir:
            self.load(self.policy_dir)

    # --- Public API Contract ---

    def evaluate(self, category: str, context: dict[str, Any]) -> str:
        """
        Evaluate active policies matching the category against context values.
        
        Returns:
            Decision string: 'allow' or 'deny'
        """
        decision = self.evaluator.evaluate(category, context)

        # Emit PolicyEvaluated event
        self._emit_event(
            "PolicyEvaluated",
            {"category": category, "context": context, "decision": decision}
        )

        return decision

    def register(self, policy: dict[str, Any]) -> None:
        """
        Register a new policy version.
        
        Validates schema, adds version, sets active, and clears evaluation cache.
        """
        with self._lock:
            # 1. Validate
            success, errors = self.validator.validate(policy)
            if not success:
                self._emit_event(
                    "PolicyRejected",
                    {"policy_id": policy.get("policy_id"), "errors": errors}
                )
                raise PolicyValidationError(f"Invalid policy structure: {errors}")

            # 2. Track Version history
            pid = policy["policy_id"]
            self.versions.add_version(policy)

            # 3. Retrieve and register the active version
            active_p = self.versions.get_active(pid)
            if active_p:
                self.registry.register(active_p)

            # 4. Clear cache to enforce re-compilation
            self.cache.clear()

            # 5. Emit Loaded/Updated events
            self._emit_event(
                "PolicyLoaded",
                {"policy_id": pid, "version": policy["version"]}
            )
            self._emit_event(
                "PolicyUpdated",
                {"policy_id": pid, "version": policy["version"]}
            )

    def load(self, path: str) -> None:
        """Load policy file (.json, .yaml, .toml) or scanner directory of policies."""
        with self._lock:
            if os.path.isdir(path):
                policies = self.loader.load_directory(path)
                for policy in policies:
                    self.register(policy)
                    
            elif os.path.isfile(path):
                if path.endswith(".json"):
                    policy = self.loader.load_json(path)
                elif path.endswith((".yaml", ".yml")):
                    policy = self.loader.load_yaml(path)
                elif path.endswith(".toml"):
                    policy = self.loader.load_toml(path)
                else:
                    raise PolicyError(f"Unsupported policy file format: {path}")
                    
                self.register(policy)
            else:
                raise PolicyError(f"Policy path not found: {path}")

    def reload(self) -> None:
        """Clear registry and cache, and reload from policy_dir path."""
        with self._lock:
            if self.policy_dir:
                self.registry.clear()
                self.cache.clear()
                self.load(self.policy_dir)

    def validate(self, policy: dict[str, Any]) -> Tuple[bool, list[str]]:
        """Validate policy format schema."""
        return self.validator.validate(policy)

    def rollback(self, policy_id: str) -> str:
        """
        Rollback policy ID to its previous lexicographical version.
        
        Returns:
            The version string rolled back to
        """
        with self._lock:
            version = self.versions.rollback(policy_id)
            active_p = self.versions.get_active(policy_id)
            if active_p:
                self.registry.register(active_p)
                
            self.cache.clear()

            # Emit PolicyRolledBack event
            self._emit_event(
                "PolicyRolledBack",
                {"policy_id": policy_id, "version": version}
            )

            return version

    def list_policies(self, category: Optional[str] = None) -> list[dict[str, Any]]:
        """List active registered policies."""
        if category:
            return self.registry.list_by_category(category)
        return self.registry.list_all()

    # --- Internal Event Helper ---

    def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Publish event via Event Bus."""
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name=event_name,
                        source="policy.manager",
                        payload=payload,
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass
