"""
Task Manager — public coordinator and state engine for Realtimex Tasks.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from events.event import Event
from tasks.exceptions import TaskNotFoundError, TaskValidationError
from tasks.history import add_history_entry
from tasks.states import TaskState, validate_transition
from tasks.task import Task, TaskPriority

if TYPE_CHECKING:
    from events.bus import EventBus
    from tasks.repository import TaskRepository


class TaskManager:
    """
    Coordinates creation, lifecycle management, and querying of tasks.

    The Task Manager publishes appropriate event system notifications
    for all status and progress changes, and coordinates cache updates
    and disk persistence.
    """

    def __init__(
        self,
        repository: TaskRepository,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize the Task Manager.

        Args:
            repository: The TaskRepository database abstraction.
            event_bus: The EventBus instance for event emissions.
            logger: The logger instance.
        """
        self._repository = repository
        self._event_bus = event_bus
        self._logger = logger
        self._lock = threading.RLock()

    def create_task(
        self,
        goal: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """
        Create a new task, persist it, and announce its creation.

        Args:
            goal: The core objective/request of the task.
            priority: Execution priority level.
            metadata: Optional user/context metadata.

        Returns:
            The created Task instance.
        """
        if not goal.strip():
            raise TaskValidationError("Task goal cannot be empty.")

        with self._lock:
            # Construct initial task
            task = Task(
                goal=goal,
                priority=priority,
                metadata=metadata or {},
            )

            # Record creation in history
            task = add_history_entry(
                task=task,
                event_type="TaskCreated",
                description=f"Task created with goal: '{goal}'",
            )

            # Add to repository (saves to cache + persistence)
            self._repository.add(task)

            # Publish event
            self._event_bus.publish(
                Event(
                    name="TaskCreated",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload=task.to_dict(),
                )
            )

            self._logger.info("Created task %s: '%s' (priority: %s)", task.task_id, goal, priority.name)
            return task

    def get_task(self, task_id: str) -> Task:
        """
        Retrieve a task by its unique ID.

        Args:
            task_id: The UUID of the task.

        Returns:
            The Task instance.

        Raises:
            TaskNotFoundError: If the task is not found.
        """
        with self._lock:
            task = self._repository.get(task_id)
            if task is None:
                raise TaskNotFoundError(f"Task with ID {task_id} not found.")
            return task

    def update_state(self, task_id: str, new_state: TaskState) -> Task:
        """
        Transition a task to a new state, validating the transition.

        Args:
            task_id: The UUID of the task.
            new_state: The target TaskState.

        Returns:
            The updated Task instance.
        """
        with self._lock:
            task = self.get_task(task_id)
            old_state = task.state

            if old_state == new_state:
                return task

            # Validate under state lifecycle machine rules
            validate_transition(old_state, new_state)

            # Prepare history entry description
            desc = f"State transitioned from {old_state.value} to {new_state.value}"
            updated_task = add_history_entry(
                task=task,
                event_type="StateTransition",
                description=desc,
                metadata={"old_state": old_state.value, "new_state": new_state.value},
            )

            # Replace the state property
            import dataclasses
            updated_task = dataclasses.replace(
                updated_task,
                state=new_state,
                updated_at=datetime.now(timezone.utc),
            )

            self._repository.update(updated_task)

            # Emit state-specific events if matching
            self._emit_state_change_events(updated_task, old_state, new_state)

            self._logger.info("Task %s state updated: %s -> %s", task_id, old_state.value, new_state.value)
            return updated_task

    def _emit_state_change_events(self, task: Task, old_state: TaskState, new_state: TaskState) -> None:
        """Emit specific and general events for task state updates."""
        # Generic update event
        self._event_bus.publish(
            Event(
                name="TaskUpdated",
                source="tasks.manager",
                task_id=task.task_id,
                payload=task.to_dict(),
            )
        )

        # Specific events
        if new_state == TaskState.PAUSED:
            self._event_bus.publish(
                Event(
                    name="TaskPaused",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload={"task_id": task.task_id},
                )
            )
        elif old_state == TaskState.PAUSED and new_state in {TaskState.QUEUED, TaskState.RUNNING}:
            self._event_bus.publish(
                Event(
                    name="TaskResumed",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload={"task_id": task.task_id, "new_state": new_state.value},
                )
            )
        elif new_state == TaskState.CANCELLED:
            self._event_bus.publish(
                Event(
                    name="TaskCancelled",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload={"task_id": task.task_id},
                )
            )
        elif new_state == TaskState.COMPLETED:
            self._event_bus.publish(
                Event(
                    name="TaskCompleted",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload={"task_id": task.task_id},
                )
            )
        elif new_state == TaskState.FAILED:
            self._event_bus.publish(
                Event(
                    name="TaskFailed",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload={"task_id": task.task_id},
                )
            )

    def pause_task(self, task_id: str) -> Task:
        """
        Pause a task. Must be in a running or queued state.

        Args:
            task_id: The UUID of the task.

        Returns:
            The updated Task instance.
        """
        return self.update_state(task_id, TaskState.PAUSED)

    def resume_task(self, task_id: str) -> Task:
        """
        Resume a paused task (moves to QUEUED).

        Args:
            task_id: The UUID of the task.

        Returns:
            The updated Task instance.
        """
        # Resume to QUEUED so Scheduler picks it up
        return self.update_state(task_id, TaskState.QUEUED)

    def cancel_task(self, task_id: str) -> Task:
        """
        Cancel a task.

        Args:
            task_id: The UUID of the task.

        Returns:
            The updated Task instance.
        """
        return self.update_state(task_id, TaskState.CANCELLED)

    def update_progress(self, task_id: str, progress: int) -> Task:
        """
        Update a task's completion progress percentage (0-100).

        Args:
            task_id: The UUID of the task.
            progress: Progress percentage.

        Returns:
            The updated Task instance.
        """
        if not (0 <= progress <= 100):
            raise TaskValidationError(f"Progress must be between 0 and 100. Got: {progress}")

        with self._lock:
            task = self.get_task(task_id)
            old_progress = task.progress

            if old_progress == progress:
                return task

            updated_task = add_history_entry(
                task=task,
                event_type="ProgressUpdate",
                description=f"Progress updated from {old_progress}% to {progress}%",
                metadata={"old_progress": old_progress, "new_progress": progress},
            )

            import dataclasses
            updated_task = dataclasses.replace(
                updated_task,
                progress=progress,
                updated_at=datetime.now(timezone.utc),
            )

            self._repository.update(updated_task)

            # Publish ProgressUpdated
            self._event_bus.publish(
                Event(
                    name="ProgressUpdated",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload={"task_id": task.task_id, "old_progress": old_progress, "new_progress": progress},
                )
            )
            # Publish TaskUpdated
            self._event_bus.publish(
                Event(
                    name="TaskUpdated",
                    source="tasks.manager",
                    task_id=task.task_id,
                    payload=updated_task.to_dict(),
                )
            )

            self._logger.info("Task %s progress updated to %d%%", task_id, progress)
            return updated_task

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task from repository and persistence.

        Args:
            task_id: The UUID of the task.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            # We want to publish before losing cache if found
            task = self._repository.get(task_id)
            deleted = self._repository.delete(task_id)

            if deleted:
                self._event_bus.publish(
                    Event(
                        name="TaskDeleted",
                        source="tasks.manager",
                        task_id=task_id,
                        payload={"task_id": task_id, "goal": task.goal if task else ""},
                    )
                )
                self._logger.info("Deleted task %s", task_id)
            return deleted

    def list_tasks(
        self,
        active_only: bool = False,
        completed_only: bool = False,
    ) -> list[Task]:
        """
        List tasks stored in the repository.

        Args:
            active_only: Filter by active (non-terminal) tasks.
            completed_only: Filter by completed (terminal) tasks.

        Returns:
            List of tasks.
        """
        with self._lock:
            if active_only:
                return self._repository.list_active()
            if completed_only:
                return self._repository.list_completed()
            return self._repository.list_all()
