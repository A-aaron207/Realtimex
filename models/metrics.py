"""
Metrics tracker for the Realtimex Model Gateway.
"""

from __future__ import annotations

import threading
from typing import Any


class GatewayMetrics:
    """
    Thread-safe metrics accumulator tracking usage volume, token counts, costs,
    and cache performance statistics.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.failover_triggers = 0
        
        # Structure: provider_name -> count
        self._calls_by_provider: dict[str, int] = {}
        self._tokens_by_provider: dict[str, int] = {}
        self._cost_by_provider: dict[str, float] = {}

    def record_request(self) -> None:
        with self._lock:
            self.total_requests += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def record_failover(self) -> None:
        with self._lock:
            self.failover_triggers += 1

    def record_provider_usage(
        self,
        provider_name: str,
        tokens: int,
        cost: float = 0.0,
    ) -> None:
        p_name = provider_name.lower()
        with self._lock:
            self._calls_by_provider[p_name] = self._calls_by_provider.get(p_name, 0) + 1
            self._tokens_by_provider[p_name] = self._tokens_by_provider.get(p_name, 0) + tokens
            self._cost_by_provider[p_name] = self._cost_by_provider.get(p_name, 0.0) + cost

    def get_summary(self) -> dict[str, Any]:
        """Get accumulated metrics summary dictionary."""
        with self._lock:
            total_tokens = sum(self._tokens_by_provider.values())
            total_cost = sum(self._cost_by_provider.values())
            total_calls = sum(self._calls_by_provider.values())

            cache_rate = 0.0
            total_cache_attempts = self.cache_hits + self.cache_misses
            if total_cache_attempts > 0:
                cache_rate = self.cache_hits / total_cache_attempts

            return {
                "total_requests": self.total_requests,
                "total_provider_calls": total_calls,
                "total_tokens_consumed": total_tokens,
                "total_cost_incurred": total_cost,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate": cache_rate,
                "failover_triggers": self.failover_triggers,
                "calls_by_provider": dict(self._calls_by_provider),
                "tokens_by_provider": dict(self._tokens_by_provider),
                "cost_by_provider": dict(self._cost_by_provider),
            }

    def reset(self) -> None:
        """Reset all tracked metrics."""
        with self._lock:
            self.total_requests = 0
            self.cache_hits = 0
            self.cache_misses = 0
            self.failover_triggers = 0
            self._calls_by_provider.clear()
            self._tokens_by_provider.clear()
            self._cost_by_provider.clear()
