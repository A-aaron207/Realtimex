"""
Ephemeral memory store implementation for short-lived records.
"""

from __future__ import annotations

from datetime import datetime, timezone

from memory.registry import MemoryRecord
from memory.stores.base import BaseMemoryStore


class EphemeralMemoryStore(BaseMemoryStore):
    """
    In-memory store for short-lived, transient memories.
    Supports periodic or manual eviction of expired records.
    """

    def evict_expired(self) -> list[MemoryRecord]:
        """
        Scan and remove all records whose expiration times have passed.

        Returns:
            List of evicted MemoryRecord objects.
        """
        now = datetime.now(timezone.utc)
        evicted: list[MemoryRecord] = []
        
        with self._lock:
            expired_ids = [
                mid for mid, rec in self._records.items()
                if rec.expires_at is not None and now > rec.expires_at
            ]
            for mid in expired_ids:
                evicted.append(self._records[mid])
                del self._records[mid]
                
        return evicted
