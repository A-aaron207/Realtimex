"""
Failover engine for handling routing retries and fallback models in the Realtimex Model Gateway.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Coroutine

from models.exceptions import FailoverError, NoCompatibleProviderError, QuotaExceededError
from models.provider import ModelRequest, ModelResponse
from models.registry import ModelRegistry
from models.selector import ModelSelector


class FailoverEngine:
    """
    Coordinates fallback execution across compatible providers when primary providers
    fail, timeout, or exceed quotas.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        selector: ModelSelector,
        health_monitor: Any,
        quota_manager: Any,
        event_bus: Any = None,
        logger: logging.Logger | None = None,
        metrics: Any = None,
    ) -> None:
        self.registry = registry
        self.selector = selector
        self.health_monitor = health_monitor
        self.quota_manager = quota_manager
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger("realtimex.models.failover")
        self.metrics = metrics

    async def execute_with_failover(
        self,
        request: ModelRequest,
        execute_fn: Callable[[str, str, ModelRequest], Coroutine[Any, Any, ModelResponse]],
    ) -> ModelResponse:
        """
        Execute request, trying alternative models if failure or quota limit occurs.

        Args:
            request: The ModelRequest.
            execute_fn: Async callback performing the raw adapter call.

        Returns:
            The successful ModelResponse.

        Raises:
            FailoverError: If all candidate models fail or are rate-limited.
        """
        exclude_set: set[tuple[str, str]] = set()
        last_exception: Exception | None = None

        while True:
            # 1. Select best model excluding failed ones
            try:
                model_meta = self.selector.select_model(request, exclude=exclude_set)
            except NoCompatibleProviderError as e:
                # No compatible models left to try
                if last_exception:
                    raise FailoverError(
                        f"All compatible models failed or exceeded quota. Last error: {last_exception}"
                    ) from last_exception
                raise NoCompatibleProviderError("No compatible healthy models are available.") from e

            provider = model_meta.provider_name
            model = model_meta.model_name
            t_key = (provider, model)

            # 2. Check Quota
            # Estimate tokens: prompt length + 1000 buffer
            estimated_tokens = (len(request.prompt) // 4) + 1000
            rpm = model_meta.rate_limits.get("rpm")
            tpm = model_meta.rate_limits.get("tpm")
            rpd = model_meta.rate_limits.get("rpd")
            
            under_quota = self.quota_manager.check_quota(
                provider_name=provider,
                estimated_tokens=estimated_tokens,
                rpm_limit=rpm,
                tpm_limit=tpm,
                rpd_limit=rpd,
            )

            if not under_quota:
                self.logger.warning("Quota exceeded for provider '%s' (model '%s'). Retrying alternative...", provider, model)
                self._emit_event("QuotaExceeded", request.task_id, {"provider": provider, "model": model})
                self._emit_event("FailoverTriggered", request.task_id, {"provider": provider, "model": model, "reason": "quota_exceeded"})
                exclude_set.add(t_key)
                continue

            # 3. Execute
            self.logger.info("Selected model '%s/%s' for task %s", provider, model, request.task_id)
            self._emit_event("ModelSelected", request.task_id, {"provider": provider, "model": model})
            self._emit_event("RequestStarted", request.task_id, {"provider": provider, "model": model})

            try:
                start_time = time.time()
                response = await execute_fn(provider, model, request)
                latency = time.time() - start_time

                # Success! Record metrics and quota
                self.health_monitor.record_success(provider, model, latency)
                
                # Update registry average latency
                self.registry.update_model_latency(provider, model, latency)
                
                # Consume quota
                total_tokens = response.token_usage.get("total_tokens", estimated_tokens)
                self.quota_manager.consume(provider, total_tokens)

                if self.metrics is not None:
                    self.metrics.record_model_usage(provider, model, True, latency, total_tokens, len(exclude_set))

                self._emit_event(
                    "RequestCompleted",
                    request.task_id,
                    {
                        "provider": provider,
                        "model": model,
                        "latency": latency,
                        "tokens": total_tokens,
                    },
                )
                return response

            except Exception as e:
                self.logger.error("Request failed on model '%s/%s': %s", provider, model, e)
                last_exception = e
                
                # Record failure in health monitor
                self.health_monitor.record_failure(provider, model)
                
                # Mark as unhealthy if it crossed threshold
                if not self.health_monitor.is_model_healthy(provider, model):
                    self.registry.update_model_health(provider, model, "unhealthy")
                    self._emit_event("ProviderUnavailable", request.task_id, {"provider": provider, "model": model})

                if self.metrics is not None:
                    self.metrics.record_model_usage(provider, model, False, time.time() - start_time, estimated_tokens, len(exclude_set))

                self._emit_event("RequestFailed", request.task_id, {"provider": provider, "model": model, "error": str(e)})
                self._emit_event("FailoverTriggered", request.task_id, {"provider": provider, "model": model, "reason": "execution_failed"})
                
                exclude_set.add(t_key)

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        """Helper to emit events to EventBus if present."""
        if self.event_bus is not None:
            try:
                from events.event import Event, EventPriority
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="models.failover",
                        task_id=task_id,
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as ex:
                self.logger.warning("Failover engine failed to emit event %s: %s", name, ex)
