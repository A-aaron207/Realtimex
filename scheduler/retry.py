"""
Retry Manager coordinating automatic task execution retries and backoff timings.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, TYPE_CHECKING

from events.event import Event

if TYPE_CHECKING:
    from workflow.step import WorkflowStep


class RetryManager:
    """
    Tracks failure retry counts and handles delayed enqueuing of retried workflow steps
    using exponential backoff.
    """

    def __init__(
        self,
        event_bus: Any,
        logger: logging.Logger,
        max_retries: int = 3,
        base_delay: float = 1.0,
        use_exponential_backoff: bool = True,
    ) -> None:
        """
        Initialize the Retry Manager.

        Args:
            event_bus: Global EventBus.
            logger: Diagnostics logger.
            max_retries: Max number of allowed retry attempts per step.
            base_delay: Base delay in seconds.
            use_exponential_backoff: Whether to use exponential delay scaling.
        """
        self._event_bus = event_bus
        self._logger = logger
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.use_exponential_backoff = use_exponential_backoff
        self._attempts: dict[str, int] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.RLock()

    def should_retry(self, step: WorkflowStep) -> bool:
        """
        Check if a step can be retried.
        """
        with self._lock:
            attempt = self._attempts.get(step.step_id, 0)
            return attempt < self.max_retries

    def get_attempts(self, step_id: str) -> int:
        """Get current retry attempt count for a step."""
        with self._lock:
            return self._attempts.get(step_id, 0)

    def clear(self, step_id: str) -> None:
        """Clear attempt stats for a step."""
        with self._lock:
            if step_id in self._attempts:
                del self._attempts[step_id]

    def schedule_retry(
        self,
        step: WorkflowStep,
        enqueue_fn: Callable[[WorkflowStep, datetime], None],
    ) -> float:
        """
        Increment the attempt counter, calculate backoff delay, and schedule a thread
        Timer to re-enqueue the step after the delay.

        Args:
            step: The WorkflowStep instance.
            enqueue_fn: Callback of the form enqueue(step, ready_at) to insert back to queue.

        Returns:
            The delay in seconds scheduled.
        """
        with self._lock:
            attempt = self._attempts.get(step.step_id, 0) + 1
            self._attempts[step.step_id] = attempt

        # Calculate delay
        if self.use_exponential_backoff:
            delay = self.base_delay * (2 ** (attempt - 1))
        else:
            delay = self.base_delay

        self._logger.info(
            "Scheduling retry attempt %d/%d for step %s in %.2fs",
            attempt,
            self.max_retries,
            step.step_id,
            delay,
        )

        # Emit RetryScheduled
        self._event_bus.publish(
            Event(
                name="RetryScheduled",
                source="scheduler.retry",
                task_id=step.workflow_id,
                payload={
                    "step_id": step.step_id,
                    "attempt": attempt,
                    "max_retries": self.max_retries,
                    "delay_seconds": delay,
                },
            )
        )

        def re_enqueue():
            with self._lock:
                self._timers.pop(step.step_id, None)
            now = datetime.now(timezone.utc)
            enqueue_fn(step, now)
            self._logger.info("Step %s re-enqueued for retry after delay", step.step_id)

        # Start background timer thread
        timer = threading.Timer(delay, re_enqueue)
        timer.name = f"RetryTimer-{step.step_id}"
        timer.daemon = True
        
        with self._lock:
            old_timer = self._timers.get(step.step_id)
            if old_timer:
                try:
                    old_timer.cancel()
                except Exception:
                    pass
            self._timers[step.step_id] = timer
            
        timer.start()

        return delay

    def cancel_all(self) -> None:
        """Cancel all pending retry timers."""
        with self._lock:
            for timer in list(self._timers.values()):
                try:
                    timer.cancel()
                except Exception:
                    pass
            self._timers.clear()
