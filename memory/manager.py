"""
Memory Manager orchestrator for the Realtimex Memory System.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from events.event import Event, EventPriority
from events.event_types import MemoryEventType
from memory.cache import MemoryCache
from memory.exceptions import (
    MemoryNotFoundError,
    MemoryValidationError,
    MemoryScopeError,
)
from memory.indexing import MemoryIndexer
from memory.lifecycle import validate_lifecycle_transition
from memory.persistence import MemoryPersistence
from memory.policies import MemoryPolicy, PolicyEnforcer
from memory.registry import MemoryRecord, MemoryRegistry, MemoryScope
from memory.retrieval import MemoryRetrieval
from memory.search import MemorySearchQuery, MemorySearcher
from memory.artifact_memory import ArtifactMemoryStore, ArtifactRecord
from memory.stores.ephemeral_store import EphemeralMemoryStore
from memory.stores.global_store import GlobalMemoryStore
from memory.stores.task_store import TaskMemoryStore
from memory.task_trajectory import TaskTrajectoryRecord, TaskTrajectoryStore
from memory.workspace import WorkspaceContext, WorkspaceMemoryStore


class MemoryManager:
    """
    Main orchestration class managing knowledge access, scopes, persistence,
    caching, search index mappings, policies, and lifecycle stages in Realtimex.
    """

    def __init__(
        self,
        persistence: MemoryPersistence,
        event_bus: Any = None,
        policy: MemoryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.persistence = persistence
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.memory")
        self.policy = policy or MemoryPolicy()
        self.policy_enforcer = PolicyEnforcer(self.policy)

        # Core components
        self.registry = MemoryRegistry()
        self.indexer = MemoryIndexer()
        self.cache = MemoryCache()
        self.searcher = MemorySearcher()

        # Stores
        self.global_store = GlobalMemoryStore(persistence=self.persistence)
        self.task_store = TaskMemoryStore(persistence=self.persistence)
        self.ephemeral_store = EphemeralMemoryStore()

        # Memory 2.0 Subsystems
        self.workspace_store = WorkspaceMemoryStore()
        self.trajectory_store = TaskTrajectoryStore()
        self.artifact_store = ArtifactMemoryStore()

        self.retrieval = MemoryRetrieval(
            registry=self.registry,
            global_store=self.global_store,
            task_store=self.task_store,
            ephemeral_store=self.ephemeral_store,
            indexer=self.indexer,
        )

        # Register loaded persisted memories in the registry and indexer
        self._bootstrap_indexes()

    def _bootstrap_indexes(self) -> None:
        """Load and index all bootsrapped persistent memory records."""
        # 1. Global memories
        for rec in self.global_store.list_all():
            self.registry.register(rec.memory_id, "global", rec.owner)
            self.indexer.index_record(rec.memory_id, rec.tags, rec.owner, rec.source)

        # 2. Task memories (if any are pre-loaded in task_store cache)
        for rec in self.task_store.list_all():
            self.registry.register(rec.memory_id, "task", rec.owner)
            self.indexer.index_record(rec.memory_id, rec.tags, rec.owner, rec.source)

        # 3. Discover and register task memory files from persistence directories
        if hasattr(self.persistence, "directory"):
            task_dir = self.persistence.directory / "task"
            if task_dir.exists():
                for file_path in task_dir.glob("*.json"):
                    task_id = file_path.stem
                    try:
                        records = self.persistence.load("task", task_id)
                        for rec in records:
                            self.registry.register(rec.memory_id, "task", rec.owner)
                            self.indexer.index_record(rec.memory_id, rec.tags, rec.owner, rec.source)
                    except Exception:
                        pass

    def _sweep_expired_ephemeral(self) -> None:
        """Automatically prunes expired ephemeral memories and publishes events."""
        evicted = self.ephemeral_store.evict_expired()
        for rec in evicted:
            self.registry.unregister(rec.memory_id)
            self.indexer.deindex_record(rec.memory_id, rec.tags, rec.owner, rec.source)
            self._emit_event(
                name=MemoryEventType.MEMORY_EXPIRED,
                task_id=rec.owner if rec.scope == "task" else "",
                payload={"memory_id": rec.memory_id},
            )

    # --- Public API ---

    def create(
        self,
        scope: MemoryScope,
        owner: str,
        content: Any,
        source: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: float | None = None,
    ) -> MemoryRecord:
        """
        Create a new memory record and store it within the specified scope.
        """
        self._sweep_expired_ephemeral()

        # Compute expiration if provided or default for ephemeral
        expires_at: datetime | None = None
        if ttl_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        elif scope == "ephemeral":
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.policy.default_ephemeral_ttl_seconds
            )

        record = MemoryRecord(
            content=content,
            scope=scope,
            owner=owner,
            source=source,
            tags=tags or [],
            metadata=metadata or {},
            expires_at=expires_at,
            status="active",
        )

        # Enforce policy limits
        if scope == "task":
            current_count = len(self.task_store.list_by_task(owner))
            self.policy_enforcer.enforce_limits(record, current_count)

        # Store in appropriate store
        if scope == "global":
            self.global_store.add(record)
        elif scope == "task":
            self.task_store.add(record)
        elif scope == "ephemeral":
            self.ephemeral_store.add(record)

        # Update registry and indexes
        self.registry.register(record.memory_id, scope, record.owner)
        self.indexer.index_record(record.memory_id, record.tags, record.owner, record.source)

        # Invalidate cache
        self.cache.invalidate()

        # Emit event
        self._emit_event(
            name=MemoryEventType.MEMORY_CREATED,
            task_id=owner if scope == "task" else "",
            payload=record.to_dict(),
        )

        return record

    def retrieve(self, memory_id: str) -> MemoryRecord:
        """
        Retrieve a single memory record by its ID.

        Raises:
            MemoryNotFoundError: If the record is missing or expired.
        """
        self._sweep_expired_ephemeral()

        # Check Cache
        cached_list = self.cache.get("exact_lookup", {"memory_id": memory_id})
        if cached_list:
            record = cached_list[0]
            if self.policy_enforcer.is_expired(record):
                self.delete(memory_id)
                raise MemoryNotFoundError(f"Memory record with ID '{memory_id}' has expired.")
            self._emit_event(
                name=MemoryEventType.MEMORY_RETRIEVED,
                task_id=record.owner if record.scope == "task" else "",
                payload=record.to_dict(),
            )
            return record

        record = self.retrieval.exact_lookup(memory_id)
        if record is None or record.status == "deleted":
            raise MemoryNotFoundError(f"Memory record with ID '{memory_id}' not found.")

        # Check explicit expiration (e.g. for global/task that got expired but not yet pruned)
        if self.policy_enforcer.is_expired(record):
            # Clean up
            self.delete(memory_id)
            raise MemoryNotFoundError(f"Memory record with ID '{memory_id}' has expired.")

        # Save to Cache
        self.cache.set("exact_lookup", {"memory_id": memory_id}, [record])

        # Emit event
        self._emit_event(
            name=MemoryEventType.MEMORY_RETRIEVED,
            task_id=record.owner if record.scope == "task" else "",
            payload=record.to_dict(),
        )

        return record

    def update(
        self,
        memory_id: str,
        content: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """
        Update fields of an existing memory record.
        """
        record = self.retrieve(memory_id)

        # De-index old values
        self.indexer.deindex_record(record.memory_id, record.tags, record.owner, record.source)

        # Create updated record copy
        new_content = content if content is not None else record.content
        new_tags = tags if tags is not None else record.tags
        new_metadata = record.metadata.copy()
        if metadata:
            new_metadata.update(metadata)

        updated_record = MemoryRecord(
            memory_id=record.memory_id,
            content=new_content,
            scope=record.scope,
            owner=record.owner,
            source=record.source,
            created_at=record.created_at,
            updated_at=datetime.now(timezone.utc),
            tags=new_tags,
            metadata=new_metadata,
            expires_at=record.expires_at,
            status=record.status,
        )

        # Update in store
        if record.scope == "global":
            self.global_store.update(memory_id, updated_record)
        elif record.scope == "task":
            self.task_store.update(memory_id, updated_record)
        elif record.scope == "ephemeral":
            self.ephemeral_store.update(memory_id, updated_record)

        # Index new values
        self.indexer.index_record(
            updated_record.memory_id,
            updated_record.tags,
            updated_record.owner,
            updated_record.source,
        )

        # Invalidate cache
        self.cache.invalidate()

        # Emit event
        self._emit_event(
            name=MemoryEventType.MEMORY_UPDATED,
            task_id=updated_record.owner if updated_record.scope == "task" else "",
            payload=updated_record.to_dict(),
        )

        return updated_record

    def delete(self, memory_id: str) -> None:
        """
        Transition a memory record to the DELETED state and remove it from store.
        """
        # Fetch directly without retrieve() to avoid recursion if called during expiration
        scope = self.registry.get_scope(memory_id)
        if scope is None:
            return

        record = self.retrieval.exact_lookup(memory_id)
        if record is None:
            return

        # Validate lifecycle state transition
        validate_lifecycle_transition(record.status, "deleted")

        # De-index
        self.indexer.deindex_record(record.memory_id, record.tags, record.owner, record.source)

        # Delete from store
        if scope == "global":
            self.global_store.delete(memory_id)
        elif scope == "task":
            self.task_store.delete(memory_id)
        elif scope == "ephemeral":
            self.ephemeral_store.delete(memory_id)

        # Remove from scope mapping registry
        self.registry.unregister(memory_id)

        # Invalidate cache
        self.cache.invalidate()

        # Emit event
        self._emit_event(
            name=MemoryEventType.MEMORY_DELETED,
            task_id=record.owner if scope == "task" else "",
            payload={"memory_id": memory_id},
        )

    def archive(self, memory_id: str) -> MemoryRecord:
        """
        Archive a memory record, changing its status and preserving it on disk.
        """
        record = self.retrieve(memory_id)
        validate_lifecycle_transition(record.status, "archived")

        updated_record = MemoryRecord(
            memory_id=record.memory_id,
            content=record.content,
            scope=record.scope,
            owner=record.owner,
            source=record.source,
            created_at=record.created_at,
            updated_at=datetime.now(timezone.utc),
            tags=record.tags,
            metadata=record.metadata,
            expires_at=record.expires_at,
            status="archived",
        )

        # Save update in store
        if record.scope == "global":
            self.global_store.update(memory_id, updated_record)
        elif record.scope == "task":
            self.task_store.update(memory_id, updated_record)
        elif record.scope == "ephemeral":
            self.ephemeral_store.update(memory_id, updated_record)

        self.cache.invalidate()

        self._emit_event(
            name=MemoryEventType.MEMORY_ARCHIVED,
            task_id=updated_record.owner if record.scope == "task" else "",
            payload=updated_record.to_dict(),
        )

        return updated_record

    def move(self, memory_id: str, target_scope: MemoryScope) -> MemoryRecord:
        """
        Move a memory record from its current scope to a target scope.
        """
        self._sweep_expired_ephemeral()

        record = self.retrieve(memory_id)
        current_scope = record.scope

        if current_scope == target_scope:
            return record

        # Remove from current store
        if current_scope == "global":
            self.global_store.delete(memory_id)
        elif current_scope == "task":
            self.task_store.delete(memory_id)
        elif current_scope == "ephemeral":
            self.ephemeral_store.delete(memory_id)

        self.registry.unregister(memory_id)
        self.indexer.deindex_record(record.memory_id, record.tags, record.owner, record.source)

        # Adjust expiration when moving
        expires_at = record.expires_at
        if target_scope == "ephemeral":
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.policy.default_ephemeral_ttl_seconds
            )
        elif current_scope == "ephemeral":
            # Ephemeral transitioning to permanent
            expires_at = None

        new_record = MemoryRecord(
            memory_id=record.memory_id,
            content=record.content,
            scope=target_scope,
            owner=record.owner,
            source=record.source,
            created_at=record.created_at,
            updated_at=datetime.now(timezone.utc),
            tags=record.tags,
            metadata=record.metadata,
            expires_at=expires_at,
            status=record.status,
        )

        # Enforce target limits
        if target_scope == "task":
            current_count = len(self.task_store.list_by_task(new_record.owner))
            self.policy_enforcer.enforce_limits(new_record, current_count)

        # Add to target store
        if target_scope == "global":
            self.global_store.add(new_record)
        elif target_scope == "task":
            self.task_store.add(new_record)
        elif target_scope == "ephemeral":
            self.ephemeral_store.add(new_record)

        # Register and index
        self.registry.register(new_record.memory_id, target_scope, new_record.owner)
        self.indexer.index_record(
            new_record.memory_id,
            new_record.tags,
            new_record.owner,
            new_record.source,
        )

        self.cache.invalidate()

        self._emit_event(
            name=MemoryEventType.MEMORY_UPDATED,
            task_id=new_record.owner if target_scope == "task" else "",
            payload=new_record.to_dict(),
        )

        return new_record

    def search(
        self,
        query: MemorySearchQuery | dict[str, Any],
        scope: MemoryScope | None = None,
    ) -> list[MemoryRecord]:
        """
        Search for memory records matching query parameters.
        """
        self._sweep_expired_ephemeral()

        # Parse dict query if provided
        if isinstance(query, dict):
            # Map dictionary query keys
            query_obj = MemorySearchQuery(
                query_text=query.get("query_text"),
                tags=query.get("tags", []),
                owner=query.get("owner"),
                scope=query.get("scope") or scope,
                status=query.get("status"),
                source=query.get("source"),
                created_since=query.get("created_since"),
                created_until=query.get("created_until"),
            )
        else:
            query_obj = query
            if scope is not None:
                query_obj.scope = scope

        # 1. Fetch Candidates (Optimization: check task owner to narrow search window)
        candidates: list[MemoryRecord] = []
        if query_obj.owner and query_obj.scope == "task":
            candidates = self.task_store.list_by_task(query_obj.owner)
        else:
            # Collect everything across all scopes
            scopes_to_scan = [query_obj.scope] if query_obj.scope is not None else ["global", "task", "ephemeral"]
            if "global" in scopes_to_scan:
                candidates.extend(self.global_store.list_all())
            if "task" in scopes_to_scan:
                candidates.extend(self.task_store.list_all())
            if "ephemeral" in scopes_to_scan:
                candidates.extend(self.ephemeral_store.list_all())

        # 2. Run through filters
        return self.searcher.search(query_obj, candidates)

    def list(self, scope: MemoryScope | None = None, owner: str | None = None) -> list[MemoryRecord]:
        """
        List memory records, optionally filtered by scope and owner.
        """
        self._sweep_expired_ephemeral()
        
        query = MemorySearchQuery(scope=scope, owner=owner)
        candidates: list[MemoryRecord] = []
        
        scopes_to_scan = [scope] if scope is not None else ["global", "task", "ephemeral"]
        
        if "global" in scopes_to_scan:
            candidates.extend(self.global_store.list_all())
        if "task" in scopes_to_scan:
            if owner:
                candidates.extend(self.task_store.list_by_task(owner))
            else:
                candidates.extend(self.task_store.list_all())
        if "ephemeral" in scopes_to_scan:
            candidates.extend(self.ephemeral_store.list_all())

        return self.searcher.search(query, candidates)

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        """Internal helper to publish memory transactions to EventBus."""
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="memory.manager",
                        task_id=task_id,
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Failed to emit memory event %s: %s", name, e)
