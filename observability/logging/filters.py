"""
Log Filters for Realtimex.

Allows filtering log records by context or key-value criteria.
"""

from __future__ import annotations

import logging
from typing import Any


class ContextFilter(logging.Filter):
    """Filters logs based on context keys and values."""

    def __init__(self, key: str, value: Any = None) -> None:
        """
        Initialize ContextFilter.
        
        Args:
            key: Context key to check
            value: Optional expected value for the key
        """
        super().__init__()
        self.key = key
        self.value = value

    def filter(self, record: logging.LogRecord) -> bool:
        context = getattr(record, "context", None)
        if not isinstance(context, dict):
            return False
        
        if self.key not in context:
            return False
            
        if self.value is not None:
            return context[self.key] == self.value
            
        return True


class LevelRangeFilter(logging.Filter):
    """Filters logs to be within a specific level range (inclusive)."""

    def __init__(self, min_level: int, max_level: int) -> None:
        """
        Initialize LevelRangeFilter.
        
        Args:
            min_level: Minimum log level integer value
            max_level: Maximum log level integer value
        """
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return self.min_level <= record.levelno <= self.max_level
