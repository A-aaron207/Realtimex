"""
Custom exceptions for the Realtimex Recovery System.
"""

from __future__ import annotations


class RecoveryError(Exception):
    """Base exception for all Recovery System errors."""


class CheckpointError(RecoveryError):
    """Raised when checkpoint loading, saving, or parsing fails."""


class SnapshotError(RecoveryError):
    """Raised when snapshot backup or restore operations encounter issues."""


class StateValidationError(RecoveryError):
    """Raised when data integrity or schema validation checks fail."""


class RecoveryPolicyError(RecoveryError):
    """Raised when recovery operations violate configured limits or retention rules."""


class RecoveryPlannerError(RecoveryError):
    """Raised when the recovery planner fails to chart or sequence the recovery path."""
