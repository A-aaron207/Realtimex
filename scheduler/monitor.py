"""
Scheduler Monitor aggregating runtime performance metrics and wait/execution times.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable


class SchedulerMonitor:
    """
    Thread-safe diagnostics accumulator tracking queues, running jobs, wait times,
    execution times, and dispatch rates.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._start_time = datetime.now(timezone.utc)
        self._total_dispatched = 0
        self._total_completed = 0
        self._total_failed = 0
        self._running_jobs: set[str] = set()
        self._wait_times: list[float] = []
        self._execution_times: list[float] = []

    def record_queued(self, step_id: str) -> None:
        """Record step insertion."""
        pass

    def record_dispatched(self, step_id: str, wait_time: float) -> None:
        """Record step dispatch start."""
        with self._lock:
            self._total_dispatched += 1
            self._running_jobs.add(step_id)
            self._wait_times.append(wait_time)

    def record_completed(self, step_id: str, exec_time: float) -> None:
        """Record successful execution completion."""
        with self._lock:
            self._total_completed += 1
            self._running_jobs.discard(step_id)
            self._execution_times.append(exec_time)

    def record_failed(self, step_id: str) -> None:
        """Record execution failure."""
        with self._lock:
            self._total_failed += 1
            self._running_jobs.discard(step_id)

    def metrics(
        self,
        queue_length: int,
        worker_counts_provider: Callable[[], tuple[int, int]],
    ) -> dict[str, Any]:
        """
        Compile diagnostics metrics report.

        Args:
            queue_length: Current count of items in Dispatch Queue.
            worker_counts_provider: Callback returning (idle_workers, busy_workers).
        """
        with self._lock:
            idle_workers, busy_workers = worker_counts_provider()
            elapsed_seconds = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            # Dispatch Rate: dispatches per second (or per minute)
            dispatch_rate = self._total_dispatched / elapsed_seconds if elapsed_seconds > 0 else 0.0

            avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0.0
            avg_exec = sum(self._execution_times) / len(self._execution_times) if self._execution_times else 0.0

            return {
                "queue_length": queue_length,
                "running_jobs_count": len(self._running_jobs),
                "running_jobs": list(self._running_jobs),
                "idle_workers": idle_workers,
                "busy_workers": busy_workers,
                "average_wait_time_s": round(avg_wait, 3),
                "average_execution_time_s": round(avg_exec, 3),
                "dispatch_rate_per_s": round(dispatch_rate, 3),
                "total_dispatched": self._total_dispatched,
                "total_completed": self._total_completed,
                "total_failed": self._total_failed,
            }
