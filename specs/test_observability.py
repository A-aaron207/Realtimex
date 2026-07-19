"""
Unit tests for the Realtimex Observability System.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
import pytest
from unittest.mock import MagicMock

from events.bus import EventBus
from events.event import Event
from observability.manager import Observability
from observability.logging.manager import LoggingManager
from observability.logging.audit import AuditLogger
from observability.metrics.manager import MetricsManager
from observability.metrics.exporters import LogExporter, FileExporter
from observability.tracing.tracer import Tracer
from observability.tracing.context import get_current_trace_id, get_current_span_id
from observability.health.monitor import HealthMonitor
from observability.health.checks import ResourceHealthCheck, PingHealthCheck, HealthStatus
from observability.diagnostics.analyzer import DiagnosticsAnalyzer
from observability.exceptions import ObservabilityError


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def event_bus():
    """Fixture for Event Bus."""
    return MagicMock(spec=EventBus)


def test_logging_manager_structured_context(event_bus):
    """Test LoggingManager log levels and context binding."""
    log_mgr = LoggingManager(event_bus=event_bus)
    log_mgr.set_level("DEBUG")
    
    # Context binding
    log_mgr.bind_context(session_id="sess-abc", request_id="req-123")
    assert log_mgr.get_context() == {"session_id": "sess-abc", "request_id": "req-123"}
    
    # Unbind context
    log_mgr.unbind_context("session_id")
    assert log_mgr.get_context() == {"request_id": "req-123"}
    
    # Logging execution & EventBus trigger check
    log_mgr.info("Testing structured log", {"extra_val": 42})
    assert event_bus.publish.called
    
    # Verify published log payload
    event = event_bus.publish.call_args[0][0]
    assert event.name == "LogWritten"
    assert event.payload["message"] == "Testing structured log"
    assert event.payload["context"]["request_id"] == "req-123"
    assert event.payload["context"]["extra_val"] == 42


def test_metrics_manager_collection_and_export(temp_dir, event_bus):
    """Test MetricsManager recording and exporting to file."""
    metrics_mgr = MetricsManager(event_bus=event_bus)
    
    # Test counter
    metrics_mgr.increment("tasks.completed")
    metrics_mgr.increment("tasks.completed", 2)
    assert metrics_mgr.get_metric("tasks.completed") == 3
    
    # Test gauge
    metrics_mgr.set_gauge("queue.length", 15)
    assert metrics_mgr.get_metric("queue.length") == 15
    
    # Test histogram
    metrics_mgr.record_histogram("model.latency_ms", 120.5)
    metrics_mgr.record_histogram("model.latency_ms", 130.0)
    assert len(metrics_mgr.get_metric("model.latency_ms")) == 2
    
    # Test FileExporter persistence
    export_file = os.path.join(temp_dir, "metrics.json")
    exporter = FileExporter(export_file)
    metrics_mgr.add_exporter(exporter)
    metrics_mgr.export()
    
    assert os.path.exists(export_file)
    with open(export_file, "r") as f:
        data = json.load(f)
    assert data["tasks.completed"] == 3
    assert data["queue.length"] == 15
    assert "system.cpu_percent" in data


def test_tracing_context_nesting(event_bus):
    """Test trace context manager propagation and child spans nesting."""
    tracer = Tracer(event_bus=event_bus)
    
    # Start root trace
    with tracer.start_trace("root-operation") as root:
        assert root.trace_id is not None
        assert get_current_trace_id() == root.trace_id
        assert get_current_span_id() == root.span_id
        
        # Start nested child span
        with tracer.start_span("child-operation") as child:
            assert child.trace_id == root.trace_id
            assert child.parent_span_id == root.span_id
            assert get_current_span_id() == child.span_id
            
        # Context restored to root span
        assert get_current_span_id() == root.span_id
        
    # Context cleared after trace block exits
    assert get_current_trace_id() is None
    assert get_current_span_id() is None
    
    # Verify trace history and events
    assert len(tracer.get_trace(root.trace_id)) == 2
    assert event_bus.publish.called


def test_health_monitor_status_evaluation(event_bus):
    """Test health component check evaluation and status transitions."""
    monitor = HealthMonitor(event_bus=event_bus)
    
    # Register mock healthy ping check
    check_healthy = PingHealthCheck("mem_store_ping", lambda: True)
    monitor.register_check("memory", check_healthy)
    
    # Register mock degraded check
    check_degraded = ResourceHealthCheck(
        name="worker_cpu",
        check_func=lambda: 85.0,
        warn_threshold=80.0,
        fail_threshold=95.0
    )
    monitor.register_check("workers", check_degraded)
    
    # Register mock failing check
    check_failed = ResourceHealthCheck(
        name="disk_space",
        check_func=lambda: 98.0,
        warn_threshold=80.0,
        fail_threshold=95.0
    )
    monitor.register_check("scheduler", check_failed)
    
    # Run check
    report = monitor.check_health()
    
    assert report.status == HealthStatus.FAILED
    assert report.components["memory"]["status"] == HealthStatus.HEALTHY
    assert report.components["workers"]["status"] == HealthStatus.DEGRADED
    assert report.components["scheduler"]["status"] == HealthStatus.FAILED
    
    # Verify state transitions warnings and events
    assert monitor.get_status("scheduler") == HealthStatus.FAILED
    assert event_bus.publish.called


def test_diagnostics_report(event_bus):
    """Test DiagnosticsAnalyzer report creation and code profiling."""
    analyzer = DiagnosticsAnalyzer(event_bus=event_bus)
    
    # Test Profiler duration logging
    with analyzer.profiler.profile("complex_search"):
        time.sleep(0.01)
        
    stats = analyzer.profiler.get_stats("complex_search")
    assert stats["count"] == 1
    assert stats["avg"] > 0.0
    
    # Generate diagnostics report
    report = analyzer.generate_report(component_stats={"tasks": {"active": 4}})
    
    assert "timestamp" in report
    assert "system" in report
    assert len(report["system"]["threads"]) > 0
    assert report["component_stats"]["tasks"]["active"] == 4
    assert event_bus.publish.called


def test_audit_logger_immutability(temp_dir, event_bus):
    """Test AuditLogger logs security events safely and append-only."""
    audit_file = os.path.join(temp_dir, "audit.log")
    audit = AuditLogger(event_bus=event_bus, filepath=audit_file)
    
    audit.record(
        action="permission.approve",
        actor="admin_user",
        status="success",
        details={"resource": "memory.records"}
    )
    
    records = audit.get_records()
    assert len(records) == 1
    assert records[0]["action"] == "permission.approve"
    assert records[0]["actor"] == "admin_user"
    
    # Mutating returned list should not modify internal list
    records.append({"tampered": True})
    assert len(audit.get_records()) == 1
    
    # Verify file append
    assert os.path.exists(audit_file)
    with open(audit_file, "r") as f:
        line = f.readline()
        data = json.loads(line)
    assert data["action"] == "permission.approve"
    assert event_bus.publish.called


def test_unified_observability_api(temp_dir, event_bus):
    """Test overall unified Observability orchestration class."""
    log_file = os.path.join(temp_dir, "realtimex.log")
    audit_file = os.path.join(temp_dir, "audit.log")
    
    obs = Observability(
        event_bus=event_bus,
        log_filepath=log_file,
        audit_filepath=audit_file
    )
    
    # Test logging
    obs.log("INFO", "Logging message via unified manager")
    
    # Test metrics
    obs.metric("worker.utilization", 75, "gauge")
    assert obs.metrics_mgr.get_metric("worker.utilization") == 75
    
    # Test tracing context Manager
    with obs.trace("web-request") as span:
        assert span.trace_id is not None
        
    # Test audit
    obs.audit("user.authenticate", "cli_user", "success")
    assert len(obs.audit_logger.get_records()) == 1
    
    # Test summary report
    rep = obs.report()
    assert "health" in rep
    assert "metrics" in rep
