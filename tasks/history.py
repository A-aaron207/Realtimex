"""
Helpers for managing a Task's internal execution history.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from tasks.task import Task, TaskHistoryEntry


def add_history_entry(
    task: Task,
    event_type: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> Task:
    """
    Append a history entry to the task and return a new Task instance.

    This automatically updates the task's ``updated_at`` field.

    Args:
        task: The current Task instance.
        event_type: The semantic category of the entry (e.g. "state_transition").
        description: A human-readable message.
        metadata: Optional dictionary with additional event context.

    Returns:
        A new Task instance containing the appended history entry.
    """
    now = datetime.now(timezone.utc)
    new_entry = TaskHistoryEntry(
        timestamp=now,
        event_type=event_type,
        description=description,
        metadata=metadata or {},
    )

    new_history = list(task.history) + [new_entry]

    return dataclasses.replace(
        task,
        history=new_history,
        updated_at=now,
    )
