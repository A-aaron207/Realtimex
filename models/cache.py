"""
Response cache for the Realtimex Model Gateway.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from models.provider import ModelResponse


class ResponseCache:
    """
    Thread-safe cache for model generation responses based on request inputs
    (prompt, context, model, parameters) and TTL.
    """

    def __init__(self, default_ttl: float = 600.0) -> None:
        """
        Initialize the ResponseCache.

        Args:
            default_ttl: Expiration duration in seconds (defaults to 10 minutes).
        """
        self.default_ttl = default_ttl
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[ModelResponse, float]] = {}

    def _generate_key(
        self,
        prompt: str,
        context: dict[str, Any],
        model: str,
        parameters: dict[str, Any],
    ) -> str:
        """Generate a stable, unique hash key representing the request parameters."""
        data = {
            "prompt": prompt,
            "context": context,
            "model": model,
            "parameters": parameters,
        }
        # Serialize to JSON with sorted keys for consistency
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(
        self,
        prompt: str,
        context: dict[str, Any],
        model: str,
        parameters: dict[str, Any],
    ) -> ModelResponse | None:
        """Retrieve a cached response if valid and not expired."""
        key = self._generate_key(prompt, context, model, parameters)
        with self._lock:
            if key not in self._cache:
                return None
            
            response, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
                
            return response

    def set(
        self,
        prompt: str,
        context: dict[str, Any],
        model: str,
        parameters: dict[str, Any],
        response: ModelResponse,
        ttl: float | None = None,
    ) -> None:
        """Cache a model generation response."""
        key = self._generate_key(prompt, context, model, parameters)
        ttl_seconds = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + ttl_seconds
        
        with self._lock:
            self._cache[key] = (response, expiry)

    def invalidate(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Return the number of cached items."""
        with self._lock:
            return len(self._cache)
