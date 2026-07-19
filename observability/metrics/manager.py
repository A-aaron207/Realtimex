"""
Metrics Manager for Realtimex.

Handles recording counters, gauges, histograms, collecting resource utilization,
and exporting metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from observability.metrics.collectors import get_cpu_usage, get_memory_usage, get_disk_usage
from observability.metrics.exporters import MetricExporter
from observability.exceptions import MetricsError


class MetricsManager:
    """
    Central metrics engine for Realtimex.
    
    Provides APIs for counters, gauges, histograms, automatic
    gathering of system statistics, and scheduled metrics exportation.
    """

    def __init__(
        self,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Metrics Manager.
        
        Args:
            event_bus: Optional Event Bus for emitting MetricRecorded events
            logger: Optional logger instance
        """
        self.bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.observability.metrics")
        self._metrics: dict[str, Any] = {}
        self._exporters: list[MetricExporter] = []
        
        self._lock = threading.RLock()
        self._running = False
        self._export_thread: Optional[threading.Thread] = None

    def add_exporter(self, exporter: MetricExporter) -> None:
        """Register a new metric exporter."""
        with self._lock:
            self._exporters.append(exporter)

    def remove_exporter(self, exporter: MetricExporter) -> None:
        """Deregister a metric exporter."""
        with self._lock:
            if exporter in self._exporters:
                self._exporters.remove(exporter)

    # --- Recording API ---

    def increment(self, name: str, value: int = 1, tags: Optional[dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        with self._lock:
            current = self._metrics.get(name, 0)
            if not isinstance(current, (int, float)):
                current = 0
            self._metrics[name] = current + value
            self._emit_metric(name, self._metrics[name], "counter", tags)

    def set_gauge(self, name: str, value: Any, tags: Optional[dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        with self._lock:
            self._metrics[name] = value
            self._emit_metric(name, value, "gauge", tags)

    def record_histogram(self, name: str, value: float, tags: Optional[dict[str, str]] = None) -> None:
        """Record value inside a histogram log."""
        with self._lock:
            if name not in self._metrics or not isinstance(self._metrics[name], list):
                self._metrics[name] = []
            
            self._metrics[name].append(value)
            # Cap observations to prevent memory leaks
            if len(self._metrics[name]) > 1000:
                self._metrics[name].pop(0)
                
            self._emit_metric(name, value, "histogram", tags)

    def get_metric(self, name: str, default: Any = None) -> Any:
        """Retrieve recorded metric value."""
        with self._lock:
            return self._metrics.get(name, default)

    def get_all(self) -> dict[str, Any]:
        """Get copy of all recorded metrics, including fresh system stats."""
        with self._lock:
            snapshot = self._metrics.copy()
            # Inject current system resource stats
            snapshot["system.cpu_percent"] = get_cpu_usage()
            snapshot["system.memory_mb"] = get_memory_usage()
            disk = get_disk_usage()
            snapshot["system.disk_total_mb"] = disk["total_mb"]
            snapshot["system.disk_used_mb"] = disk["used_mb"]
            snapshot["system.disk_free_mb"] = disk["free_mb"]
            snapshot["system.disk_percent"] = disk["percent_used"]
            return snapshot

    # --- Exporting API ---

    def export(self) -> None:
        """Manually trigger metrics export to all registered sinks."""
        with self._lock:
            snapshot = self.get_all()
            for exporter in self._exporters:
                try:
                    exporter.export(snapshot)
                except Exception as e:
                    self.logger.error("Failed to export metrics: %s", e)

    def start_export_loop(self, interval: float = 60.0) -> None:
        """Start background daemon thread to export metrics periodically."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._export_thread = threading.Thread(
                target=self._export_loop,
                args=(interval,),
                daemon=True
            )
            self._export_thread.start()
            self.logger.info("Metrics periodic export thread started (interval: %.1fs)", interval)

    def stop_export_loop(self) -> None:
        """Stop background export loop."""
        with self._lock:
            self._running = False
            self.logger.info("Metrics periodic export thread stopped.")

    def _export_loop(self, interval: float) -> None:
        while getattr(self, "_running", False):
            time.sleep(interval)
            try:
                self.export()
            except Exception as e:
                self.logger.error("Error in metrics export loop: %s", e)

    def _emit_metric(
        self,
        name: str,
        value: Any,
        metric_type: str,
        tags: Optional[dict[str, str]] = None,
    ) -> None:
        """Emit MetricRecorded event via Event Bus."""
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name="MetricRecorded",
                        source="observability.metrics",
                        payload={
                            "name": name,
                            "value": value,
                            "type": metric_type,
                            "tags": tags or {},
                            "timestamp": time.time(),
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass
