"""
Summarizer Module entry point.

Declares the `summarize_text` capability. This module also declares a
dependency on the `model_gateway` service, which does not yet exist in
the Kernel -- Milestone 2's loader logs that gap as a warning rather
than failing the module, since service resolution is a future
milestone's responsibility.
"""

from __future__ import annotations

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the summarizer module."""

    module_id = "summarizer"
    capabilities = ["summarize_text"]

    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        return "Provides text summarization capability via Model Gateway."

    def summarize_text(self, input_data: dict[str, Any] | str) -> dict[str, Any]:
        """
        Execute summarization using the model_gateway service.
        """
        import asyncio
        from services.registry import ServiceRegistry
        from models.provider import ModelRequest

        # Resolve model_gateway service
        registry = ServiceRegistry.get_instance()
        gateway_service = registry.get("model_gateway")
        model_gateway = gateway_service.metadata["gateway"]

        # Parse text from input
        if isinstance(input_data, dict):
            text = input_data.get("text") or input_data.get("prompt") or str(input_data)
        else:
            text = str(input_data)

        # Build ModelRequest
        request = ModelRequest(
            task_id="summarize_task",
            request_type="generate",
            capability_required="summarization",
            prompt=f"Summarize the following text: {text}",
            preferred_model="llama3-70b-8192"
        )

        # Run gateway generation synchronously
        response = asyncio.run(model_gateway.generate(request))

        # Return summary and cost details
        return {
            "summary": response.output,
            "provider": response.provider_used,
            "model": response.model_used,
            "latency": response.latency
        }

