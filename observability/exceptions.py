"""
Custom exceptions for the Realtimex Observability System.
"""

from __future__ import annotations


class ObservabilityError(Exception):
    """Base exception for all Observability System errors."""


class LoggingError(ObservabilityError):
    """Raised when a logging operation fails."""


class MetricsError(ObservabilityError):
    """Raised when a metrics operation fails."""


class TracingError(ObservabilityError):
    """Raised when a tracing operation fails."""


class HealthError(ObservabilityError):
    """Raised when a health check operation fails."""


class DiagnosticsError(ObservabilityError):
    """Raised when diagnostics generation fails."""
