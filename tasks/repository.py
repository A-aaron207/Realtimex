"""
Thread-safe repository for in-memory caching and retrieval of tasks, backed by persistence.
"""

from __future__ import annotations

import threading
from typing import Callable

from tasks.exceptions import TaskNotFoundError
from tasks.persistence import TaskPersistence
from tasks.states import TaskState, is_terminal_state
from tasks.task import Task, TaskPriority


class TaskRepository:
    """
    Thread-safe repository for tasks. Handles memory caching and delegates
    persistence operations to TaskPersistence.
    """

    def __init__(self, persistence: TaskPersistence) -> None:
        """
        Initialize the repository.

        Args:
            persistence: The TaskPersistence instance used to save/load tasks.
        """
        self._persistence = persistence
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()
        self._load_initial_tasks()

    def _load_initial_tasks(self) -> None:
        """Load all tasks from persistence to memory cache."""
        all_persisted = self._persistence.load_all()
        for task in all_persisted:
            self._tasks[task.task_id] = task

    def add(self, task: Task) -> None:
        """
        Add a new task to memory cache and persist it.

        Args:
            task: The Task to add.
        """
        with self._lock:
            self._tasks[task.task_id] = task
            self._persistence.save(task)

    def get(self, task_id: str) -> Task | None:
        """
        Get a task by ID.

        Args:
            task_id: The UUID of the task.

        Returns:
            The Task instance or None if not found.
        """
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task: Task) -> None:
        """
        Update a task in memory cache and persist it.

        Args:
            task: The updated Task instance.
        """
        with self._lock:
            if task.task_id not in self._tasks:
                raise TaskNotFoundError(f"Task with ID {task.task_id} not found in repository.")
            self._tasks[task.task_id] = task
            self._persistence.save(task)

    def delete(self, task_id: str) -> bool:
        """
        Delete a task from memory cache and disk.

        Args:
            task_id: The UUID of the task.

        Returns:
            True if the task was found and deleted, False otherwise.
        """
        with self._lock:
            exists_in_mem = task_id in self._tasks
            if exists_in_mem:
                del self._tasks[task_id]
            exists_on_disk = self._persistence.delete(task_id)
            return exists_in_mem or exists_on_disk

    def list_all(self) -> list[Task]:
        """Return a copy of all tasks in the repository."""
        with self._lock:
            return list(self._tasks.values())

    def list_active(self) -> list[Task]:
        """Return all tasks that are in a non-terminal state."""
        with self._lock:
            return [t for t in self._tasks.values() if not is_terminal_state(t.state)]

    def list_completed(self) -> list[Task]:
        """Return all tasks that are in a terminal state (COMPLETED, FAILED, CANCELLED)."""
        with self._lock:
            return [t for t in self._tasks.values() if is_terminal_state(t.state)]

    def find_by(self, predicate: Callable[[Task], bool]) -> list[Task]:
        """
        Find tasks matching a specific predicate.

        Args:
            predicate: A callable that returns True for matching tasks.

        Returns:
            List of matching tasks.
        """
        with self._lock:
            return [t for t in self._tasks.values() if predicate(t)]
