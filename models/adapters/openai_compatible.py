"""
OpenAI-compatible provider adapter for the Realtimex Model Gateway.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from models.provider import ModelRequest, ModelResponse, ProviderAdapter


class OpenAICompatibleAdapter(ProviderAdapter):
    """
    Adapter for any OpenAI-compatible API gateway (e.g. self-hosted LocalAI, Ollama, OpenAI itself).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "openai_compatible",
                "model_name": "gpt-4o",
                "context_window": 128000,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation", "structured_output"],
                "cost_metadata": {"input_cost_1k": 0.0050, "output_cost_1k": 0.0150},
                "rate_limits": {"rpm": 200, "tpm": 80000},
            },
            {
                "provider_name": "openai_compatible",
                "model_name": "gpt-4-turbo",
                "context_window": 128000,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0100, "output_cost_1k": 0.0300},
                "rate_limits": {"rpm": 150, "tpm": 60000},
            },
        ]

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        start_time = time.time()
        
        # Simulate network delay
        latency = 0.18 + (len(request.prompt) * 0.0001)
        await asyncio.sleep(latency)

        prompt_words = len(request.prompt.split())
        completion = (
            f"Simulated OpenAI Response ({model}) for prompt: '{request.prompt[:30]}...'. "
            f"Processed prompt with context."
        )
        completion_words = len(completion.split())

        prompt_tokens = int(prompt_words * 1.3)
        completion_tokens = int(completion_words * 1.3)
        token_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }

        return ModelResponse(
            output=completion,
            provider_used="openai_compatible",
            model_used=model,
            token_usage=token_usage,
            latency=time.time() - start_time,
            finish_reason="stop",
            metadata={"simulated": True, "api_base": self.base_url},
        )

    async def stream(self, model: str, request: ModelRequest) -> AsyncIterator[str]:
        chunks = [
            f"[OpenAICompatible - {model}] Establishing socket connection... ",
            "Transmitting stream tokens. ",
            "Data chunk A. ",
            "Data chunk B. ",
            "Finished OpenAI-compatible socket stream."
        ]

        for chunk in chunks:
            await asyncio.sleep(0.05)
            yield chunk

    async def health(self) -> dict[str, Any]:
        return {
            "status": "online" if self._initialized else "offline",
            "latency": 0.18,
            "success_rate": 1.0,
        }

    async def shutdown(self) -> None:
        self._initialized = False
