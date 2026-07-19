"""
Tracing Context for Realtimex.

Handles thread-local trace ID and span ID storage.
"""

from __future__ import annotations

import threading
from typing import Optional

_local_context = threading.local()


def get_current_trace_id() -> Optional[str]:
    """Get trace ID associated with the current thread execution context."""
    return getattr(_local_context, "trace_id", None)


def set_current_trace_id(trace_id: Optional[str]) -> None:
    """Set trace ID associated with the current thread execution context."""
    _local_context.trace_id = trace_id


def get_current_span_id() -> Optional[str]:
    """Get active span ID of the current thread execution context."""
    return getattr(_local_context, "span_id", None)


def set_current_span_id(span_id: Optional[str]) -> None:
    """Set active span ID of the current thread execution context."""
    _local_context.span_id = span_id


def get_current_trace_context() -> dict[str, str]:
    """Get dictionary containing trace_id and span_id if set."""
    context = {}
    tid = get_current_trace_id()
    sid = get_current_span_id()
    if tid:
        context["trace_id"] = tid
    if sid:
        context["span_id"] = sid
    return context
