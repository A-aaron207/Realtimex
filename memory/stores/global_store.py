"""
Global memory store implementation for long-term configuration and user preferences.
"""

from __future__ import annotations

from memory.persistence import MemoryPersistence
from memory.registry import MemoryRecord
from memory.stores.base import BaseMemoryStore


class GlobalMemoryStore(BaseMemoryStore):
    """
    Persistent store for global, system-wide memories.
    Loads existing data from disk on startup and persists all updates.
    """

    def __init__(self, persistence: MemoryPersistence) -> None:
        super().__init__()
        self.persistence = persistence
        self._load_from_persistence()

    def _load_from_persistence(self) -> None:
        try:
            records = self.persistence.load(scope="global", owner="system")
            for rec in records:
                self._records[rec.memory_id] = rec
        except Exception:
            # Fallback to empty if load fails, or raise depending on strictness
            pass

    def add(self, record: MemoryRecord) -> None:
        super().add(record)
        self._sync()

    def update(self, memory_id: str, updated_record: MemoryRecord) -> None:
        super().update(memory_id, updated_record)
        self._sync()

    def delete(self, memory_id: str) -> None:
        super().delete(memory_id)
        self._sync()

    def clear(self) -> None:
        super().clear()
        self._sync()

    def _sync(self) -> None:
        """Synchronize the in-memory records to persistent storage."""
        try:
            self.persistence.save(scope="global", owner="system", records=self.list_all())
        except Exception:
            # In a production system we'd log this persistence failure
            pass
