"""
Unit tests for the Realtimex Model Gateway.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, AsyncIterator

from events.event import Event
from events.event_types import ModelGatewayEventType
from models.exceptions import FailoverError, NoCompatibleProviderError, ProviderUnavailableError
from models.gateway import ModelGateway
from models.provider import ModelRequest, ModelResponse, ProviderAdapter
from models.registry import ModelMetadata


class DummyEventBus:
    """Mock event bus to collect emitted gateway events."""

    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class FaultyProviderAdapter(ProviderAdapter):
    """Mock provider adapter designed to consistently throw errors to trigger failover."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "faulty",
                "model_name": self.model_name,
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning"],
                "cost_metadata": {"input_cost_1k": 0.0, "output_cost_1k": 0.0},
                "rate_limits": {"rpm": 100, "tpm": 40000},
            }
        ]

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        raise ConnectionError("Simulated provider connection timeout.")

    async def stream(self, model: str, request: ModelRequest) -> AsyncIterator[str]:
        raise ConnectionError("Simulated streaming initiation failure.")
        # Need this to satisfy async generator syntax
        yield ""

    async def health(self) -> dict[str, Any]:
        return {"status": "degraded"}

    async def shutdown(self) -> None:
        self._initialized = False


class TestModelGateway(unittest.IsolatedAsyncioTestCase):
    """Asynchronous test cases verifying Model Gateway functionality."""

    async def asyncSetUp(self) -> None:
        self.event_bus = DummyEventBus()
        self.gateway = ModelGateway(event_bus=self.event_bus)
        await self.gateway.initialize()

    async def test_initialization_registers_providers(self) -> None:
        """Verify gateway registers standard provider adapters and models."""
        providers = self.gateway.list_providers()
        self.assertIn("groq", providers)
        self.assertIn("nvidia", providers)
        self.assertIn("openai_compatible", providers)
        self.assertIn("openrouter", providers)
        self.assertIn("gemini", providers)

        models = self.gateway.list_models()
        model_names = [m.model_name for m in models]
        self.assertIn("llama3-70b-8192", model_names)
        self.assertIn("nemotron-4-340b", model_names)
        self.assertIn("gpt-4o", model_names)

        # Check emitted ProviderRegistered events
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertEqual(emitted_names.count("ProviderRegistered"), 5)

    async def test_model_selection_capabilities(self) -> None:
        """Verify model selection based on capability capabilities and preferences."""
        # 1. Structured output selection (nvidia/openai support this, groq does not)
        req_structured = ModelRequest(
            task_id="t1",
            request_type="text",
            capability_required="structured_output",
            prompt="JSON format only",
        )
        selected = self.gateway.selector.select_model(req_structured)
        self.assertIn(selected.provider_name, ["nvidia", "openai_compatible"])

        # 2. Preferred model selection
        req_pref = ModelRequest(
            task_id="t2",
            request_type="text",
            capability_required="reasoning",
            prompt="think",
            preferred_model="mixtral-8x7b-32768",
        )
        selected_pref = self.gateway.selector.select_model(req_pref)
        self.assertEqual(selected_pref.model_name, "mixtral-8x7b-32768")

    async def test_caching_hit_miss(self) -> None:
        """Verify ResponseCache stores outputs and returns hits based on prompt parameters."""
        req1 = ModelRequest(
            task_id="t_cache",
            request_type="text",
            capability_required="summarization",
            prompt="Cache me please",
            parameters={"temp": 0.0},
        )

        # First call (Cache Miss)
        resp1 = await self.gateway.generate(req1)
        self.assertEqual(self.gateway.metrics.cache_hits, 0)
        self.assertEqual(self.gateway.metrics.cache_misses, 1)

        # Second call (Cache Hit)
        resp2 = await self.gateway.generate(req1)
        self.assertEqual(self.gateway.metrics.cache_hits, 1)
        self.assertEqual(self.gateway.metrics.cache_misses, 1)
        self.assertEqual(resp1.output, resp2.output)

        # Invalidate Cache
        self.gateway.invalidate_cache()
        resp3 = await self.gateway.generate(req1)
        self.assertEqual(self.gateway.metrics.cache_hits, 1)
        self.assertEqual(self.gateway.metrics.cache_misses, 2)

    async def test_quota_manager_rerouting(self) -> None:
        """Verify quota exhaustion forces selection to route to alternative models."""
        provider_name = "groq"
        model_name = "llama3-70b-8192"

        # Exceed RPM quota artificially
        for _ in range(101):
            self.gateway.quota_manager.consume(provider_name, 100)

        # The selector itself does not block quota, routing does.
        # Let's request reasoning. Llama3-70b-8192 is now blocked.
        # The routing should automatically fall back to mixtral-8x7b-32768 (same capability, under quota).
        req = ModelRequest(
            task_id="t_quota",
            request_type="text",
            capability_required="reasoning",
            prompt="Hello world",
            preferred_model=model_name, # Try requesting llama3
        )
        
        resp = await self.gateway.generate(req)
        # Should fallback to Mixtral or GPT-4o
        self.assertNotEqual(resp.model_used, model_name)
        self.assertIn("QuotaExceeded", [e.name for e in self.event_bus.emitted])

    async def test_failover_transparent_retry(self) -> None:
        """Verify transparent failover works when a provider raises errors."""
        # 1. Register a Faulty provider
        faulty = FaultyProviderAdapter(model_name="unstable-model")
        await faulty.initialize()
        self.gateway.registry.register_provider("faulty", faulty)
        for m in await faulty.list_models():
            self.gateway.registry.register_model(ModelMetadata.from_dict(m))

        # Adjust the faulty model to have high selection priority by modifying registry latency
        metadata = self.gateway.registry.get_model_metadata("faulty", "unstable-model")
        self.assertIsNotNone(metadata)
        metadata.latency = 0.01  # Set extremely low latency to guarantee primary selection

        self.gateway.health_monitor.failure_threshold = 1

        # 2. Trigger generate call. The first try will target "faulty/unstable-model" and fail.
        # It should catch ConnectionError, label it unhealthy, trigger failover, and fallback
        # to a healthy provider (e.g. Llama3 or GPT-4o) transparently to the caller!
        req = ModelRequest(
            task_id="t_failover",
            request_type="text",
            capability_required="reasoning",
            prompt="Verify failover",
            preferred_model="unstable-model", # force selector to pick this first
        )

        response = await self.gateway.generate(req)
        
        # Verify execution completed using a healthy fallback provider
        self.assertNotEqual(response.provider_used, "faulty")
        self.assertIn(response.provider_used, ["groq", "openai_compatible", "nvidia", "mock"])

        # Check that events record the failover
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("RequestFailed", emitted_names)
        self.assertIn("FailoverTriggered", emitted_names)
        self.assertIn("RequestCompleted", emitted_names)
        
        # Faulty model should now be flagged as unhealthy
        self.assertFalse(self.gateway.health_monitor.is_model_healthy("faulty", "unstable-model"))

    async def test_streaming_generation(self) -> None:
        """Verify async streaming outputs chunks and handles initial failover."""
        req = ModelRequest(
            task_id="t_stream",
            request_type="text",
            capability_required="code_generation",
            prompt="def hello():",
            streaming=True,
        )

        chunks = []
        async for chunk in self.gateway.stream(req):
            chunks.append(chunk)

        self.assertTrue(len(chunks) > 0)
        self.assertTrue(any("hello" in c or "Code" in c or "Establish" in c or "Groq" in c for c in chunks))

    async def test_provider_health_recovery(self) -> None:
        """Verify that provider health checks update states and trigger recoveries."""
        # Force a model to be unhealthy
        self.gateway.health_monitor.record_failure("groq", "llama3-70b-8192")
        self.gateway.health_monitor.record_failure("groq", "llama3-70b-8192")
        self.gateway.health_monitor.record_failure("groq", "llama3-70b-8192")

        meta = self.gateway.registry.get_model_metadata("groq", "llama3-70b-8192")
        self.assertIsNotNone(meta)
        meta.health_status = "unhealthy"

        # Query provider_health - should test the Groq adapter and mark it healthy since health returns 'online'
        status = await self.gateway.provider_health("groq")
        self.assertEqual(status["status"], "online")

        # It should have recovered and changed registry back to healthy, emitting ProviderRecovered event
        meta_after = self.gateway.registry.get_model_metadata("groq", "llama3-70b-8192")
        self.assertEqual(meta_after.health_status, "healthy")
        
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("ProviderRecovered", emitted_names)


    async def test_capability_based_routing_and_telemetry(self) -> None:
        """Verify dynamic capability keyword generation and per-model telemetry tracking."""
        # 1. Invoke generate with capability keyword args
        response = await self.gateway.generate(
            capability="coding",
            prompt="write python code",
            task_id="t_capability_dynamic"
        )
        self.assertIsNotNone(response.output)
        
        # 2. Check telemetry recording in metrics
        metrics_summary = self.gateway.metrics.get_summary()
        self.assertIn("model_stats", metrics_summary)
        model_stats = metrics_summary["model_stats"]
        self.assertTrue(len(model_stats) > 0)
        
        # Verify that the keys in model_stats have stats properties
        for key, stats in model_stats.items():
            self.assertIn("calls", stats)
            self.assertIn("successes", stats)
            self.assertIn("failures", stats)
            self.assertIn("avg_latency", stats)


if __name__ == "__main__":
    unittest.main()
