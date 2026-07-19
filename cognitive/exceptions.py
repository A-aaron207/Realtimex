"""
Custom exceptions for the Realtimex Cognitive Engine.
"""

from __future__ import annotations


class CognitiveError(Exception):
    """Base exception for all Cognitive Engine errors."""


class ReasoningError(CognitiveError):
    """Raised when a reasoning provider fails or returns invalid reasoning formats."""


class ValidationError(CognitiveError):
    """Raised when a recommendation fails safety, capability, or semantic validation."""


class ContextBuilderError(CognitiveError):
    """Raised when building reasoning context fails."""


class PlanningError(CognitiveError):
    """Raised when planning or workflow optimization fails."""
