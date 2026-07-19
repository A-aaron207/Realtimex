"""
Provider adapter interface and request/response representations for the Model Gateway.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass(frozen=True)
class ModelRequest:
    """
    Unified representation of a model generation request.
    """
    task_id: str
    request_type: str
    capability_required: str
    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    preferred_model: str | None = None
    streaming: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "request_type": self.request_type,
            "capability_required": self.capability_required,
            "prompt": self.prompt,
            "context": self.context,
            "constraints": self.constraints,
            "preferred_model": self.preferred_model,
            "streaming": self.streaming,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelRequest:
        return cls(
            task_id=data["task_id"],
            request_type=data["request_type"],
            capability_required=data["capability_required"],
            prompt=data["prompt"],
            context=data.get("context", {}),
            constraints=data.get("constraints", []),
            preferred_model=data.get("preferred_model"),
            streaming=bool(data.get("streaming", False)),
            parameters=data.get("parameters", {}),
        )


@dataclass(frozen=True)
class ModelResponse:
    """
    Unified representation of a model generation response.
    """
    output: str
    provider_used: str
    model_used: str
    token_usage: dict[str, int]  # e.g., {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    latency: float  # Latency in seconds
    finish_reason: str  # e.g., "stop", "length", "content_filter"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
            "token_usage": self.token_usage,
            "latency": self.latency,
            "finish_reason": self.finish_reason,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelResponse:
        return cls(
            output=data["output"],
            provider_used=data["provider_used"],
            model_used=data["model_used"],
            token_usage=data["token_usage"],
            latency=float(data["latency"]),
            finish_reason=data["finish_reason"],
            metadata=data.get("metadata", {}),
        )


class ProviderAdapter(ABC):
    """
    Abstract Base Class for all provider adapters (e.g. Groq, NVIDIA, OpenAI).
    Ensures a unified calling interface for all AI engines.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connections, load API keys, and configure client instances."""
        pass

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """
        List all models supported by this provider, returning a list of dicts.
        Each dict should contain fields matching ModelMetadata constructor keys.
        """
        pass

    @abstractmethod
    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        """
        Execute a standard generation request.

        Args:
            model: The target model name.
            request: The request payload.

        Returns:
            The populated ModelResponse.
        """
        pass

    @abstractmethod
    async def stream(self, model: str, request: ModelRequest) -> AsyncIterator[str]:
        """
        Execute a streaming generation request.

        Args:
            model: The target model name.
            request: The request payload.

        Yields:
            Text chunks as they are generated.
        """
        pass

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """
        Check the status of the provider.

        Returns:
            A dictionary containing status (e.g., {"status": "online", "latency": 0.12})
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully release resources, close connections, etc."""
        pass
