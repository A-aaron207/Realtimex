"""
Log Formatter for Realtimex.

Handles structured and JSON log formatting.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        # Extract base fields
        timestamp = datetime.fromtimestamp(record.created, timezone.utc).isoformat()
        log_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Include context-aware fields if present
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            log_data["context"] = context
            
        # Exception details
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data, default=str)


class TextFormatter(logging.Formatter):
    """Formats log records as human-readable text."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        base = f"{timestamp} [{record.levelname}] {record.name}: {record.getMessage()}"
        
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            context_str = " ".join(f"{k}={v}" for k, v in context.items())
            base += f" | {context_str}"
            
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
            
        return base
