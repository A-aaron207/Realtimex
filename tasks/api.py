"""
Task API — public search and query API for Realtimex Tasks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tasks.exceptions import TaskNotFoundError
from tasks.states import TaskState
from tasks.task import Task, TaskPriority

if TYPE_CHECKING:
    from tasks.repository import TaskRepository


class TaskAPI:
    """
    Search and query interface exposing advanced lookup operations on tasks.
    """

    def __init__(self, repository: TaskRepository) -> None:
        """
        Initialize the Task Search API.

        Args:
            repository: The TaskRepository database instance.
        """
        self._repository = repository

    def find_by_id(self, task_id: str) -> Task:
        """
        Retrieve a task by ID.

        Args:
            task_id: The UUID of the task.

        Returns:
            The Task instance.

        Raises:
            TaskNotFoundError: If the task does not exist.
        """
        task = self._repository.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task with ID {task_id} not found.")
        return task

    def find_by_state(self, state: TaskState) -> list[Task]:
        """
        Find all tasks in a specific state.

        Args:
            state: The TaskState to filter by.

        Returns:
            List of matching Task instances.
        """
        return self._repository.find_by(lambda t: t.state == state)

    def find_by_priority(self, priority: TaskPriority) -> list[Task]:
        """
        Find all tasks of a specific priority.

        Args:
            priority: The TaskPriority to filter by.

        Returns:
            List of matching Task instances.
        """
        return self._repository.find_by(lambda t: t.priority == priority)

    def find_recent(self, limit: int = 10) -> list[Task]:
        """
        Retrieve the most recently updated tasks, ordered by updated_at descending.

        Args:
            limit: Maximum number of tasks to return.

        Returns:
            Sorted list of recent tasks.
        """
        all_tasks = self._repository.list_all()
        # Sort by updated_at descending
        sorted_tasks = sorted(all_tasks, key=lambda t: t.updated_at, reverse=True)
        return sorted_tasks[:limit]

    def find_failed(self) -> list[Task]:
        """
        Retrieve all tasks that have failed.

        Returns:
            List of failed tasks.
        """
        return self._repository.find_by(lambda t: t.state == TaskState.FAILED)
