"""
Cache implementation for Realtimex Policy Engine.

Provides simple, thread-safe storage for compiled policies and evaluation outcomes.
"""

from __future__ import annotations

import threading
from typing import Any, Optional


class PolicyCache:
    """Thread-safe in-memory cache for compiled evaluation states and decisions."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value."""
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        with self._lock:
            self._cache[key] = value

    def clear(self) -> None:
        """Invalidate/clear all cached entries."""
        with self._lock:
            self._cache.clear()
