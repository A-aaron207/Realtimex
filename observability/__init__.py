"""
Realtimex Observability System.

Provides logging, metrics collection, distributed tracing, health checks,
diagnostics analyzer, and security audit log tracking.
"""

from __future__ import annotations

from observability.manager import Observability
from observability.logging.manager import LoggingManager
from observability.logging.audit import AuditLogger
from observability.metrics.manager import MetricsManager
from observability.tracing.tracer import Tracer
from observability.tracing.spans import Span
from observability.health.monitor import HealthMonitor
from observability.health.checks import HealthCheck, HealthStatus
from observability.diagnostics.analyzer import DiagnosticsAnalyzer

from observability.exceptions import (
    ObservabilityError,
    LoggingError,
    MetricsError,
    TracingError,
    HealthError,
    DiagnosticsError,
)

__all__ = [
    # Top-level orchestrator
    "Observability",
    
    # Subsystem managers
    "LoggingManager",
    "AuditLogger",
    "MetricsManager",
    "Tracer",
    "Span",
    "HealthMonitor",
    "HealthCheck",
    "HealthStatus",
    "DiagnosticsAnalyzer",
    
    # Exceptions
    "ObservabilityError",
    "LoggingError",
    "MetricsError",
    "TracingError",
    "HealthError",
    "DiagnosticsError",
]
