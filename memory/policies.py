"""
Memory policies configuration and enforcer for the Realtimex Memory System.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from memory.exceptions import MemoryPolicyViolationError
from memory.registry import MemoryRecord


@dataclass
class MemoryPolicy:
    """
    Configuration parameters for memory lifecycle and size limits.
    """
    max_records_per_task: int = 1000
    retention_period_days: int = 365
    auto_archive_on_expiry: bool = True
    default_ephemeral_ttl_seconds: int = 300


class PolicyEnforcer:
    """
    Validates and enforces memory size, retention, and expiration rules.
    """

    def __init__(self, policy: MemoryPolicy | None = None) -> None:
        self.policy = policy or MemoryPolicy()

    def enforce_limits(self, record: MemoryRecord, current_count: int) -> None:
        """
        Enforce memory capacity rules before adding a record.
        """
        if record.scope == "task":
            if current_count >= self.policy.max_records_per_task:
                raise MemoryPolicyViolationError(
                    f"Memory limit exceeded: Task '{record.owner}' has reached the maximum allowed "
                    f"memory records ({self.policy.max_records_per_task})."
                )

    def is_expired(self, record: MemoryRecord) -> bool:
        """
        Verify if a memory record has expired based on its explicit expiration timestamp.
        """
        if record.expires_at is None:
            return False
        return datetime.now(timezone.utc) > record.expires_at

    def should_be_pruned(self, record: MemoryRecord) -> bool:
        """
        Verify if an archived memory record is beyond its retention period.
        """
        if record.status != "archived":
            return False
            
        now = datetime.now(timezone.utc)
        age = now - record.updated_at
        return age.days >= self.policy.retention_period_days
