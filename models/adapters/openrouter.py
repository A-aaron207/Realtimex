"""
OpenRouter provider adapter for the Realtimex Model Gateway.
"""

from __future__ import annotations

from typing import Any

from models.adapters.openai_compatible import OpenAICompatibleAdapter


class OpenRouterAdapter(OpenAICompatibleAdapter):
    """
    Adapter for OpenRouter API, listing open source models.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        import os
        resolved_key = api_key or os.getenv("OPENROUTER_API_KEY")
        super().__init__(
            api_key=resolved_key,
            base_url=base_url or "https://openrouter.ai/api/v1"
        )

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "openrouter",
                "model_name": "meta-llama/llama-3.1-70b-instruct",
                "context_window": 128000,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.00035, "output_cost_1k": 0.0004},
                "rate_limits": {"rpm": 120, "tpm": 40000},
                "is_open_source": True,
            },
            {
                "provider_name": "openrouter",
                "model_name": "meta-llama/llama-3.1-8b-instruct",
                "context_window": 128000,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.00007, "output_cost_1k": 0.00007},
                "rate_limits": {"rpm": 120, "tpm": 40000},
                "is_open_source": True,
            },
            {
                "provider_name": "openrouter",
                "model_name": "mistralai/mixtral-8x7b-instruct",
                "context_window": 32768,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization"],
                "cost_metadata": {"input_cost_1k": 0.00027, "output_cost_1k": 0.00027},
                "rate_limits": {"rpm": 100, "tpm": 30000},
                "is_open_source": True,
            },
            {
                "provider_name": "openrouter",
                "model_name": "google/gemma-2-27b-it",
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization"],
                "cost_metadata": {"input_cost_1k": 0.00027, "output_cost_1k": 0.00027},
                "rate_limits": {"rpm": 100, "tpm": 30000},
                "is_open_source": True,
            },
        ]
