"""
Custom exceptions for the Realtimex Task System.
"""

from __future__ import annotations


class TaskSystemError(Exception):
    """Base exception for all Task System errors."""


class TaskNotFoundError(TaskSystemError):
    """Raised when a requested task cannot be found."""


class InvalidTaskStateTransitionError(TaskSystemError):
    """Raised when a task transition is invalid under the task state lifecycle."""


class TaskValidationError(TaskSystemError):
    """Raised when task data fails validation."""


class TaskPersistenceError(TaskSystemError):
    """Raised when task persistence operations fail."""


class TaskRecoveryError(TaskSystemError):
    """Raised when task recovery operations fail."""
