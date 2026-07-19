"""
Custom exceptions for the Realtimex Worker Runtime.
"""

from __future__ import annotations


class WorkerError(Exception):
    """Base exception for all worker runtime errors."""


class WorkerNotFoundError(WorkerError):
    """Raised when a specified worker cannot be found."""


class WorkerExecutionError(WorkerError):
    """Raised when a worker fails to execute an assigned task step."""


class InvalidWorkerLifecycleError(WorkerError):
    """Raised when an illegal worker state transition is attempted."""


class WorkerPoolError(WorkerError):
    """Raised when a worker pool operation fails."""
