"""
Core gateway implementation for the Realtimex Model Gateway.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from events.event import Event, EventPriority
from events.event_types import ModelGatewayEventType
from models.adapters.groq import GroqAdapter
from models.adapters.nvidia import NvidiaAdapter
from models.adapters.openai_compatible import OpenAICompatibleAdapter
from models.adapters.openrouter import OpenRouterAdapter
from models.adapters.gemini import GeminiAdapter
from models.cache import ResponseCache
from models.exceptions import ModelGatewayError, NoCompatibleProviderError, ProviderUnavailableError
from models.failover import FailoverEngine
from models.health import HealthMonitor
from models.metrics import GatewayMetrics
from models.provider import ModelRequest, ModelResponse
from models.quota import QuotaManager
from models.registry import ModelMetadata, ModelRegistry
from models.selector import ModelSelector
from models.routing import RequestRouter


class ModelGateway:
    """
    Unified entry point for routing AI model requests across various providers.
    Supports routing, failover, quota checks, caching, and health metrics.
    """

    def __init__(
        self,
        event_bus: Any = None,
        config: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logger or logging.getLogger("realtimex.models.gateway")

        # Instantiate subcomponents
        self.registry = ModelRegistry()
        self.health_monitor = HealthMonitor()
        self.quota_manager = QuotaManager()
        self.cache = ResponseCache()
        self.selector = ModelSelector(self.registry, self.health_monitor)
        self.router = RequestRouter(self.registry)
        self.metrics = GatewayMetrics()

        self.failover_engine = FailoverEngine(
            registry=self.registry,
            selector=self.selector,
            health_monitor=self.health_monitor,
            quota_manager=self.quota_manager,
            event_bus=self.event_bus,
            logger=self.logger,
            metrics=self.metrics,
        )

    async def initialize(self) -> None:
        """
        Bootstrap and register standard provider adapters.
        """
        self.logger.info("Initializing Model Gateway...")

        # Load API configurations if available in config
        gateway_config = self.config.get("model_gateway", {})
        
        # 1. Register Groq
        groq_cfg = gateway_config.get("groq", {})
        groq = GroqAdapter(
            api_key=groq_cfg.get("api_key"),
            base_url=groq_cfg.get("base_url"),
            model_fallback_chain=groq_cfg.get("model_fallback_chain"),
            temperature=groq_cfg.get("temperature", 0.4),
        )
        await groq.initialize()
        self.registry.register_provider("groq", groq)
        for m in await groq.list_models():
            self.registry.register_model(ModelMetadata.from_dict(m))
        self._emit_event(ModelGatewayEventType.PROVIDER_REGISTERED, "", {"provider": "groq"})


        # 2. Register NVIDIA
        nv_cfg = gateway_config.get("nvidia", {})
        nvidia = NvidiaAdapter(api_key=nv_cfg.get("api_key"), base_url=nv_cfg.get("base_url"))
        await nvidia.initialize()
        self.registry.register_provider("nvidia", nvidia)
        for m in await nvidia.list_models():
            self.registry.register_model(ModelMetadata.from_dict(m))
        self._emit_event(ModelGatewayEventType.PROVIDER_REGISTERED, "", {"provider": "nvidia"})

        # 3. Register OpenAI Compatible
        oa_cfg = gateway_config.get("openai_compatible", {})
        openai = OpenAICompatibleAdapter(api_key=oa_cfg.get("api_key"), base_url=oa_cfg.get("base_url"))
        await openai.initialize()
        self.registry.register_provider("openai_compatible", openai)
        for m in await openai.list_models():
            self.registry.register_model(ModelMetadata.from_dict(m))
        self._emit_event(ModelGatewayEventType.PROVIDER_REGISTERED, "", {"provider": "openai_compatible"})

        # 4. Register OpenRouter
        or_cfg = gateway_config.get("openrouter", {})
        openrouter = OpenRouterAdapter(api_key=or_cfg.get("api_key"), base_url=or_cfg.get("base_url"))
        await openrouter.initialize()
        self.registry.register_provider("openrouter", openrouter)
        for m in await openrouter.list_models():
            self.registry.register_model(ModelMetadata.from_dict(m))
        self._emit_event(ModelGatewayEventType.PROVIDER_REGISTERED, "", {"provider": "openrouter"})

        # 5. Register Gemini
        gem_cfg = gateway_config.get("gemini", {})
        gemini = GeminiAdapter(api_key=gem_cfg.get("api_key"), base_url=gem_cfg.get("base_url"))
        await gemini.initialize()
        self.registry.register_provider("gemini", gemini)
        for m in await gemini.list_models():
            self.registry.register_model(ModelMetadata.from_dict(m))
        self._emit_event(ModelGatewayEventType.PROVIDER_REGISTERED, "", {"provider": "gemini"})

        # 6. Dynamically register configured capability models in registry
        capabilities_cfg = gateway_config.get("capabilities", {})
        for cap_name, config_item in capabilities_cfg.items():
            for role in ("primary", "fallback"):
                role_cfg = config_item.get(role)
                if role_cfg:
                    provider = role_cfg.get("provider")
                    model = role_cfg.get("model")
                    if provider and model:
                        meta = self.registry.get_model_metadata(provider, model)
                        if meta is None:
                            meta = ModelMetadata(
                                provider_name=provider,
                                model_name=model,
                                context_window=32768,
                                max_tokens=4096,
                                capabilities=[cap_name],
                                is_open_source=True
                            )
                            self.registry.register_model(meta)
                        else:
                            if cap_name not in meta.capabilities:
                                meta.capabilities.append(cap_name)

        self.logger.info("Model Gateway initialization completed.")

    async def generate(self, request: ModelRequest | None = None, **kwargs) -> ModelResponse:
        """
        Execute standard model text generation.
        Supports both direct ModelRequest objects and dynamic capability-based keyword calls.
        """
        if request is None:
            task_id = kwargs.get("task_id", "dynamic_task")
            request_type = kwargs.get("request_type", "generate")
            capability = kwargs.get("capability") or kwargs.get("capability_required") or "chat"
            prompt = kwargs.get("prompt", "")
            context = kwargs.get("context", {})
            constraints = kwargs.get("constraints", [])
            preferred_model = kwargs.get("preferred_model")
            streaming = kwargs.get("streaming", False)
            parameters = kwargs.get("parameters", {})
            request = ModelRequest(
                task_id=task_id,
                request_type=request_type,
                capability_required=capability,
                prompt=prompt,
                context=context,
                constraints=constraints,
                preferred_model=preferred_model,
                streaming=streaming,
                parameters=parameters,
            )

        if not self.registry.list_providers():
            await self.initialize()

        self.metrics.record_request()

        # Check Cache
        cached_resp = self.cache.get(
            prompt=request.prompt,
            context=request.context,
            model=request.preferred_model or "auto",
            parameters=request.parameters,
        )

        if cached_resp is not None:
            self.logger.debug("Cache hit for request: '%s'", request.prompt[:30])
            self.metrics.record_cache_hit()
            self._emit_event(ModelGatewayEventType.CACHE_HIT, request.task_id, {"prompt": request.prompt[:30]})
            return cached_resp

        self.metrics.record_cache_miss()
        self._emit_event(ModelGatewayEventType.CACHE_MISS, request.task_id, {"prompt": request.prompt[:30]})

        # Execute through FailoverEngine
        try:
            response = await self.failover_engine.execute_with_failover(
                request=request,
                execute_fn=self.router.route_generate,
            )
        except Exception as e:
            error_msg = str(e)
            # Detect the specific cause so the user gets a useful message
            if "name resolution" in error_msg or "Errno -3" in error_msg or "Temporary failure" in error_msg:
                friendly = (
                    "⚠ No internet connection — cannot reach the AI model (Groq/OpenRouter).\n"
                    "Please check your network and try again."
                )
            elif "exhausted" in error_msg.lower() or "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                friendly = (
                    "⚠ All AI model providers are rate-limited or quota-exhausted.\n"
                    "Please wait a few minutes and try again."
                )
            elif "Credentials not configured" in error_msg or "mock values" in error_msg:
                friendly = (
                    "⚠ AI model credentials are not configured.\n"
                    "Please add your API key to config/config.json or .env."
                )
            else:
                friendly = f"⚠ AI model unavailable: {error_msg}"

            self.logger.error("All provider routes failed — returning error to user. Error: %s", e)
            import time as _time
            response = ModelResponse(
                output=friendly,
                provider_used="error",
                model_used="none",
                token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency=0.0,
                finish_reason="error",
                metadata={"error": True, "error_message": error_msg},
            )
            self._emit_event(
                ModelGatewayEventType.REQUEST_COMPLETED,
                request.task_id,
                {"provider": "error", "model": "none", "latency": 0.0, "tokens": 0},
            )
            if hasattr(self, "metrics") and self.metrics:
                self.metrics.record_model_usage("error", "none", False, 0.0, 0)

        # Cache response
        self.cache.set(
            prompt=request.prompt,
            context=request.context,
            model=request.preferred_model or "auto",
            parameters=request.parameters,
            response=response,
        )

        # Record metrics usage
        cost_meta = self.registry.get_model_metadata(response.provider_used, response.model_used)
        total_tokens = response.token_usage.get("total_tokens", 0)
        cost = 0.0
        if cost_meta:
            input_tokens = response.token_usage.get("prompt_tokens", 0)
            output_tokens = response.token_usage.get("completion_tokens", 0)
            cost = (
                (input_tokens / 1000.0) * cost_meta.cost_metadata.get("input_cost_1k", 0.0)
                + (output_tokens / 1000.0) * cost_meta.cost_metadata.get("output_cost_1k", 0.0)
            )
        self.metrics.record_provider_usage(response.provider_used, total_tokens, cost)

        return response

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        """
        Execute streaming model generation.
        Supports initial failover if the selected model fails to start streaming.
        """
        self.metrics.record_request()
        exclude_set: set[tuple[str, str]] = set()

        while True:
            try:
                model_meta = self.selector.select_model(request, exclude=exclude_set)
            except NoCompatibleProviderError as e:
                raise NoCompatibleProviderError("No compatible healthy models are available for streaming.") from e

            provider = model_meta.provider_name
            model = model_meta.model_name
            t_key = (provider, model)

            # Record selection and execution start
            self._emit_event(ModelGatewayEventType.MODEL_SELECTED, request.task_id, {"provider": provider, "model": model})
            self._emit_event(ModelGatewayEventType.REQUEST_STARTED, request.task_id, {"provider": provider, "model": model, "streaming": True})

            try:
                # Try getting the stream iterator from the router
                async for chunk in self.router.route_stream(provider, model, request):
                    yield chunk

                # Success, record metric
                self.health_monitor.record_success(provider, model, 0.1) # Default tiny latency for streaming
                self._emit_event(ModelGatewayEventType.REQUEST_COMPLETED, request.task_id, {"provider": provider, "model": model, "streaming": True})
                return

            except Exception as e:
                self.logger.error("Streaming request failed on model '%s/%s': %s", provider, model, e)
                self.health_monitor.record_failure(provider, model)
                
                if not self.health_monitor.is_model_healthy(provider, model):
                    self.registry.update_model_health(provider, model, "unhealthy")
                    self._emit_event(ModelGatewayEventType.PROVIDER_UNAVAILABLE, request.task_id, {"provider": provider, "model": model})

                self._emit_event(ModelGatewayEventType.REQUEST_FAILED, request.task_id, {"provider": provider, "model": model, "error": str(e)})
                self._emit_event(ModelGatewayEventType.FAILOVER_TRIGGERED, request.task_id, {"provider": provider, "model": model, "reason": "streaming_failed"})
                
                self.metrics.record_failover()
                exclude_set.add(t_key)

    def list_models(self, capability: str | None = None, active_only: bool = False) -> list[ModelMetadata]:
        """
        List all registered models.
        """
        return self.registry.list_models(capability=capability, active_only=active_only)

    def list_providers(self) -> list[str]:
        """
        List all registered provider adapters.
        """
        return self.registry.list_providers()

    async def provider_health(self, provider_name: str) -> dict[str, Any]:
        """
        Check health of a specific provider.
        Supports transitioning from unhealthy to healthy (ProviderRecovered).
        """
        adapter = self.registry.get_adapter(provider_name)
        if adapter is None:
            raise ProviderUnavailableError(f"No registered adapter for provider: '{provider_name}'")

        status_info = await adapter.health()
        
        # Check if we need to recover the provider in the registry
        is_online = status_info.get("status") == "online"
        
        # Check all models for this provider
        models = self.registry.list_models()
        provider_models = [m for m in models if m.provider_name.lower() == provider_name.lower()]

        for model in provider_models:
            was_unhealthy = model.health_status == "unhealthy"
            if is_online:
                if was_unhealthy:
                    self.registry.update_model_health(provider_name, model.model_name, "healthy")
                    self._emit_event(ModelGatewayEventType.PROVIDER_RECOVERED, "", {"provider": provider_name, "model": model.model_name})
            else:
                self.registry.update_model_health(provider_name, model.model_name, "unhealthy")

        return status_info

    def invalidate_cache(self) -> None:
        """
        Invalidate all cached items.
        """
        self.cache.invalidate()

    def _emit_event(self, name: str, task_id: str, payload: dict[str, Any]) -> None:
        """Internal helper to publish a transaction event."""
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="models.gateway",
                        task_id=task_id,
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Failed to emit gateway transaction event %s: %s", name, e)
