"""
Permission Decision models for the Realtimex Permission System.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PermissionDecision:
    """
    Structured outcome of a permission request evaluation.
    """
    approved: bool
    reason: str
    reviewer: str  # rule_engine, cognitive_engine, policy_evaluator, user
    expiration: datetime | None = None
    cache_policy: str = "once"  # once, task, session, persistent
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "reason": self.reason,
            "reviewer": self.reviewer,
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "cache_policy": self.cache_policy,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionDecision:
        exp = data.get("expiration")
        expiration = datetime.fromisoformat(exp) if isinstance(exp, str) else None
        
        return cls(
            approved=data["approved"],
            reason=data["reason"],
            reviewer=data["reviewer"],
            expiration=expiration,
            cache_policy=data.get("cache_policy", "once"),
            metadata=data.get("metadata", {}),
        )
