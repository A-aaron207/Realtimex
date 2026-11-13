"""
Persistence layer for storing workflows on disk as JSON files.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from workflow.exceptions import WorkflowPersistenceError
from workflow.workflow import Workflow


class WorkflowPersistence:
    """
    Handles saving and loading workflows to/from disk as individual JSON files.
    """

    def __init__(self, directory: Path) -> None:
        """
        Initialize workflow persistence.

        Args:
            directory: Directory where workflow JSON files will be stored.
        """
        self._directory = directory
        self._lock = threading.Lock()
        self._ensure_directory()
        self._logger = logging.getLogger("realtimex.workflow.persistence")

    def _ensure_directory(self) -> None:
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise WorkflowPersistenceError(
                f"Failed to create workflow persistence directory '{self._directory}': {e}"
            ) from e

    def _filepath(self, workflow_id: str) -> Path:
        return self._directory / f"workflow_{workflow_id}.json"

    def save(self, workflow: Workflow) -> None:
        """
        Save a workflow to disk.

        Args:
            workflow: The Workflow instance.
        """
        filepath = self._filepath(workflow.workflow_id)
        with self._lock:
            try:
                self._ensure_directory()
                temp_filepath = filepath.with_suffix(".tmp")
                with open(temp_filepath, "w", encoding="utf-8") as f:
                    json.dump(workflow.to_dict(), f, indent=2, ensure_ascii=False)
                temp_filepath.replace(filepath)
            except Exception as e:
                self._logger.error("Failed to save workflow %s to %s: %s", workflow.workflow_id, filepath, e)
                raise WorkflowPersistenceError(f"Failed to persist workflow {workflow.workflow_id}: {e}") from e

    def load(self, workflow_id: str) -> Workflow | None:
        """
        Load a workflow from disk by ID.

        Args:
            workflow_id: Unique workflow ID.

        Returns:
            The loaded Workflow instance, or None if not found.
        """
        filepath = self._filepath(workflow_id)
        if not filepath.exists():
            return None

        with self._lock:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Workflow.from_dict(data)
            except Exception as e:
                self._logger.error("Failed to load workflow %s from %s: %s", workflow_id, filepath, e)
                raise WorkflowPersistenceError(f"Failed to load workflow {workflow_id}: {e}") from e

    def delete(self, workflow_id: str) -> bool:
        """
        Delete a workflow file from disk.

        Args:
            workflow_id: Unique workflow ID.

        Returns:
            True if deleted, False if file did not exist.
        """
        filepath = self._filepath(workflow_id)
        with self._lock:
            try:
                if filepath.exists():
                    filepath.unlink()
                    return True
                return False
            except Exception as e:
                self._logger.error("Failed to delete workflow file %s: %s", filepath, e)
                raise WorkflowPersistenceError(f"Failed to delete workflow persistence file {workflow_id}: {e}") from e

    def load_all(self) -> list[Workflow]:
        """
        Load all workflows from the persistence directory.

        Returns:
            A list of loaded Workflow objects.
        """
        workflows: list[Workflow] = []
        with self._lock:
            try:
                for file in self._directory.glob("workflow_*.json"):
                    try:
                        with open(file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        workflows.append(Workflow.from_dict(data))
                    except Exception as e:
                        self._logger.error("Corrupted workflow file detected at %s: %s", file, e)
            except Exception as e:
                raise WorkflowPersistenceError(f"Failed to scan workflow persistence directory: {e}") from e
        return workflows
