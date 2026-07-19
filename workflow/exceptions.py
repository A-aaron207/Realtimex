"""
Custom exceptions for the Realtimex Workflow Engine.
"""

from __future__ import annotations


class WorkflowError(Exception):
    """Base exception for all Workflow Engine errors."""


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow or step cannot be found."""


class WorkflowValidationError(WorkflowError):
    """Raised when a workflow fails structural, dependency, or lifecycle validation."""


class WorkflowPersistenceError(WorkflowError):
    """Raised when a workflow persistence operation fails."""


class InvalidStepStateTransitionError(WorkflowError):
    """Raised when a workflow step state transition is invalid."""
