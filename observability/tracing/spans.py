"""
Tracing Spans for Realtimex.

Defines the Span class representing a unit of traced execution.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional


class Span:
    """Represents a single span of execution trace context."""

    def __init__(
        self,
        name: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        tracer: Optional[Any] = None,
    ) -> None:
        """
        Initialize a Tracing Span.
        
        Args:
            name: Span name / operation description
            trace_id: Active trace context ID
            parent_span_id: Optional parent span context ID
            tracer: Tracer reference
        """
        self.name = name
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.span_id = str(uuid.uuid4())
        self.tracer = tracer
        
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration: float = 0.0
        self.status = "success"  # success, error
        self.error: Optional[str] = None
        self.metadata: dict[str, Any] = {}
        
        # Stashes for nesting context restoration
        self._prev_trace_id: Optional[str] = None
        self._prev_span_id: Optional[str] = None

    def set_metadata(self, key: str, value: Any) -> None:
        """Store additional metadata fields on the span."""
        self.metadata[key] = value

    def __enter__(self) -> Span:
        from observability.tracing.context import (
            get_current_trace_id,
            get_current_span_id,
            set_current_trace_id,
            set_current_span_id,
        )
        self.start_time = time.time()
        
        # Backup current stack trace context
        self._prev_trace_id = get_current_trace_id()
        self._prev_span_id = get_current_span_id()
        
        # Set current execution context to this span
        set_current_trace_id(self.trace_id)
        set_current_span_id(self.span_id)
        
        if self.tracer:
            self.tracer._on_span_start(self)
            
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        
        if exc_type is not None:
            self.status = "error"
            self.error = str(exc_val)
            self.metadata["error.type"] = exc_type.__name__
            self.metadata["error.message"] = str(exc_val)
            
        from observability.tracing.context import (
            set_current_trace_id,
            set_current_span_id,
        )
        # Restore parent trace context
        set_current_trace_id(self._prev_trace_id)
        set_current_span_id(self._prev_span_id)
        
        if self.tracer:
            self.tracer._on_span_end(self)

    def to_dict(self) -> dict[str, Any]:
        """Convert span record to dictionary."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
        }
