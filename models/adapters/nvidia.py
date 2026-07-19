"""
NVIDIA provider adapter for the Realtimex Model Gateway.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from models.provider import ModelRequest, ModelResponse, ProviderAdapter
from models.exceptions import ProviderUnavailableError


class NvidiaAdapter(ProviderAdapter):
    """
    Adapter for NVIDIA NIM/API endpoints, supporting simulated capabilities.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url or "https://integrate.api.nvidia.com/v1"
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "nvidia",
                "model_name": "nemotron-4-340b",
                "context_window": 4096,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation", "structured_output"],
                "cost_metadata": {"input_cost_1k": 0.0015, "output_cost_1k": 0.0015},
                "rate_limits": {"rpm": 50, "tpm": 15000},
            }
        ]

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        start_time = time.time()
        
        if not self.api_key or self.api_key.startswith("mock_") or len(self.api_key.strip()) <= 5:
            raise ProviderUnavailableError("Nvidia API key not configured or invalid.")

        # Simulate API network delay (nemotron is a bit larger)
        latency = 0.22 + (len(request.prompt) * 0.0003)
        await asyncio.sleep(latency)

        prompt_words = len(request.prompt.split())
        completion = (
            f"Simulated NVIDIA Response ({model}) for prompt: '{request.prompt[:30]}...'. "
            f"Verified constraint safety checks."
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
            provider_used="nvidia",
            model_used=model,
            token_usage=token_usage,
            latency=time.time() - start_time,
            finish_reason="stop",
            metadata={"simulated": True, "api_base": self.base_url},
        )

    async def stream(self, model: str, request: ModelRequest) -> AsyncIterator[str]:
        chunks = [
            f"[NVIDIA - {model}] Processing Nim tokens... ",
            f"Prompt: '{request.prompt[:20]}...' ",
            "Rendering chunk A. ",
            "Rendering chunk B. ",
            "Finished NIM rendering."
        ]

        for chunk in chunks:
            await asyncio.sleep(0.08)
            yield chunk

    async def health(self) -> dict[str, Any]:
        return {
            "status": "online" if self._initialized else "offline",
            "latency": 0.22,
            "success_rate": 1.0,
        }

    async def shutdown(self) -> None:
        self._initialized = False
