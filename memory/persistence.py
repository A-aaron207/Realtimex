"""
Persistence layer for serializing and storing Memory Records to disk.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from memory.exceptions import MemoryPersistenceError
from memory.registry import MemoryRecord, MemoryScope


class MemoryPersistence(ABC):
    """
    Abstract interface for memory persistence backends.
    """

    @abstractmethod
    def save(self, scope: MemoryScope, owner: str, records: list[MemoryRecord]) -> None:
        """Save a list of memory records for a given scope and owner."""
        pass

    @abstractmethod
    def load(self, scope: MemoryScope, owner: str) -> list[MemoryRecord]:
        """Load a list of memory records for a given scope and owner."""
        pass

    @abstractmethod
    def delete(self, scope: MemoryScope, owner: str) -> None:
        """Delete all memory records for a given scope and owner."""
        pass


class FileMemoryPersistence(MemoryPersistence):
    """
    JSON file-based memory persistence backend.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            # Create subdirs for task and global partitioning
            (self.directory / "global").mkdir(parents=True, exist_ok=True)
            (self.directory / "task").mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise MemoryPersistenceError(f"Failed to create persistence directory: {e}") from e

    def _get_path(self, scope: MemoryScope, owner: str) -> Path:
        if scope == "global":
            # All global memories stored together
            return self.directory / "global" / "global_store.json"
        elif scope == "task":
            # Task memories are partitioned by task ID
            clean_owner = "".join(c for c in owner if c.isalnum() or c in "-_")
            return self.directory / "task" / f"{clean_owner}.json"
        else:
            raise MemoryPersistenceError(f"Scope '{scope}' is not persistable on disk.")

    def save(self, scope: MemoryScope, owner: str, records: list[MemoryRecord]) -> None:
        if scope == "ephemeral":
            return  # Ephemeral memory is never saved to disk

        file_path = self._get_path(scope, owner)
        try:
            serialized = [rec.to_dict() for rec in records]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise MemoryPersistenceError(f"Failed to persist memory records to {file_path}: {e}") from e

    def load(self, scope: MemoryScope, owner: str) -> list[MemoryRecord]:
        if scope == "ephemeral":
            return []

        file_path = self._get_path(scope, owner)
        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise MemoryPersistenceError(f"Malformed memory data file: {file_path}")
            return [MemoryRecord.from_dict(d) for d in data]
        except Exception as e:
            raise MemoryPersistenceError(f"Failed to load memory records from {file_path}: {e}") from e

    def delete(self, scope: MemoryScope, owner: str) -> None:
        if scope == "ephemeral":
            return

        file_path = self._get_path(scope, owner)
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                raise MemoryPersistenceError(f"Failed to delete memory file {file_path}: {e}") from e
