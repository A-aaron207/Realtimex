"""
Custom exceptions for the Realtimex Scheduler.
"""

from __future__ import annotations


class SchedulerError(Exception):
    """Base exception for all Scheduler errors."""


class QueueError(SchedulerError):
    """Raised when an operation on the scheduling queue fails."""


class AllocationError(SchedulerError):
    """Raised when the Scheduler cannot allocate a worker for a capability."""


class DispatchError(SchedulerError):
    """Raised when dispatching a step execution fails."""


class DependencyError(SchedulerError):
    """Raised when dependency resolution fails or prerequisites are not met."""
