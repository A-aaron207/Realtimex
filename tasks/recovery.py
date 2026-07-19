"""
Task recovery orchestrator invoked during Kernel startup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from events.event import Event
from tasks.history import add_history_entry
from tasks.states import is_terminal_state

if TYPE_CHECKING:
    from events.bus import EventBus
    from tasks.repository import TaskRepository


class TaskRecovery:
    """
    Scans the repository for incomplete (active) tasks, restores them,
    adds a recovery log to their history, and announces their recovery
    through the Event Bus.
    """

    def __init__(
        self,
        repository: TaskRepository,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize Task Recovery.

        Args:
            repository: The TaskRepository.
            event_bus: The EventBus to publish recovery events.
            logger: The logger.
        """
        self._repository = repository
        self._event_bus = event_bus
        self._logger = logger

    def recover_tasks(self) -> int:
        """
        Identify all incomplete tasks in persistence/repository, preserve
        their state, update their execution history, and emit a TaskRecovered event.

        Returns:
            The number of recovered tasks.
        """
        self._logger.info("Starting Task Recovery sequence...")
        active_tasks = self._repository.list_active()
        recovered_count = 0

        for task in active_tasks:
            try:
                # Add history entry recording recovery
                updated_task = add_history_entry(
                    task=task,
                    event_type="TaskRecovered",
                    description=f"Task recovered during startup in state: {task.state.value}",
                )
                self._repository.update(updated_task)

                # Emit TaskRecovered event
                self._event_bus.publish(
                    Event(
                        name="TaskRecovered",
                        source="tasks.recovery",
                        task_id=task.task_id,
                        payload={
                            "task_id": task.task_id,
                            "goal": task.goal,
                            "state": task.state.value,
                            "priority": task.priority.value,
                        },
                    )
                )
                self._logger.info("Successfully recovered task %s (state: %s)", task.task_id, task.state.value)
                recovered_count += 1
            except Exception as e:
                self._logger.exception("Failed to recover task %s: %s", task.task_id, e)

        self._logger.info("Task Recovery complete. Recovered %d tasks.", recovered_count)
        return recovered_count
