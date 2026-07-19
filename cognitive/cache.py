"""
Thread-safe caching mechanism for the Realtimex Cognitive Engine.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from cognitive.reasoning import CognitiveRequest, CognitiveResponse


class CognitiveCache:
    """
    Thread-safe cache for cognitive reasoning requests with configurable TTL expiration.
    """

    def __init__(self, default_ttl: float = 300.0) -> None:
        """
        Initialize the CognitiveCache.

        Args:
            default_ttl: Expiration duration in seconds (defaults to 300s/5m).
        """
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[CognitiveResponse, float]] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, request: CognitiveRequest, decision_type: str) -> str:
        """Generate a stable, unique hash key for a request and decision type."""
        data = {
            "task_id": request.task_id,
            "objective": request.objective,
            "workflow_id": request.workflow_id,
            "constraints": sorted(request.constraints),
            "available_capabilities": sorted(request.available_capabilities),
            "decision_type": decision_type,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, request: CognitiveRequest, decision_type: str) -> CognitiveResponse | None:
        """
        Retrieve a cached response if present and not expired.

        Args:
            request: The cognitive request.
            decision_type: The decision type.

        Returns:
            CognitiveResponse if found and valid, otherwise None.
        """
        key = self._generate_key(request, decision_type)
        with self._lock:
            if key not in self._cache:
                return None
            
            response, expiry = self._cache[key]
            if time.time() > expiry:
                # Cache expired, remove it
                del self._cache[key]
                return None
                
            return response

    def set(
        self,
        request: CognitiveRequest,
        decision_type: str,
        response: CognitiveResponse,
        ttl: float | None = None,
    ) -> None:
        """
        Cache a reasoning response.

        Args:
            request: The cognitive request.
            decision_type: The decision type.
            response: The reasoning response.
            ttl: Optional override for time-to-live in seconds.
        """
        key = self._generate_key(request, decision_type)
        ttl_seconds = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + ttl_seconds
        
        with self._lock:
            self._cache[key] = (response, expiry)

    def clear(self) -> None:
        """Clear all entries in the cache."""
        with self._lock:
            self._cache.clear()

    def remove_expired(self) -> int:
        """Remove all expired cache entries and return the count of removed items."""
        now = time.time()
        removed = 0
        with self._lock:
            expired_keys = [k for k, (_, expiry) in self._cache.items() if now > expiry]
            for k in expired_keys:
                del self._cache[k]
                removed += 1
        return removed

    @property
    def size(self) -> int:
        """Return the current number of items stored in the cache."""
        with self._lock:
            return len(self._cache)
