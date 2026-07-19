"""
Realtimex Kernel Startup Profiler.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProfileEntry:
    """Representation of a subsystem boot timing entry."""
    name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    dependencies: list[str] = field(default_factory=list)
    thread_name: str = ""
    status: str = "PENDING"  # RUNNING, SUCCESS, FAILURE
    error_message: str | None = None


class BootProfiler:
    """
    Subsystem timing tracker that measures startup durations and produces boot reports.
    """

    def __init__(self) -> None:
        """Initialize the boot profiler."""
        self._entries: dict[str, ProfileEntry] = {}
        self._lock = threading.RLock()
        self._total_start = time.perf_counter()
        self._total_duration_ms: float | None = None

    def start(self, name: str, dependencies: list[str] | None = None) -> None:
        """Record the start of a subsystem boot phase."""
        with self._lock:
            self._entries[name] = ProfileEntry(
                name=name,
                start_time=time.perf_counter(),
                dependencies=dependencies or [],
                thread_name=threading.current_thread().name,
                status="RUNNING"
            )

    def stop(self, name: str, success: bool = True, error_message: str | None = None) -> None:
        """Record the end of a subsystem boot phase."""
        with self._lock:
            entry = self._entries.get(name)
            if entry:
                entry.end_time = time.perf_counter()
                entry.duration_ms = (entry.end_time - entry.start_time) * 1000
                entry.status = "SUCCESS" if success else "FAILURE"
                entry.error_message = error_message

    def finish_boot(self) -> None:
        """Finish overall boot profiling and compute total duration."""
        with self._lock:
            total_end = time.perf_counter()
            self._total_duration_ms = (total_end - self._total_start) * 1000

    def generate_report(self) -> str:
        """Generate a human-readable Markdown/Text boot report."""
        with self._lock:
            lines = [
                "Boot Report",
                "──────────────────────────────"
            ]
            
            # Sort entries by their start time
            sorted_entries = sorted(self._entries.values(), key=lambda e: e.start_time)
            
            total_accounted_ms = 0.0
            for entry in sorted_entries:
                duration_str = f"{entry.duration_ms:.1f} ms" if entry.duration_ms is not None else "N/A"
                if entry.status == "FAILURE":
                    duration_str += " (FAILED)"
                
                dots = "." * max(2, 30 - len(entry.name))
                lines.append(f"{entry.name}{dots}{duration_str}")
                
                if entry.duration_ms is not None:
                    total_accounted_ms += entry.duration_ms
            
            lines.append("──────────────────────────────")
            total_str = f"{self._total_duration_ms:.1f} ms" if self._total_duration_ms is not None else f"{total_accounted_ms:.1f} ms"
            dots = "." * max(2, 30 - len("Total"))
            lines.append(f"Total{dots}{total_str}")
            
            return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert all profiling data to a dictionary."""
        with self._lock:
            return {
                "total_duration_ms": self._total_duration_ms,
                "entries": {
                    name: {
                        "start_time": entry.start_time,
                        "end_time": entry.end_time,
                        "duration_ms": entry.duration_ms,
                        "dependencies": entry.dependencies,
                        "thread": entry.thread_name,
                        "status": entry.status,
                        "error_message": entry.error_message,
                    }
                    for name, entry in self._entries.items()
                }
            }
