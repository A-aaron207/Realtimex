"""
Policy Evaluator for Realtimex.

Evaluates matching policies against context and resolves conflicts based on selected strategies.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from policy.compiler import RuleCompiler
from policy.registry import PolicyRegistry
from policy.cache import PolicyCache


class PolicyEvaluator:
    """Evaluates context parameters against active policies and resolves conflicts."""

    def __init__(
        self,
        registry: PolicyRegistry,
        compiler: RuleCompiler,
        cache: Optional[PolicyCache] = None,
        resolution_strategy: str = "priority",  # priority, deny_override, first_match
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize PolicyEvaluator.
        
        Args:
            registry: PolicyRegistry instance
            compiler: RuleCompiler instance
            cache: Optional PolicyCache instance
            resolution_strategy: Conflict resolution name
            logger: Optional logger instance
        """
        self.registry = registry
        self.compiler = compiler
        self.cache = cache or PolicyCache()
        self.resolution_strategy = resolution_strategy
        self.logger = logger or logging.getLogger("realtimex.policy.evaluator")

    def evaluate(self, category: str, context: dict[str, Any]) -> str:
        """
        Evaluate context parameters against policies matching target category.
        
        Args:
            category: Policy category (e.g. 'security', 'worker')
            context: Context data dictionary (e.g. {'user': {'role': 'admin'}})
            
        Returns:
            Decision string: 'allow' or 'deny'
        """
        # Fetch enabled policies under category
        all_policies = self.registry.list_by_category(category)
        enabled_policies = [p for p in all_policies if p.get("enabled", True)]

        if not enabled_policies:
            self.logger.debug("No policies found in category: %s (Default Deny)", category)
            return "deny"

        matched = []
        for policy in enabled_policies:
            pid = policy["policy_id"]
            cache_key = f"compiled_{pid}_{policy['version']}"
            
            # Fetch compiled code execution block from cache
            compiled_fn = self.cache.get(cache_key)
            if not compiled_fn:
                compiled_fn = self.compiler.compile_policy(policy["conditions"])
                self.cache.set(cache_key, compiled_fn)

            # Evaluate
            try:
                if compiled_fn(context):
                    matched.append(policy)
            except Exception as e:
                self.logger.error("Error evaluating policy %s: %s", pid, e)
                continue

        if not matched:
            self.logger.debug("No policies matched for category: %s (Default Deny)", category)
            return "deny"

        # Resolve conflicts based on strategy
        decision = self.resolve_conflict(matched)
        
        return decision

    def resolve_conflict(self, matched_policies: list[dict[str, Any]]) -> str:
        """
        Resolve conflicts among matched policies based on active resolution_strategy.
        
        Supported strategies:
        - 'priority': Highest priority value wins.
        - 'deny_override': If any matched policy has a 'deny' effect, 'deny' wins.
        - 'first_match': First matched policy in order of registry query wins.
        """
        if not matched_policies:
            return "deny"

        if self.resolution_strategy == "deny_override":
            for p in matched_policies:
                if p["effect"] == "deny":
                    return "deny"
            return "allow"

        elif self.resolution_strategy == "first_match":
            return matched_policies[0]["effect"]

        elif self.resolution_strategy == "priority":
            # Sort by priority value descending, then default deny overrides allow if priorities are equal
            sorted_p = sorted(
                matched_policies,
                key=lambda p: (p["priority"], 1 if p["effect"] == "deny" else 0),
                reverse=True
            )
            return sorted_p[0]["effect"]

        # Default fallback (priority sorting)
        sorted_p = sorted(matched_policies, key=lambda p: p["priority"], reverse=True)
        return sorted_p[0]["effect"]
