"""
Retrieval engine for looking up memories in the Realtimex Memory System.
"""

from __future__ import annotations

from typing import Any

from memory.exceptions import MemoryNotFoundError
from memory.registry import MemoryRecord, MemoryRegistry, MemoryScope
from memory.stores.global_store import GlobalMemoryStore
from memory.stores.task_store import TaskMemoryStore
from memory.stores.ephemeral_store import EphemeralMemoryStore
from memory.indexing import MemoryIndexer


class MemoryRetrieval:
    """
    Retrieval system providing exact lookups, tag lookups, task lookups,
    recency listings, and future-ready semantic searching.
    """

    def __init__(
        self,
        registry: MemoryRegistry,
        global_store: GlobalMemoryStore,
        task_store: TaskMemoryStore,
        ephemeral_store: EphemeralMemoryStore,
        indexer: MemoryIndexer,
    ) -> None:
        self.registry = registry
        self.global_store = global_store
        self.task_store = task_store
        self.ephemeral_store = ephemeral_store
        self.indexer = indexer

    def exact_lookup(self, memory_id: str) -> MemoryRecord | None:
        """Look up a memory record by its unique ID across all scopes."""
        scope = self.registry.get_scope(memory_id)
        if scope is None:
            return None

        if scope == "global":
            return self.global_store.get(memory_id)
        elif scope == "ephemeral":
            return self.ephemeral_store.get(memory_id)
        elif scope == "task":
            # Task memory might need lazy loading, we check registry mapping to find owner
            # Let's search inside loaded flat records first
            rec = self.task_store.get(memory_id)
            if rec is not None:
                return rec
            
            owner = self.registry.get_owner(memory_id)
            if owner:
                return self.task_store.load_record_with_owner(memory_id, owner)
            
            # Fallback scan loaded partitions
            for task_id in list(self.task_store._partitions.keys()):
                rec = self.task_store.load_record_with_owner(memory_id, task_id)
                if rec is not None:
                    return rec
            return None
        return None

    def get_by_tag(self, tag: str) -> list[MemoryRecord]:
        """Retrieve all memory records matching a tag."""
        mids = self.indexer.get_by_tag(tag)
        records = []
        for mid in mids:
            rec = self.exact_lookup(mid)
            if rec is not None:
                records.append(rec)
        return records

    def get_by_task(self, task_id: str) -> list[MemoryRecord]:
        """Retrieve all memory records associated with a task ID."""
        # Task store will lazy-load the task file if not in cache
        return self.task_store.list_by_task(task_id)

    def get_recent(self, count: int = 10, scope: MemoryScope | None = None) -> list[MemoryRecord]:
        """Retrieve the most recently created memory records."""
        records: list[MemoryRecord] = []
        
        # Collect from requested or all active scopes
        scopes_to_collect = [scope] if scope is not None else ["global", "task", "ephemeral"]
        
        if "global" in scopes_to_collect:
            records.extend(self.global_store.list_all())
        if "ephemeral" in scopes_to_collect:
            # First prune expired
            self.ephemeral_store.evict_expired()
            records.extend(self.ephemeral_store.list_all())
        if "task" in scopes_to_collect:
            # We list loaded records
            records.extend(self.task_store.list_all())

        # Sort descending by created_at time
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:count]

    def semantic_search(self, query: str, limit: int = 5, scope: MemoryScope | None = None) -> list[MemoryRecord]:
        """
        Placeholder interface for semantic search.
        Currently performs keyword matching on content/tags. Can be upgraded to
        embeddings-based vector search without changing public callers.
        """
        query_words = set(query.lower().split())
        if not query_words:
            return self.get_recent(limit, scope)

        # Collect candidate records
        candidates = self.get_recent(100, scope)
        scored_candidates: list[tuple[MemoryRecord, int]] = []

        for rec in candidates:
            score = 0
            content_str = str(rec.content).lower()
            tag_str = " ".join(rec.tags).lower()
            
            # Simple keyword match scoring
            for word in query_words:
                if word in content_str:
                    score += 2
                if word in tag_str:
                    score += 3
                    
            if score > 0:
                scored_candidates.append((rec, score))

        # Sort by match score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return [rec for rec, _ in scored_candidates[:limit]]
