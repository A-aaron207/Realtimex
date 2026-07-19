"""
Disk-based task persistence layer storing tasks as individual JSON files.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from tasks.exceptions import TaskPersistenceError
from tasks.task import Task


class TaskPersistence:
    """
    Handles saving and loading tasks to/from disk as individual JSON files.
    """

    def __init__(self, directory: Path) -> None:
        """
        Initialize task persistence with a target directory.

        Args:
            directory: Directory where task JSON files will be stored.
        """
        self._directory = directory
        self._lock = threading.Lock()
        self._ensure_directory()
        self._logger = logging.getLogger("realtimex.tasks.persistence")

    def _ensure_directory(self) -> None:
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise TaskPersistenceError(
                f"Failed to create persistence directory '{self._directory}': {e}"
            ) from e

    def _filepath(self, task_id: str) -> Path:
        return self._directory / f"task_{task_id}.json"

    def save(self, task: Task) -> None:
        """
        Save a task to disk.

        Args:
            task: The Task instance to serialize and save.
        """
        filepath = self._filepath(task.task_id)
        with self._lock:
            try:
                temp_filepath = filepath.with_suffix(".tmp")
                with open(temp_filepath, "w", encoding="utf-8") as f:
                    json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)
                temp_filepath.replace(filepath)
            except Exception as e:
                self._logger.error("Failed to save task %s to %s: %s", task.task_id, filepath, e)
                raise TaskPersistenceError(f"Failed to persist task {task.task_id}: {e}") from e

    def load(self, task_id: str) -> Task | None:
        """
        Load a task from disk by ID.

        Args:
            task_id: Unique task identifier.

        Returns:
            The loaded Task object, or None if not found.
        """
        filepath = self._filepath(task_id)
        if not filepath.exists():
            return None

        with self._lock:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Task.from_dict(data)
            except Exception as e:
                self._logger.error("Failed to load task %s from %s: %s", task_id, filepath, e)
                raise TaskPersistenceError(f"Failed to load task {task_id}: {e}") from e

    def delete(self, task_id: str) -> bool:
        """
        Delete a task file from disk.

        Args:
            task_id: Unique task identifier.

        Returns:
            True if deleted, False if file did not exist.
        """
        filepath = self._filepath(task_id)
        with self._lock:
            try:
                if filepath.exists():
                    filepath.unlink()
                    return True
                return False
            except Exception as e:
                self._logger.error("Failed to delete task file %s: %s", filepath, e)
                raise TaskPersistenceError(f"Failed to delete task persistence file {task_id}: {e}") from e

    def load_all(self) -> list[Task]:
        """
        Load all tasks from the persistence directory.

        Returns:
            A list of loaded Task objects.
        """
        tasks: list[Task] = []
        with self._lock:
            try:
                for file in self._directory.glob("task_*.json"):
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        tasks.append(Task.from_dict(data))
                    except Exception as e:
                        # Log error but continue loading other files
                        self._logger.error("Corrupted task file detected at %s: %s", file, e)
            except Exception as e:
                raise TaskPersistenceError(f"Failed to scan task persistence directory: {e}") from e
        return tasks
