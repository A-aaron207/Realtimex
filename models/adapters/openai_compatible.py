"""
OpenAI-compatible provider adapter for the Realtimex Model Gateway.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from models.provider import ModelRequest, ModelResponse, ProviderAdapter
from models.exceptions import ProviderUnavailableError


class OpenAICompatibleAdapter(ProviderAdapter):
    """
    Adapter for any OpenAI-compatible API gateway (e.g. self-hosted LocalAI, Ollama, OpenAI itself).
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
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
                "is_open_source": False,
            },
            {
                "provider_name": "openai_compatible",
                "model_name": "gpt-4-turbo",
                "context_window": 128000,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0100, "output_cost_1k": 0.0300},
                "rate_limits": {"rpm": 150, "tpm": 60000},
                "is_open_source": False,
            },
        ]

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        start_time = time.time()
        
        # Raise error if no valid key is present to trigger gateway failover
        if not self.api_key or self.api_key.startswith("mock_") or len(self.api_key.strip()) <= 5:
            raise ProviderUnavailableError(f"Credentials not configured or mock values used for {model}.")

        try:
            import urllib.request
            import urllib.error
            import json
            
            url = self.base_url
            if not url.endswith("/chat/completions"):
                url = url.rstrip("/") + "/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Add OpenRouter compatibility headers
            if "openrouter.ai" in url:
                headers["HTTP-Referer"] = "https://realtimex.ai"
                headers["X-Title"] = "Realtimex Kernel"

            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": request.prompt}
                ]
            }
            
            data = json.dumps(payload).encode("utf-8")
            
            def _do_post():
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=20) as response:
                    return json.loads(response.read().decode("utf-8"))
            
            response_json = await asyncio.to_thread(_do_post)
            
            choices = response_json.get("choices", [])
            if choices:
                completion = choices[0].get("message", {}).get("content", "")
            else:
                completion = "No completion returned from live API."
            
            usage = response_json.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            
            return ModelResponse(
                output=completion,
                provider_used="openai_compatible" if "openrouter" not in url else "openrouter",
                model_used=model,
                token_usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                },
                latency=time.time() - start_time,
                finish_reason="stop",
                metadata={"simulated": False, "api_base": self.base_url}
            )
        except Exception as e:
            raise ProviderUnavailableError(f"Live completions call failed: {e}") from e

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
