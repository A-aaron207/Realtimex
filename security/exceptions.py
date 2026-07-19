"""
Custom exceptions for the Realtimex Security & Sandboxing System.
"""

from __future__ import annotations


class SecurityError(Exception):
    """Base exception for all security-related errors."""


class SandboxError(SecurityError):
    """Raised when sandbox operations fail."""


class SandboxViolationError(SecurityError):
    """Raised when a sandbox constraint or isolation boundary is violated."""


class ResourceLimitExceededError(SecurityError):
    """Raised when a task exceeds its configured system resource limits."""


class PolicyValidationError(SecurityError):
    """Raised when checking or registering security policies fails."""
