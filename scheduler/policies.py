"""
Pluggable Scheduling Policies determining sorting and execution priority order.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workflow.step import WorkflowStep
    from tasks.task import TaskPriority


@dataclass(frozen=True)
class QueueItem:
    """
    Wrapper around WorkflowStep mapping metadata required for policy sorting.
    """
    step: WorkflowStep
    priority: TaskPriority
    queued_at: datetime
    ready_at: datetime


class SchedulingPolicy(ABC):
    """
    Abstract Base Class for scheduling selection policies.
    """

    @abstractmethod
    def sort(self, items: list[QueueItem]) -> list[QueueItem]:
        """
        Sort list of QueueItem instances according to policy guidelines.

        Args:
            items: Unsorted QueueItem list.

        Returns:
            Sorted QueueItem list in order of scheduling preference (highest priority first).
        """
        raise NotImplementedError


class FIFOPolicy(SchedulingPolicy):
    """
    First-In-First-Out policy: orders strictly by queued timestamp.
    """

    def sort(self, items: list[QueueItem]) -> list[QueueItem]:
        return sorted(items, key=lambda item: item.queued_at)


class PriorityPolicy(SchedulingPolicy):
    """
    Priority-based policy: orders by priority level descending, then FIFO.
    """

    def sort(self, items: list[QueueItem]) -> list[QueueItem]:
        # Priority is an IntEnum, we want highest value first, so negate or reverse.
        # Python sort is stable, so we can sort by queued_at ascending, then priority descending.
        # Or sort with key: (-int(item.priority), item.queued_at)
        return sorted(items, key=lambda item: (-int(item.priority), item.queued_at))


class EarliestReadyPolicy(SchedulingPolicy):
    """
    Earliest Ready policy: orders by ready timestamp ascending (oldest ready first), then priority.
    """

    def sort(self, items: list[QueueItem]) -> list[QueueItem]:
        return sorted(items, key=lambda item: (item.ready_at, -int(item.priority)))
