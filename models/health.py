"""
Health monitor for tracking provider and model health states in the Realtimex Model Gateway.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class HealthMetrics:
    """
    Health metrics for a specific provider model.
    """
    online: bool = True
    avg_latency: float = 0.0
    consecutive_failures: int = 0
    last_successful_request: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests


class HealthMonitor:
    """
    Thread-safe tracker recording and assessing model health status, latency, and success rates.
    """

    def __init__(self, failure_threshold: int = 3) -> None:
        self.failure_threshold = failure_threshold
        self._lock = threading.Lock()
        self._metrics: dict[tuple[str, str], HealthMetrics] = {}

    def _get_metrics(self, provider_name: str, model_name: str) -> HealthMetrics:
        key = (provider_name.lower(), model_name)
        if key not in self._metrics:
            self._metrics[key] = HealthMetrics()
        return self._metrics[key]

    def record_success(self, provider_name: str, model_name: str, latency: float) -> None:
        """Record a successful request to a model."""
        with self._lock:
            metrics = self._get_metrics(provider_name, model_name)
            metrics.total_requests += 1
            metrics.successful_requests += 1
            metrics.consecutive_failures = 0
            metrics.last_successful_request = time.time()
            metrics.online = True
            
            # Latency running average
            if metrics.avg_latency == 0.0:
                metrics.avg_latency = latency
            else:
                metrics.avg_latency = (metrics.avg_latency * 0.8) + (latency * 0.2)

    def record_failure(self, provider_name: str, model_name: str) -> None:
        """Record a failed request to a model."""
        with self._lock:
            metrics = self._get_metrics(provider_name, model_name)
            metrics.total_requests += 1
            metrics.consecutive_failures += 1
            if metrics.consecutive_failures >= self.failure_threshold:
                metrics.online = False

    def is_model_healthy(self, provider_name: str, model_name: str) -> bool:
        """Determine if a model is currently healthy and online."""
        with self._lock:
            metrics = self._get_metrics(provider_name, model_name)
            return metrics.online and metrics.consecutive_failures < self.failure_threshold

    def get_status(self, provider_name: str, model_name: str) -> dict[str, Any]:
        """Fetch a summary of health metrics for a model."""
        with self._lock:
            metrics = self._get_metrics(provider_name, model_name)
            return {
                "online": metrics.online,
                "avg_latency": metrics.avg_latency,
                "consecutive_failures": metrics.consecutive_failures,
                "success_rate": metrics.success_rate,
                "last_successful_request": metrics.last_successful_request,
            }
