"""
Thread-safe Dispatch Queue for storing pending workflow steps.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from events.event import Event
from scheduler.exceptions import QueueError
from scheduler.policies import QueueItem

if TYPE_CHECKING:
    from workflow.step import WorkflowStep
    from tasks.task import TaskPriority
    from scheduler.policies import SchedulingPolicy


class DispatchQueue:
    """
    Thread-safe scheduling queue supporting prioritization, pluggable policies,
    blocking pops, and structural inspection.
    """

    def __init__(self, event_bus: Any) -> None:
        """
        Initialize the queue.

        Args:
            event_bus: The EventBus or EventManager to emit events.
        """
        self._event_bus = event_bus
        self._items: list[QueueItem] = []
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

    def push(
        self,
        step: WorkflowStep,
        priority: TaskPriority,
        ready_at: datetime | None = None,
    ) -> None:
        """
        Enqueue a step.

        Args:
            step: The WorkflowStep instance.
            priority: The TaskPriority of the parent task.
            ready_at: Timestamp when this step became ready. Defaults to now.
        """
        now = datetime.now(timezone.utc)
        item = QueueItem(
            step=step,
            priority=priority,
            queued_at=now,
            ready_at=ready_at or now,
        )

        with self._lock:
            # Check if step is already enqueued
            if any(existing.step.step_id == step.step_id for existing in self._items):
                return  # Idempotent push

            self._items.append(item)
            self._condition.notify_all()

        # Emit StepQueued
        self._event_bus.publish(
            Event(
                name="StepQueued",
                source="scheduler.queue",
                task_id=step.workflow_id,  # Associate with workflow
                payload={"step_id": step.step_id, "priority": priority.value},
            )
        )

    def pop(
        self,
        policy: SchedulingPolicy,
        timeout: float | None = None,
    ) -> QueueItem | None:
        """
        Retrieve and remove the highest priority item from the queue.
        Blocks if the queue is empty.

        Args:
            policy: Pluggable SchedulingPolicy.
            timeout: Timeout in seconds for blocking pop.

        Returns:
            The popped QueueItem, or None if timed out.
        """
        with self._lock:
            start_time = time.time()
            while not self._items:
                # Wait for items to arrive
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return None
                    self._condition.wait(timeout=remaining)
                else:
                    self._condition.wait()

            # Sort candidate list according to active policy rules
            sorted_items = policy.sort(self._items)
            selected = sorted_items[0]
            
            # Remove from original storage
            self._items.remove(selected)

            if not self._items:
                # Emit QueueEmpty
                self._event_bus.publish(
                    Event(
                        name="QueueEmpty",
                        source="scheduler.queue",
                        payload={},
                    )
                )

            return selected

    def remove(self, step_id: str) -> bool:
        """
        Remove a step from the queue by ID (cancellation helper).

        Returns:
            True if removed, False otherwise.
        """
        with self._lock:
            for item in list(self._items):
                if item.step.step_id == step_id:
                    self._items.remove(item)
                    return True
            return False

    def clear(self) -> None:
        """Clear all items."""
        with self._lock:
            self._items.clear()

    def statistics(self) -> dict[str, Any]:
        """
        Gather metrics on queue contents.
        """
        with self._lock:
            total = len(self._items)
            priorities = {}
            for item in self._items:
                p_name = item.priority.name
                priorities[p_name] = priorities.get(p_name, 0) + 1

            return {
                "length": total,
                "priority_breakdown": priorities,
            }

    def list_items(self) -> list[QueueItem]:
        """Return a copy of the queue items for inspection."""
        with self._lock:
            return list(self._items)

