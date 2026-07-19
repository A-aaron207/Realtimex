"""
Permission Cache implementation for temporary and scoped approvals in Realtimex.
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass

from permissions.decision import PermissionDecision
from permissions.request import PermissionRequest


@dataclass
class CacheEntry:
    decision: PermissionDecision
    expires_at: datetime | None
    cache_policy: str
    task_id: str | None


class PermissionCache:
    """
    Thread-safe cache storing evaluated decisions. Supports scoping parameters
    (once, task lifetime, session lifetime, persistent).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Map: cache_key -> CacheEntry
        self._cache: dict[str, CacheEntry] = {}

    def _generate_key(self, worker_id: str, action: str, target: str) -> str:
        raw = f"{worker_id.strip().lower()}:{action.strip().lower()}:{target.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, request: PermissionRequest) -> PermissionDecision | None:
        """
        Check if a valid cached approval exists for the request.
        Handles policy expiration and single-use removal.
        """
        key = self._generate_key(request.worker_id, request.action, request.target)
        
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # 1. Expiration check
            if entry.expires_at and datetime.now(timezone.utc) > entry.expires_at:
                del self._cache[key]
                return None

            # 2. Scope check (Task lifetime)
            if entry.cache_policy == "task":
                if entry.task_id != request.task_id:
                    # Belongs to a different task
                    return None

            # 3. Once check (Single-use)
            if entry.cache_policy == "once":
                del self._cache[key]
                return entry.decision

            return entry.decision

    def set(self, request: PermissionRequest, decision: PermissionDecision) -> None:
        """Cache a decision for a request."""
        if not decision.approved:
            # We typically only cache approvals; denials are re-evaluated or cached briefly
            # but let's follow the standard pattern of caching both depending on cache_policy.
            pass

        key = self._generate_key(request.worker_id, request.action, request.target)
        
        with self._lock:
            self._cache[key] = CacheEntry(
                decision=decision,
                expires_at=decision.expiration,
                cache_policy=decision.cache_policy,
                task_id=request.task_id,
            )

    def invalidate_task(self, task_id: str) -> None:
        """Evict all cached decisions tied to the given task ID."""
        with self._lock:
            keys_to_remove = [
                key for key, entry in self._cache.items()
                if entry.cache_policy == "task" and entry.task_id == task_id
            ]
            for key in keys_to_remove:
                del self._cache[key]

    def list_all(self) -> list[tuple[str, PermissionDecision]]:
        """List all currently cached entries as (key_hash, decision)."""
        with self._lock:
            # Clean expired first
            now = datetime.now(timezone.utc)
            active_keys = []
            for key, entry in list(self._cache.items()):
                if entry.expires_at and now > entry.expires_at:
                    del self._cache[key]
                else:
                    active_keys.append((key, entry.decision))
            return active_keys

    def clear(self) -> None:
        """Wipe the cache completely."""
        with self._lock:
            self._cache.clear()
