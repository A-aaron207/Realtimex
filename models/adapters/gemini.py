"""
Gemini and Gemma provider adapter for the Realtimex Model Gateway.
"""

from __future__ import annotations

from typing import Any

from models.adapters.openai_compatible import OpenAICompatibleAdapter


class GeminiAdapter(OpenAICompatibleAdapter):
    """
    Adapter for Google Gemini API, supporting Gemini and Gemma open-source models.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        import os
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        super().__init__(
            api_key=resolved_key,
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        )

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "provider_name": "gemini",
                "model_name": "gemini-1.5-pro",
                "context_window": 2000000,
                "max_tokens": 8192,
                "capabilities": ["reasoning", "summarization", "code_generation", "structured_output"],
                "cost_metadata": {"input_cost_1k": 0.007, "output_cost_1k": 0.021},
                "rate_limits": {"rpm": 360, "tpm": 120000},
                "is_open_source": False,
            },
            {
                "provider_name": "gemini",
                "model_name": "gemini-1.5-flash",
                "context_window": 1000000,
                "max_tokens": 8192,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.00035, "output_cost_1k": 0.00105},
                "rate_limits": {"rpm": 360, "tpm": 120000},
                "is_open_source": False,
            },
            {
                "provider_name": "gemini",
                "model_name": "gemma-2-27b-it",
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0, "output_cost_1k": 0.0},
                "rate_limits": {"rpm": 60, "tpm": 30000},
                "is_open_source": True,
            },
        ]
