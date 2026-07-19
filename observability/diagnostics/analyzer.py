"""
Diagnostics Analyzer for Realtimex.

Aggregates system performance snapshots and diagnostic reports.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from observability.diagnostics.snapshots import take_system_snapshot
from observability.diagnostics.profiler import Profiler
from observability.exceptions import DiagnosticsError


class DiagnosticsAnalyzer:
    """
    Central diagnostics engine for Realtimex.
    
    Coordinates profiling data, system snapshots, thread dumps,
    and gathers runtime analytics for export or audit.
    """

    def __init__(
        self,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Diagnostics Analyzer.
        
        Args:
            event_bus: Optional Event Bus for emitting diagnostics events
            logger: Optional logger instance
        """
        self.bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.observability.diagnostics")
        self.profiler = Profiler()
        self._lock = threading.RLock()

    def generate_report(self, component_stats: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Generate a comprehensive diagnostics report.
        
        Args:
            component_stats: Optional additional statistics from other subsystems
            
        Returns:
            Diagnostics report dictionary
        """
        try:
            snapshot = take_system_snapshot()
            timestamp = datetime.now(timezone.utc).isoformat()
            
            report = {
                "timestamp": timestamp,
                "system": snapshot,
                "profile_stats": self.profiler.get_all_stats(),
                "component_stats": component_stats or {},
            }

            self.logger.info("Diagnostics report generated at %s", timestamp)
            
            # Emit DiagnosticsGenerated event
            self._emit_event("DiagnosticsGenerated", {"timestamp": timestamp})
            
            return report
            
        except Exception as e:
            raise DiagnosticsError(f"Failed to generate diagnostics report: {e}") from e

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit diagnostics event via Event Bus."""
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name=event_type,
                        source="observability.diagnostics",
                        payload=data,
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass
