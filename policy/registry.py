"""
Policy Registry for Realtimex.

Registers and indexes policies by ID and Category.
"""

from __future__ import annotations

import threading
from typing import Any, Optional


class PolicyRegistry:
    """Provides thread-safe storage and category querying for active policies."""

    def __init__(self) -> None:
        # policy_id -> policy_dict
        self._policies: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register(self, policy: dict[str, Any]) -> None:
        """Register a policy dictionary."""
        with self._lock:
            pid = policy["policy_id"]
            self._policies[pid] = policy

    def deregister(self, policy_id: str) -> None:
        """Remove a policy by ID."""
        with self._lock:
            self._policies.pop(policy_id, None)

    def get(self, policy_id: str) -> Optional[dict[str, Any]]:
        """Fetch policy by ID."""
        with self._lock:
            return self._policies.get(policy_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all active registered policies."""
        with self._lock:
            return list(self._policies.values())

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        """Filter and list active policies matching a category."""
        with self._lock:
            return [p for p in self._policies.values() if p["category"] == category]

    def clear(self) -> None:
        """Clear all active registered policies."""
        with self._lock:
            self._policies.clear()
