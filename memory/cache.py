"""
In-memory cache for fast query retrieval in the Realtimex Memory System.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from memory.registry import MemoryRecord


class MemoryCache:
    """
    Thread-safe query cache for memory record lookups, with automated TTL expiration
    and write-based invalidation.
    """

    def __init__(self, default_ttl: float = 60.0) -> None:
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[list[MemoryRecord], float]] = {}

    def _generate_key(self, prefix: str, params: dict[str, Any]) -> str:
        serialized = json.dumps(params, sort_keys=True)
        h = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{prefix}:{h}"

    def get(self, prefix: str, params: dict[str, Any]) -> list[MemoryRecord] | None:
        """Retrieve a cached query result if present and not expired."""
        key = self._generate_key(prefix, params)
        with self._lock:
            if key not in self._cache:
                return None
            
            records, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
                
            return list(records)

    def set(
        self,
        prefix: str,
        params: dict[str, Any],
        records: list[MemoryRecord],
        ttl: float | None = None,
    ) -> None:
        """Cache a query result."""
        key = self._generate_key(prefix, params)
        ttl_seconds = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + ttl_seconds
        
        with self._lock:
            self._cache[key] = (list(records), expiry)

    def invalidate(self) -> None:
        """Invalidate the entire cache."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Return total size of the cache."""
        with self._lock:
            return len(self._cache)
