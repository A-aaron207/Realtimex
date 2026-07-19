"""
Groq provider adapter for the Realtimex Model Gateway.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator

from models.provider import ModelRequest, ModelResponse, ProviderAdapter


class GroqAdapter(ProviderAdapter):
    """
    Adapter for the Groq Cloud API, supporting simulated behavior in the absence of credentials.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        import os
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = base_url or "https://api.groq.com/openai/v1"
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "groq",
                "model_name": "llama3-70b-8192",
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0007, "output_cost_1k": 0.0009},
                "rate_limits": {"rpm": 100, "tpm": 30000},
                "is_open_source": True,
            },
            {
                "provider_name": "groq",
                "model_name": "llama3-8b-8192",
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0001, "output_cost_1k": 0.0002},
                "rate_limits": {"rpm": 100, "tpm": 30000},
                "is_open_source": True,
            },
            {
                "provider_name": "groq",
                "model_name": "mixtral-8x7b-32768",
                "context_window": 32768,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization"],
                "cost_metadata": {"input_cost_1k": 0.0005, "output_cost_1k": 0.0006},
                "rate_limits": {"rpm": 60, "tpm": 20000},
                "is_open_source": True,
            },
            {
                "provider_name": "groq",
                "model_name": "gemma-7b-it",
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization"],
                "cost_metadata": {"input_cost_1k": 0.0002, "output_cost_1k": 0.0002},
                "rate_limits": {"rpm": 100, "tpm": 30000},
                "is_open_source": True,
            },
        ]

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        start_time = time.time()
        from models.exceptions import ProviderUnavailableError
        
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
                provider_used="groq",
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
            raise ProviderUnavailableError(f"Live Groq completions call failed: {e}") from e

    async def stream(self, model: str, request: ModelRequest) -> AsyncIterator[str]:
        chunks = [
            f"[Groq - {model}] Processing request... ",
            f"Prompt: '{request.prompt[:30]}...'. ",
            "Simulating async response chunk 1. ",
            "Simulating async response chunk 2. ",
            "Completed stream successfully."
        ]

        for chunk in chunks:
            await asyncio.sleep(0.06)
            yield chunk

    async def health(self) -> dict[str, Any]:
        return {
            "status": "online" if self._initialized else "offline",
            "latency": 0.15,
            "success_rate": 1.0,
        }

    async def shutdown(self) -> None:
        self._initialized = False
