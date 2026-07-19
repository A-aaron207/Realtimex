"""
Custom exceptions for the Realtimex Module Development Kit (MDK).
"""

from __future__ import annotations


class SDKError(Exception):
    """Base exception for all SDK and MDK errors."""


class GeneratorError(SDKError):
    """Raised when module or file scaffolding generation fails."""


class SDKValidationError(SDKError):
    """Raised when module, manifest, or package validation fails."""


class PackagingError(SDKError):
    """Raised when building, installing, or packaging a module fails."""
