"""
Quota manager for tracking and enforcing provider limits in the Realtimex Model Gateway.
"""

from __future__ import annotations

import threading
import time


class QuotaManager:
    """
    Thread-safe quota manager tracking request and token rates to enforce rate limits
    (RPM, RPD, TPM) for each model provider.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        
        # Structure: provider_name -> list of timestamps of requests in current minute
        self._requests_minute: dict[str, list[float]] = {}
        # Structure: provider_name -> list of timestamps of requests in current day (24 hours)
        self._requests_day: dict[str, list[float]] = {}
        # Structure: provider_name -> list of tuples (timestamp, token_count)
        self._tokens_minute: dict[str, list[tuple[float, int]]] = {}

        # Default fallback limits if not specified by model metadata
        self._default_rpm = 60
        self._default_rpd = 10000
        self._default_tpm = 40000

    def check_quota(
        self,
        provider_name: str,
        estimated_tokens: int = 1000,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        rpd_limit: int | None = None,
    ) -> bool:
        """
        Verify if sending a request with estimated tokens exceeds rate limits.

        Returns:
            True if within limits, False otherwise.
        """
        now = time.time()
        one_min_ago = now - 60.0
        one_day_ago = now - 86400.0
        p_name = provider_name.lower()

        limit_rpm = rpm_limit if rpm_limit is not None else self._default_rpm
        limit_tpm = tpm_limit if tpm_limit is not None else self._default_tpm
        limit_rpd = rpd_limit if rpd_limit is not None else self._default_rpd

        with self._lock:
            # 1. Clean old entries
            self._requests_minute[p_name] = [t for t in self._requests_minute.get(p_name, []) if t > one_min_ago]
            self._requests_day[p_name] = [t for t in self._requests_day.get(p_name, []) if t > one_day_ago]
            self._tokens_minute[p_name] = [(t, count) for (t, count) in self._tokens_minute.get(p_name, []) if t > one_min_ago]

            # 2. Check RPM
            if len(self._requests_minute[p_name]) >= limit_rpm:
                return False

            # 3. Check RPD
            if len(self._requests_day[p_name]) >= limit_rpd:
                return False

            # 4. Check TPM
            current_tokens = sum(count for (_, count) in self._tokens_minute[p_name])
            if current_tokens + estimated_tokens > limit_tpm:
                return False

            return True

    def consume(self, provider_name: str, token_count: int) -> None:
        """Record consumption of a single request and token usage."""
        now = time.time()
        p_name = provider_name.lower()

        with self._lock:
            self._requests_minute.setdefault(p_name, []).append(now)
            self._requests_day.setdefault(p_name, []).append(now)
            self._tokens_minute.setdefault(p_name, []).append((now, token_count))

    def get_utilization(self, provider_name: str, rpm_limit: int, tpm_limit: int) -> dict[str, float]:
        """Retrieve current quota utilization percentages for debugging or metrics."""
        now = time.time()
        one_min_ago = now - 60.0
        p_name = provider_name.lower()

        with self._lock:
            # Refresh lists
            self._requests_minute[p_name] = [t for t in self._requests_minute.get(p_name, []) if t > one_min_ago]
            self._tokens_minute[p_name] = [(t, count) for (t, count) in self._tokens_minute.get(p_name, []) if t > one_min_ago]

            rpm_count = len(self._requests_minute[p_name])
            tpm_count = sum(count for (_, count) in self._tokens_minute[p_name])

        return {
            "rpm_pct": (rpm_count / rpm_limit) * 100.0 if rpm_limit > 0 else 0.0,
            "tpm_pct": (tpm_count / tpm_limit) * 100.0 if tpm_limit > 0 else 0.0,
        }

    def reset(self) -> None:
        """Reset all tracked metrics."""
        with self._lock:
            self._requests_minute.clear()
            self._requests_day.clear()
            self._tokens_minute.clear()
