"""
Memory record definition and scope registry for the Realtimex Memory System.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from memory.exceptions import MemoryValidationError

MemoryScope = Literal["global", "task", "ephemeral"]
MemoryStatus = Literal["created", "active", "archived", "deleted"]


@dataclass
class MemoryRecord:
    """
    Representation of a single knowledge record in the Memory System.
    """
    content: Any
    scope: MemoryScope
    owner: str
    source: str
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    status: MemoryStatus = "created"

    def __post_init__(self) -> None:
        valid_scopes = {"global", "task", "ephemeral"}
        if self.scope not in valid_scopes:
            raise MemoryValidationError(f"Invalid scope '{self.scope}'. Must be one of: {valid_scopes}")
            
        valid_statuses = {"created", "active", "archived", "deleted"}
        if self.status not in valid_statuses:
            raise MemoryValidationError(f"Invalid status '{self.status}'. Must be one of: {valid_statuses}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "scope": self.scope,
            "owner": self.owner,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "source": self.source,
            "content": self.content,
            "metadata": self.metadata,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecord:
        expires = data.get("expires_at")
        if expires and isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
            
        return cls(
            memory_id=data["memory_id"],
            scope=data["scope"],
            owner=data["owner"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            tags=data.get("tags", []),
            source=data["source"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            expires_at=expires,
            status=data.get("status", "created"),
        )


class MemoryRegistry:
    """
    Thread-safe registry mapping memory IDs to their active scopes and owners.
    Helpful for cross-scope lookups and migration operations.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Map: memory_id -> (scope, owner)
        self._registry: dict[str, tuple[MemoryScope, str]] = {}

    def register(self, memory_id: str, scope: MemoryScope, owner: str = "") -> None:
        """Register a memory record ID and its associated scope/owner."""
        with self._lock:
            self._registry[memory_id] = (scope, owner)

    def unregister(self, memory_id: str) -> None:
        """Remove a memory record ID from the registry."""
        with self._lock:
            if memory_id in self._registry:
                del self._registry[memory_id]

    def get_scope(self, memory_id: str) -> MemoryScope | None:
        """Retrieve the scope containing a memory record ID."""
        with self._lock:
            info = self._registry.get(memory_id)
            return info[0] if info else None

    def get_owner(self, memory_id: str) -> str | None:
        """Retrieve the owner containing a memory record ID."""
        with self._lock:
            info = self._registry.get(memory_id)
            return info[1] if info else None

    def list_by_scope(self, scope: MemoryScope) -> list[str]:
        """List all memory IDs associated with a specific scope."""
        with self._lock:
            return [mid for mid, (sc, _) in self._registry.items() if sc == scope]

    def clear(self) -> None:
        """Clear the registry mapping."""
        with self._lock:
            self._registry.clear()

