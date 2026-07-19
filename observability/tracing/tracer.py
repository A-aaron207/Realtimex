"""
Distributed Tracer for Realtimex.

Manages trace creation, nesting child spans, and emitting trace events.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Optional

from observability.tracing.context import get_current_trace_id, get_current_span_id
from observability.tracing.spans import Span
from observability.exceptions import TracingError


class Tracer:
    """
    Central distributed tracing engine for Realtimex.
    
    Orchestrates trace contexts, propagates parent span references,
    records completed traces, and emits event notifications.
    """

    def __init__(
        self,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Tracer.
        
        Args:
            event_bus: Optional Event Bus for emitting trace events
            logger: Optional logger instance
        """
        self.bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.observability.tracing")
        self._completed_traces: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def start_trace(self, name: str, trace_id: Optional[str] = None) -> Span:
        """
        Start a new root trace execution.
        
        Args:
            name: Root trace/operation name
            trace_id: Optional custom trace ID
            
        Returns:
            Span representing root trace context
        """
        tid = trace_id or str(uuid.uuid4())
        return Span(name=name, trace_id=tid, parent_span_id=None, tracer=self)

    def start_span(self, name: str) -> Span:
        """
        Start a nested span of execution.
        
        Inherits current trace ID and active parent span ID from context.
        If no active trace context exists, starts a new root trace.
        
        Args:
            name: Span operation name
            
        Returns:
            Span representing new nested execution context
        """
        tid = get_current_trace_id()
        sid = get_current_span_id()
        
        if not tid:
            return self.start_trace(name)
            
        return Span(name=name, trace_id=tid, parent_span_id=sid, tracer=self)

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Get all recorded spans for a trace ID."""
        with self._lock:
            return self._completed_traces.get(trace_id, []).copy()

    def clear_traces(self) -> None:
        """Clear completed traces history."""
        with self._lock:
            self._completed_traces.clear()

    # --- Internal Span Callbacks ---

    def _on_span_start(self, span: Span) -> None:
        """Triggered when a span starts."""
        if not span.parent_span_id:
            self._emit_event(
                "TraceStarted",
                {"trace_id": span.trace_id, "name": span.name}
            )

    def _on_span_end(self, span: Span) -> None:
        """Triggered when a span ends. Registers span and emits completion events."""
        with self._lock:
            if span.trace_id not in self._completed_traces:
                self._completed_traces[span.trace_id] = []
            self._completed_traces[span.trace_id].append(span.to_dict())

        if not span.parent_span_id:
            spans_list = []
            with self._lock:
                spans_list = self._completed_traces.get(span.trace_id, [])
                
            self._emit_event(
                "TraceCompleted",
                {
                    "trace_id": span.trace_id,
                    "name": span.name,
                    "duration": span.duration,
                    "status": span.status,
                    "spans": spans_list,
                }
            )

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit tracing event via Event Bus."""
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name=event_type,
                        source="observability.tracing",
                        payload=data,
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass
                
        self.logger.debug("Tracing event emitted: %s (%s)", event_type, data.get("trace_id"))
