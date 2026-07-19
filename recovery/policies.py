"""
Recovery policies configuration for limits and strategies in Realtimex.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class RecoveryPolicy:
    """
    Configuration parameters regulating checkpoint/snapshot retention and recovery strategies.
    
    Attributes:
        checkpoint_interval_seconds: Frequency of automatic checkpoints (default: 60s)
        max_retained_checkpoints: Maximum number of checkpoints to keep (default: 5)
        snapshot_retention_days: Retention period for snapshot backups in days (default: 30)
        auto_cleanup_on_start: Whether to cleanup expired items on kernel boot (default: True)
        recovery_strategy: Strategy for handling corrupted data during recovery:
            - "fail_safe": Recover valid data, isolate corrupted items (resilient, prioritizes availability)
            - "strict": Abort recovery completely if any corruption detected (safe, prioritizes consistency)
    """
    
    checkpoint_interval_seconds: float = 60.0
    """Time in seconds between automatic checkpoints (configurable interval)"""
    
    max_retained_checkpoints: int = 5
    """Maximum number of checkpoints to keep on disk (older ones pruned automatically)"""
    
    snapshot_retention_days: int = 30
    """Retention period for diagnostic snapshots in days (not currently enforced by time)"""
    
    auto_cleanup_on_start: bool = True
    """Automatically cleanup expired recovery data when kernel boots"""
    
    recovery_strategy: Literal["fail_safe", "strict"] = "fail_safe"
    """
    Recovery strategy when data corruption is detected:
    - fail_safe: Recover what can be recovered, isolate corrupted items
    - strict: Abort recovery if any corruption is found
    """
