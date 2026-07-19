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
    capabilities = ["summarize_text", "generate_text", "generate_code", "permission_check"]

    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        return "Provides text summarization, generation, coding, and permission checks via Model Gateway."

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

    def generate_text(self, input_data: dict[str, Any] | str) -> dict[str, Any]:
        """
        Execute text generation using the model_gateway service.
        """
        import asyncio
        from services.registry import ServiceRegistry
        from models.provider import ModelRequest

        # Resolve model_gateway service
        registry = ServiceRegistry.get_instance()
        gateway_service = registry.get("model_gateway")
        model_gateway = gateway_service.metadata["gateway"]

        if isinstance(input_data, dict):
            prompt = input_data.get("prompt") or input_data.get("text") or str(input_data)
        else:
            prompt = str(input_data)

        # Build ModelRequest
        request = ModelRequest(
            task_id="generate_text_task",
            request_type="generate",
            capability_required="reasoning",
            prompt=prompt,
            preferred_model="llama3-70b-8192"
        )

        response = asyncio.run(model_gateway.generate(request))

        return {
            "summary": response.output,
            "output": response.output,
            "provider": response.provider_used,
            "model": response.model_used,
            "latency": response.latency
        }

    def generate_code(self, input_data: dict[str, Any] | str) -> dict[str, Any]:
        """
        Execute code generation using the model_gateway service.
        """
        import asyncio
        from services.registry import ServiceRegistry
        from models.provider import ModelRequest

        # Resolve model_gateway service
        registry = ServiceRegistry.get_instance()
        gateway_service = registry.get("model_gateway")
        model_gateway = gateway_service.metadata["gateway"]

        if isinstance(input_data, dict):
            prompt = input_data.get("prompt") or input_data.get("instruction") or str(input_data)
        else:
            prompt = str(input_data)

        # Build ModelRequest
        request = ModelRequest(
            task_id="generate_code_task",
            request_type="generate",
            capability_required="code_generation",
            prompt=prompt,
            preferred_model="llama3-70b-8192"
        )

        response = asyncio.run(model_gateway.generate(request))

        return {
            "summary": response.output,
            "output": response.output,
            "provider": response.provider_used,
            "model": response.model_used,
            "latency": response.latency
        }

    def permission_check(self, context: Any) -> dict[str, Any]:
        """
        Check context permissions and return verification.
        """
        if isinstance(context, dict):
            # Fallback to trigger ExecutionContext call in WorkerRuntime
            raise TypeError("Expected ExecutionContext")
        
        perms = context.permissions
        if hasattr(perms, "to_dict") and callable(perms.to_dict):
            perms_val = perms.to_dict()
        elif hasattr(perms, "__dict__"):
            perms_val = {k: str(v) for k, v in perms.__dict__.items()}
        else:
            perms_val = str(perms)

        return {
            "summary": f"Context permissions: {perms_val}",
            "output": f"Context permissions: {perms_val}",
            "permissions": perms_val,
            "status": "SUCCESS"
        }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized execution entry point mapping capabilities to methods."""
        if capability == "summarize_text":
            return self.summarize_text(context.input)
        elif capability == "generate_text":
            return self.generate_text(context.input)
        elif capability == "generate_code":
            return self.generate_code(context.input)
        elif capability == "permission_check":
            return self.permission_check(context)
        else:
            raise NotImplementedError(f"Capability {capability} not supported by this module.")




