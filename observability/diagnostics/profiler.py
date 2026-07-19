"""
Diagnostics Profiler for Realtimex.

Allows profiling code block execution times.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional


class ProfileBlock:
    """Context manager for profiling a specific block of code."""

    def __init__(self, profiler: Profiler, name: str) -> None:
        self.profiler = profiler
        self.name = name
        self.start_time = 0.0

    def __enter__(self) -> ProfileBlock:
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration = time.time() - self.start_time
        self.profiler.record_duration(self.name, duration)


class Profiler:
    """Simple thread-safe in-memory profiler for tracking execution performance."""

    def __init__(self) -> None:
        self._profiles: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def record_duration(self, name: str, duration: float) -> None:
        """Record execution duration of a named code block."""
        with self._lock:
            if name not in self._profiles:
                self._profiles[name] = []
            self._profiles[name].append(duration)
            if len(self._profiles[name]) > 1000:
                self._profiles[name].pop(0)

    def get_stats(self, name: str) -> dict[str, Any]:
        """Get stats (count, avg, min, max) for a named code block."""
        with self._lock:
            durations = self._profiles.get(name)
            if not durations:
                return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0}
            return {
                "count": len(durations),
                "avg": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
            }

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get stats for all profiled code blocks."""
        with self._lock:
            return {name: self.get_stats(name) for name in self._profiles}

    def clear(self) -> None:
        """Clear recorded profiling data."""
        with self._lock:
            self._profiles.clear()

    def profile(self, name: str) -> ProfileBlock:
        """Create a profile block context manager."""
        return ProfileBlock(self, name)
