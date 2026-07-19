"""
Memory indexing implementation to support tag and owner indexes in the Realtimex Memory System.
"""

from __future__ import annotations

import threading


class MemoryIndexer:
    """
    Thread-safe indexer mapping tags, owners (task IDs), and sources to memory record IDs,
    enabling fast, non-sequential lookup.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Map: tag -> set of memory_ids
        self._tag_index: dict[str, set[str]] = {}
        # Map: owner -> set of memory_ids
        self._owner_index: dict[str, set[str]] = {}
        # Map: source -> set of memory_ids
        self._source_index: dict[str, set[str]] = {}

    def index_record(self, memory_id: str, tags: list[str], owner: str, source: str) -> None:
        """Add a memory record's fields to the indexes."""
        with self._lock:
            # 1. Index Tags
            for tag in tags:
                clean_tag = tag.strip().lower()
                self._tag_index.setdefault(clean_tag, set()).add(memory_id)
            
            # 2. Index Owner
            self._owner_index.setdefault(owner.lower(), set()).add(memory_id)
            
            # 3. Index Source
            self._source_index.setdefault(source.lower(), set()).add(memory_id)

    def deindex_record(self, memory_id: str, tags: list[str], owner: str, source: str) -> None:
        """Remove a memory record's fields from the indexes."""
        with self._lock:
            # 1. Remove Tags
            for tag in tags:
                clean_tag = tag.strip().lower()
                if clean_tag in self._tag_index and memory_id in self._tag_index[clean_tag]:
                    self._tag_index[clean_tag].remove(memory_id)
                    if not self._tag_index[clean_tag]:
                        del self._tag_index[clean_tag]
            
            # 2. Remove Owner
            clean_owner = owner.lower()
            if clean_owner in self._owner_index and memory_id in self._owner_index[clean_owner]:
                self._owner_index[clean_owner].remove(memory_id)
                if not self._owner_index[clean_owner]:
                    del self._owner_index[clean_owner]
            
            # 3. Remove Source
            clean_source = source.lower()
            if clean_source in self._source_index and memory_id in self._source_index[clean_source]:
                self._source_index[clean_source].remove(memory_id)
                if not self._source_index[clean_source]:
                    del self._source_index[clean_source]

    def get_by_tag(self, tag: str) -> set[str]:
        """Get all memory IDs associated with a specific tag."""
        with self._lock:
            return set(self._tag_index.get(tag.strip().lower(), set()))

    def get_by_owner(self, owner: str) -> set[str]:
        """Get all memory IDs associated with a specific owner (task ID)."""
        with self._lock:
            return set(self._owner_index.get(owner.lower(), set()))

    def get_by_source(self, source: str) -> set[str]:
        """Get all memory IDs associated with a specific source."""
        with self._lock:
            return set(self._source_index.get(source.lower(), set()))

    def clear(self) -> None:
        """Clear all indexes."""
        with self._lock:
            self._tag_index.clear()
            self._owner_index.clear()
            self._source_index.clear()
