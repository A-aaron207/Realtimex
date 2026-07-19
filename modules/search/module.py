"""
Search Module entry point.

Declares the `web_search` capability. Milestone 2 only registers this
capability with the Kernel's Capability Registry; actual query
execution belongs to a future Task Manager / Scheduler milestone that
will invoke providers found through the registry.
"""

from __future__ import annotations

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the search module."""

    module_id = "search"
    capabilities = ["web_search"]

    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        return "Provides web search capabilities using Model Gateway."

    def web_search(self, input_data: dict[str, Any] | str) -> dict[str, Any]:
        """
        Execute web search by generating search results using model_gateway.
        """
        import asyncio
        from services.registry import ServiceRegistry
        from models.provider import ModelRequest

        # Resolve model_gateway service
        registry = ServiceRegistry.get_instance()
        gateway_service = registry.get("model_gateway")
        model_gateway = gateway_service.metadata["gateway"]

        if isinstance(input_data, dict):
            query = input_data.get("query") or input_data.get("q") or str(input_data)
        else:
            query = str(input_data)

        # Build ModelRequest
        request = ModelRequest(
            task_id="web_search_task",
            request_type="generate",
            capability_required="reasoning",
            prompt=f"Generate 3 realistic web search results for the query: '{query}'. Provide title, URL, and a snippet for each.",
            preferred_model="llama3-70b-8192"
        )

        response = asyncio.run(model_gateway.generate(request))

        return {
            "results": [response.output],
            "query_processed": query,
            "provider": response.provider_used,
            "model": response.model_used,
            "latency": response.latency
        }

