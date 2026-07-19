"""
Logging Manager for Realtimex.

Coordinates formatters, sinks, filters, and structured logging.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

from observability.logging.formatter import JSONFormatter, TextFormatter
from observability.logging.sinks import create_console_sink
from observability.exceptions import LoggingError


class LoggingManager:
    """
    Central log management subsystem for Realtimex.
    
    Provides thread-local context binding, log level controls,
    and routing of structured logs to multiple sinks.
    """

    def __init__(
        self,
        name: str = "realtimex",
        level: str = "INFO",
        format_type: str = "text",
        event_bus: Any = None,
    ) -> None:
        """
        Initialize Logging Manager.
        
        Args:
            name: Logger name
            level: Default log level
            format_type: Format style ('text', 'json')
            event_bus: Optional Event Bus for emitting LogWritten events
        """
        self.name = name
        self.logger = logging.getLogger(name)
        # Clear existing handlers to prevent duplicate logging
        for h in list(self.logger.handlers):
            self.logger.removeHandler(h)
        self.logger.setLevel(level.upper())
        self.format_type = format_type
        self.bus = event_bus
        
        self._lock = threading.RLock()
        self._local_context = threading.local()

        # Add initial console handler
        self._setup_default_handler()

    def _setup_default_handler(self) -> None:
        """Add console output sink with configured formatter."""
        if not self.logger.handlers:
            sink = create_console_sink()
            formatter = JSONFormatter() if self.format_type == "json" else TextFormatter()
            sink.setFormatter(formatter)
            self.logger.addHandler(sink)

    def set_level(self, level: str) -> None:
        """Set logging severity threshold."""
        with self._lock:
            self.logger.setLevel(level.upper())

    def add_sink(self, sink: logging.Handler, format_type: Optional[str] = None) -> None:
        """Add log sink with specific format style."""
        with self._lock:
            fmt = format_type or self.format_type
            formatter = JSONFormatter() if fmt == "json" else TextFormatter()
            sink.setFormatter(formatter)
            self.logger.addHandler(sink)

    def remove_sink(self, sink: logging.Handler) -> None:
        """Remove log sink."""
        with self._lock:
            self.logger.removeHandler(sink)

    # --- Context Binding ---

    def bind_context(self, **kwargs: Any) -> None:
        """Bind trace or execution context to thread-local logs."""
        if not hasattr(self._local_context, "data"):
            self._local_context.data = {}
        self._local_context.data.update(kwargs)

    def unbind_context(self, *keys: str) -> None:
        """Remove keys from thread-local logs context."""
        if hasattr(self._local_context, "data"):
            for key in keys:
                self._local_context.data.pop(key, None)

    def clear_context(self) -> None:
        """Clear thread-local logs context."""
        if hasattr(self._local_context, "data"):
            self._local_context.data.clear()

    def get_context(self) -> dict[str, Any]:
        """Get copy of active thread-local logs context."""
        if hasattr(self._local_context, "data"):
            return self._local_context.data.copy()
        return {}

    # --- Structured Logging API ---

    def log(
        self,
        level: str | int,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log message with custom structured context data."""
        try:
            level_num = logging.getLevelName(level.upper()) if isinstance(level, str) else level
            if not isinstance(level_num, int):
                level_num = logging.INFO

            # Merge context fields
            merged_context = self.get_context()
            if context:
                merged_context.update(context)

            # Auto-retrieve trace ID from active spans context (if loaded)
            try:
                from observability.tracing.context import get_current_trace_context
                trace_ctx = get_current_trace_context()
                if trace_ctx:
                    merged_context.update(trace_ctx)
            except ImportError:
                pass

            # Log
            self.logger.log(level_num, message, extra={"context": merged_context})

            # Emit LogWritten event if event bus available
            if self.bus:
                try:
                    from events.event import Event, EventPriority
                    self.bus.publish(
                        Event(
                            name="LogWritten",
                            source="observability.logging",
                            payload={
                                "level": logging.getLevelName(level_num),
                                "message": message,
                                "context": merged_context,
                            },
                            priority=EventPriority.NORMAL,
                        )
                    )
                except Exception:
                    pass

        except Exception as e:
            raise LoggingError(f"Log operation failed: {e}") from e

    def debug(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        self.log(logging.DEBUG, message, context)

    def info(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        self.log(logging.INFO, message, context)

    def warning(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        self.log(logging.WARNING, message, context)

    def error(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        self.log(logging.ERROR, message, context)

    def critical(self, message: str, context: Optional[dict[str, Any]] = None) -> None:
        self.log(logging.CRITICAL, message, context)
