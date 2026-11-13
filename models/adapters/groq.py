"""
Groq provider adapter for the Realtimex Model Gateway.

Supports a model_fallback_chain: when a model returns a 429 (rate-limited)
or any API error, the adapter automatically tries the next model in the
configured chain before raising an error to the failover engine.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, AsyncIterator

from models.provider import ModelRequest, ModelResponse, ProviderAdapter


class GroqAdapter(ProviderAdapter):
    """
    Adapter for the Groq Cloud API with built-in per-request model fallback chain.

    Configuration (read from ``model_gateway.groq`` in config.json):
        model_fallback_chain: list[str]  — tried in order on error/429
        temperature: float               — sampling temperature (default 0.4)

    The adapter resolves its API key from (in order):
        1. ``api_key`` constructor arg
        2. ``GROQ_API_KEY`` env var
    """

    # Default chain used when none is configured
    _DEFAULT_CHAIN = [
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
        "openai/gpt-oss-20b",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model_fallback_chain: list[str] | None = None,
        temperature: float = 0.4,
    ) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.base_url = (base_url or "https://api.groq.com/openai/v1").rstrip("/")
        self.model_fallback_chain: list[str] = model_fallback_chain or self._DEFAULT_CHAIN
        self.temperature = temperature
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def list_models(self) -> list[dict[str, Any]]:
        """
        Return metadata for every model in the fallback chain.
        Models that are not pre-known get a sensible default metadata record.
        """
        known: dict[str, dict[str, Any]] = {
            "llama3-70b-8192": {
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0007, "output_cost_1k": 0.0009},
                "rate_limits": {"rpm": 100, "tpm": 30000},
            },
            "llama3-8b-8192": {
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization", "code_generation"],
                "cost_metadata": {"input_cost_1k": 0.0001, "output_cost_1k": 0.0002},
                "rate_limits": {"rpm": 100, "tpm": 30000},
            },
            "mixtral-8x7b-32768": {
                "context_window": 32768,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization"],
                "cost_metadata": {"input_cost_1k": 0.0005, "output_cost_1k": 0.0006},
                "rate_limits": {"rpm": 60, "tpm": 20000},
            },
            "gemma-7b-it": {
                "context_window": 8192,
                "max_tokens": 4096,
                "capabilities": ["reasoning", "summarization"],
                "cost_metadata": {"input_cost_1k": 0.0002, "output_cost_1k": 0.0002},
                "rate_limits": {"rpm": 100, "tpm": 30000},
            },
            "openai/gpt-oss-120b": {
                "context_window": 131072,
                "max_tokens": 8192,
                "capabilities": [
                    "reasoning", "coding", "code_generation", "chat", "summarization",
                    "classification", "planning", "repair", "translation",
                    "tool_selection", "intent_detection",
                ],
                "cost_metadata": {"input_cost_1k": 0.0009, "output_cost_1k": 0.0018},
                "rate_limits": {"rpm": 100, "tpm": 60000},
            },
            "qwen/qwen3.6-27b": {
                "context_window": 32768,
                "max_tokens": 4096,
                "capabilities": [
                    "reasoning", "coding", "code_generation", "chat", "summarization",
                    "classification", "translation",
                ],
                "cost_metadata": {"input_cost_1k": 0.0003, "output_cost_1k": 0.0006},
                "rate_limits": {"rpm": 100, "tpm": 30000},
            },
            "openai/gpt-oss-20b": {
                "context_window": 32768,
                "max_tokens": 4096,
                "capabilities": [
                    "chat", "summarization", "classification",
                    "tool_selection", "intent_detection",
                ],
                "cost_metadata": {"input_cost_1k": 0.0001, "output_cost_1k": 0.0002},
                "rate_limits": {"rpm": 200, "tpm": 60000},
            },
        }

        model_names = list(self.model_fallback_chain)
        for base_model in ["llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma-7b-it"]:
            if base_model not in model_names:
                model_names.append(base_model)

        models = []
        for model_name in model_names:
            meta = known.get(model_name, {})
            models.append({
                "provider_name": "groq",
                "model_name": model_name,
                "context_window": meta.get("context_window", 32768),
                "max_tokens": meta.get("max_tokens", 4096),
                "capabilities": meta.get("capabilities", ["chat", "summarization"]),
                "cost_metadata": meta.get("cost_metadata", {"input_cost_1k": 0.0005, "output_cost_1k": 0.001}),
                "rate_limits": meta.get("rate_limits", {"rpm": 100, "tpm": 30000}),
                "is_open_source": True,
            })
        return models

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        """
        Generate a response, walking the fallback chain on 429 or any API error.

        The ``model`` argument is taken as a *hint* (the first model to try).
        If it is not in the fallback chain, it is prepended so it is tried first
        before the chain takes over.
        """
        from models.exceptions import ProviderUnavailableError

        if not self.api_key or self.api_key.startswith("mock_") or len(self.api_key.strip()) <= 5:
            raise ProviderUnavailableError(
                f"Groq credentials not configured. Set GROQ_API_KEY in .env."
            )

        # Build the ordered list: requested model first, then rest of chain
        chain = list(self.model_fallback_chain)
        if model and model not in chain:
            chain.insert(0, model)
        elif model and chain[0] != model:
            chain.remove(model)
            chain.insert(0, model)

        last_error: Exception | None = None
        start_time = time.time()

        for attempt_model in chain:
            try:
                response = await self._call_api(attempt_model, request, start_time)
                return response
            except _RateLimitError as e:
                # 429 — try next model in chain
                last_error = e
                continue
            except Exception as e:
                last_error = e
                # If it's a network-level error (DNS / no internet), all models
                # in the chain will fail identically — short-circuit immediately.
                err_str = str(e)
                if "Errno -3" in err_str or "name resolution" in err_str or "Temporary failure" in err_str or "Network unreachable" in err_str:
                    raise ProviderUnavailableError(
                        f"All models in Groq fallback chain exhausted. Last error: {last_error}"
                    ) from last_error
                continue

        raise ProviderUnavailableError(
            f"All models in Groq fallback chain exhausted. Last error: {last_error}"
        ) from last_error

    async def _call_api(
        self,
        model: str,
        request: ModelRequest,
        start_time: float,
    ) -> ModelResponse:
        """Execute a single HTTP call to Groq for ``model``."""
        from models.exceptions import ProviderUnavailableError

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": self.temperature,
        }
        data = json.dumps(payload).encode("utf-8")

        def _do_post() -> dict:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as http_err:
                body = http_err.read().decode("utf-8", errors="replace")
                if http_err.code == 429:
                    raise _RateLimitError(
                        f"Groq 429 rate-limit on model '{model}': {body}"
                    ) from http_err
                raise ProviderUnavailableError(
                    f"Groq HTTP {http_err.code} on model '{model}': {body}"
                ) from http_err

        response_json = await asyncio.to_thread(_do_post)

        choices = response_json.get("choices", [])
        completion = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = response_json.get("usage", {})

        return ModelResponse(
            output=completion,
            provider_used="groq",
            model_used=model,
            token_usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            latency=time.time() - start_time,
            finish_reason="stop",
            metadata={"simulated": False, "api_base": self.base_url, "model": model},
        )

    async def stream(self, model: str, request: ModelRequest) -> AsyncIterator[str]:
        chunks = [
            f"[Groq - {model}] Processing request... ",
            f"Prompt: '{request.prompt[:30]}...'. ",
            "Simulating async response chunk 1. ",
            "Simulating async response chunk 2. ",
            "Completed stream successfully."
        ]

        for chunk in chunks:
            await asyncio.sleep(0.02)
            yield chunk


    async def health(self) -> dict[str, Any]:
        return {
            "status": "online" if self._initialized else "offline",
            "latency": 0.15,
            "success_rate": 1.0,
            "model_fallback_chain": self.model_fallback_chain,
        }

    async def shutdown(self) -> None:
        self._initialized = False


class _RateLimitError(Exception):
    """Internal sentinel raised on HTTP 429 to trigger fallback chain walk."""
