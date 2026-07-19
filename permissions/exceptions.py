"""
Custom exceptions for the Realtimex Permission System.
"""

from __future__ import annotations


class PermissionSystemError(Exception):
    """Base exception for all Permission System errors."""


class PermissionDeniedError(PermissionSystemError):
    """Raised when an operation is explicitly denied by the permission gateway."""


class PermissionValidationError(PermissionSystemError):
    """Raised when a request, policy, or decision validation fails."""


class TrustLevelError(PermissionSystemError):
    """Raised when looking up or modifying trust levels encounters problems."""


class PermissionCacheError(PermissionSystemError):
    """Raised when permission caching operations fail."""


class PolicyValidationError(PermissionSystemError):
    """Raised when permission policy parsing or parsing rules fails."""
