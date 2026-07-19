"""
Custom exceptions for the Realtimex Policy Engine.
"""

from __future__ import annotations


class PolicyError(Exception):
    """Base exception for all Policy Engine errors."""


class PolicyValidationError(PolicyError):
    """Raised when policy validation against schema fails."""


class PolicyEvaluationError(PolicyError):
    """Raised when evaluating a policy condition or rule encounters an error."""


class PolicyConflictError(PolicyError):
    """Raised when multiple conflicting policies cannot be resolved."""


class PolicyVersionError(PolicyError):
    """Raised when version control, activation, or rollback operations fail."""
