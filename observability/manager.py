"""
Observability Manager for Realtimex.

The central orchestration service for logging, metrics, tracing, health, diagnostics, and audit logs.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from observability.logging.manager import LoggingManager
from observability.logging.audit import AuditLogger
from observability.metrics.manager import MetricsManager
from observability.tracing.tracer import Tracer
from observability.tracing.spans import Span
from observability.health.monitor import HealthMonitor
from observability.health.reports import HealthReport
from observability.diagnostics.analyzer import DiagnosticsAnalyzer


class Observability:
    """
    Central orchestration subsystem for Realtimex Observability.
    
    Exposes unified public API methods mapping to specialized managers:
    - Logging Manager
    - Metrics Manager
    - Distributed Tracing
    - Health Monitor
    - Diagnostics Engine
    - Audit Logger
    """

    def __init__(
        self,
        event_bus: Any = None,
        config_dir: str = "config",
        log_filepath: Optional[str] = None,
        audit_filepath: Optional[str] = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Observability System.
        
        Args:
            event_bus: Optional Event Bus for event-driven observability
            config_dir: Directory for configurations
            log_filepath: Optional log file path
            audit_filepath: Optional audit log file path
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.observability")
        
        # Instantiate sub-managers
        self.logging_mgr = LoggingManager(event_bus=event_bus)
        self.metrics_mgr = MetricsManager(event_bus=event_bus)
        self.tracer = Tracer(event_bus=event_bus)
        self.health_monitor = HealthMonitor(event_bus=event_bus)
        self.diagnostics_analyzer = DiagnosticsAnalyzer(event_bus=event_bus)
        self.audit_logger = AuditLogger(event_bus=event_bus, filepath=audit_filepath)

        # Wire file sink to log manager if path provided
        if log_filepath:
            from observability.logging.sinks import create_rotating_file_sink
            file_sink = create_rotating_file_sink(log_filepath)
            self.logging_mgr.add_sink(file_sink)

    # --- Public API Contract ---

    def log(
        self,
        level: str | int,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log structured log record."""
        self.logging_mgr.log(level, message, context)

    def metric(
        self,
        name: str,
        value: Any,
        metric_type: str = "counter",
        tags: Optional[dict[str, str]] = None,
    ) -> None:
        """Record metric observation."""
        if metric_type == "counter":
            self.metrics_mgr.increment(name, int(value), tags)
        elif metric_type == "gauge":
            self.metrics_mgr.set_gauge(name, value, tags)
        elif metric_type == "histogram":
            self.metrics_mgr.record_histogram(name, float(value), tags)
        else:
            self.logger.warning("Unsupported metric type: %s", metric_type)

    def trace(self, name: str, trace_id: Optional[str] = None) -> Span:
        """
        Start a trace context manager span.
        
        If an active parent trace context exists on this thread,
        automatically initiates a child span context.
        """
        from observability.tracing.context import get_current_trace_id
        if get_current_trace_id():
            return self.tracer.start_span(name)
        return self.tracer.start_trace(name, trace_id)

    def health(self) -> HealthReport:
        """Run all active component health checks and return the report."""
        return self.health_monitor.check_health()

    def diagnostics(self, component_stats: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Generate a complete diagnostic snapshot report."""
        return self.diagnostics_analyzer.generate_report(component_stats)

    def audit(
        self,
        action: str,
        actor: str,
        status: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a security auditing entry."""
        self.audit_logger.record(action, actor, status, details)

    def report(self) -> dict[str, Any]:
        """Retrieve aggregated summary report of health status and metrics."""
        return {
            "health": self.health().to_dict(),
            "metrics": self.metrics_mgr.get_all(),
        }
