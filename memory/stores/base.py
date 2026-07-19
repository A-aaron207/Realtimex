"""
Base memory store implementation for the Realtimex Memory System.
"""

from __future__ import annotations

import threading
from typing import Any

from memory.exceptions import MemoryNotFoundError
from memory.registry import MemoryRecord


class BaseMemoryStore:
    """
    Thread-safe, in-memory repository base for storing Memory Records.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, MemoryRecord] = {}

    def add(self, record: MemoryRecord) -> None:
        """Add a memory record."""
        with self._lock:
            self._records[record.memory_id] = record

    def get(self, memory_id: str) -> MemoryRecord | None:
        """Get a memory record by ID."""
        with self._lock:
            return self._records.get(memory_id)

    def update(self, memory_id: str, updated_record: MemoryRecord) -> None:
        """Update an existing memory record."""
        with self._lock:
            if memory_id not in self._records:
                raise MemoryNotFoundError(f"Record with ID '{memory_id}' not found.")
            self._records[memory_id] = updated_record

    def delete(self, memory_id: str) -> None:
        """Remove a memory record by ID."""
        with self._lock:
            if memory_id in self._records:
                del self._records[memory_id]

    def list_all(self) -> list[MemoryRecord]:
        """Retrieve all memory records in the store."""
        with self._lock:
            return list(self._records.values())

    def clear(self) -> None:
        """Clear all memory records in the store."""
        with self._lock:
            self._records.clear()

    @property
    def size(self) -> int:
        """Get the total count of records in the store."""
        with self._lock:
            return len(self._records)
