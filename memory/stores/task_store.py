"""
Task memory store implementation for task-specific knowledge partitioning.
"""

from __future__ import annotations

from memory.persistence import MemoryPersistence
from memory.registry import MemoryRecord
from memory.stores.base import BaseMemoryStore


class TaskMemoryStore(BaseMemoryStore):
    """
    Persistent, lazy-loading store for task-specific memories.
    Partitioned by Task ID (owner) to keep task boundaries isolated.
    """

    def __init__(self, persistence: MemoryPersistence) -> None:
        super().__init__()
        self.persistence = persistence
        # Map: task_id -> dict[memory_id, MemoryRecord]
        self._partitions: dict[str, dict[str, MemoryRecord]] = {}

    def list_by_task(self, task_id: str) -> list[MemoryRecord]:
        """
        Retrieve all memory records associated with a specific task.
        Loads the partition from disk if not already cached in memory.
        """
        with self._lock:
            if task_id not in self._partitions:
                self._load_partition(task_id)
            return list(self._partitions[task_id].values())

    def add(self, record: MemoryRecord) -> None:
        task_id = record.owner
        with self._lock:
            if task_id not in self._partitions:
                self._load_partition(task_id)
            
            # Save to flat registry
            self._records[record.memory_id] = record
            # Save to task partition
            self._partitions[task_id][record.memory_id] = record

        self._sync_partition(task_id)

    def get(self, memory_id: str) -> MemoryRecord | None:
        # Check flat registry first
        record = super().get(memory_id)
        if record is not None:
            return record
            
        # If not found in loaded memory, we scan the persistence directories or rely on
        # lazy loading by task. Because task_id (owner) is needed to find the file on disk,
        # lookup of unknown uncached IDs directly is limited. However, the MemoryRegistry
        # will tell us the owner and scope, which we use to load the correct partition!
        return None

    def load_record_with_owner(self, memory_id: str, task_id: str) -> MemoryRecord | None:
        """
        Load a specific task record if the owner task ID is known.
        """
        with self._lock:
            if task_id not in self._partitions:
                self._load_partition(task_id)
            return self._partitions[task_id].get(memory_id)

    def update(self, memory_id: str, updated_record: MemoryRecord) -> None:
        task_id = updated_record.owner
        with self._lock:
            if task_id not in self._partitions:
                self._load_partition(task_id)
            
            self._records[memory_id] = updated_record
            self._partitions[task_id][memory_id] = updated_record
            
        self._sync_partition(task_id)

    def delete(self, memory_id: str) -> None:
        # Find record to know task_id
        record = self.get(memory_id)
        if record is None:
            return

        task_id = record.owner
        with self._lock:
            if memory_id in self._records:
                del self._records[memory_id]
            if task_id in self._partitions and memory_id in self._partitions[task_id]:
                del self._partitions[task_id][memory_id]

        self._sync_partition(task_id)

    def clear(self) -> None:
        # Collect all partition keys for sync
        with self._lock:
            task_ids = list(self._partitions.keys())
            self._records.clear()
            self._partitions.clear()

        # Delete all files on disk
        for tid in task_ids:
            try:
                self.persistence.delete("task", tid)
            except Exception:
                pass

    def clear_task(self, task_id: str) -> None:
        """Remove all memory records and the persistence file for a single task."""
        with self._lock:
            if task_id in self._partitions:
                # Remove from flat registry
                for mid in self._partitions[task_id]:
                    if mid in self._records:
                        del self._records[mid]
                del self._partitions[task_id]

        try:
            self.persistence.delete("task", task_id)
        except Exception:
            pass

    def _load_partition(self, task_id: str) -> None:
        """Internal helper to load a partition (assumes lock is held)."""
        self._partitions[task_id] = {}
        try:
            records = self.persistence.load(scope="task", owner=task_id)
            for rec in records:
                self._records[rec.memory_id] = rec
                self._partitions[task_id][rec.memory_id] = rec
        except Exception:
            pass

    def _sync_partition(self, task_id: str) -> None:
        """Internal helper to write a partition back to persistent storage."""
        with self._lock:
            partition_records = list(self._partitions.get(task_id, {}).values())

        try:
            if partition_records:
                self.persistence.save(scope="task", owner=task_id, records=partition_records)
            else:
                self.persistence.delete(scope="task", owner=task_id)
        except Exception:
            pass
