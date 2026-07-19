"""
Custom exceptions for the Realtimex Memory System.
"""

from __future__ import annotations


class MemoryError(Exception):
    """Base exception for all Memory System errors."""


class MemoryNotFoundError(MemoryError):
    """Raised when a specific memory record is not found."""


class MemoryValidationError(MemoryError):
    """Raised when memory record data fails schema or validation checks."""


class MemoryScopeError(MemoryError):
    """Raised when performing illegal scope operations (e.g. invalid scopes)."""


class MemoryPolicyViolationError(MemoryError):
    """Raised when a memory policy is violated (e.g. task memory capacity limits)."""


class MemoryPersistenceError(MemoryError):
    """Raised when writing or reading from persistent memory storage fails."""
