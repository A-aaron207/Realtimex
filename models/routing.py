"""
Request router for delegating calls to provider adapters in the Realtimex Model Gateway.
"""

from __future__ import annotations

from typing import AsyncIterator

from models.exceptions import ProviderUnavailableError
from models.provider import ModelRequest, ModelResponse
from models.registry import ModelRegistry


class RequestRouter:
    """
    Resolves provider adapters from the registry and routes execution payloads to them.
    """

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    async def route_generate(
        self,
        provider_name: str,
        model_name: str,
        request: ModelRequest,
    ) -> ModelResponse:
        """
        Route a generation request to the appropriate provider adapter.
        """
        adapter = self.registry.get_adapter(provider_name)
        if adapter is None:
            raise ProviderUnavailableError(
                f"No adapter registered for provider: '{provider_name}'"
            )
        return await adapter.generate(model_name, request)

    async def route_stream(
        self,
        provider_name: str,
        model_name: str,
        request: ModelRequest,
    ) -> AsyncIterator[str]:
        """
        Route a streaming request to the appropriate provider adapter.
        """
        adapter = self.registry.get_adapter(provider_name)
        if adapter is None:
            raise ProviderUnavailableError(
                f"No adapter registered for provider: '{provider_name}'"
            )
        
        # Generator function delegation
        async for chunk in adapter.stream(model_name, request):
            yield chunk
