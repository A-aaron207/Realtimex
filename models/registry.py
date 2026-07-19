"""
Model and Provider registry for the Realtimex Model Gateway.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from models.exceptions import ModelSelectionError
from models.provider import ProviderAdapter


@dataclass
class ModelMetadata:
    """
    Metadata representation of a registered model.
    """
    provider_name: str
    model_name: str
    context_window: int
    max_tokens: int
    capabilities: list[str]
    latency: float = 0.0  # Average response latency in seconds
    health_status: str = "healthy"  # "healthy", "degraded", "unhealthy"
    cost_metadata: dict[str, float] = field(default_factory=lambda: {"input_cost_1k": 0.0, "output_cost_1k": 0.0})
    rate_limits: dict[str, int] = field(default_factory=lambda: {"rpm": 60, "tpm": 40000})
    is_open_source: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "context_window": self.context_window,
            "max_tokens": self.max_tokens,
            "capabilities": self.capabilities,
            "latency": self.latency,
            "health_status": self.health_status,
            "cost_metadata": self.cost_metadata,
            "rate_limits": self.rate_limits,
            "is_open_source": self.is_open_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetadata:
        return cls(
            provider_name=data["provider_name"],
            model_name=data["model_name"],
            context_window=data["context_window"],
            max_tokens=data["max_tokens"],
            capabilities=data["capabilities"],
            latency=float(data.get("latency", 0.0)),
            health_status=data.get("health_status", "healthy"),
            cost_metadata=data.get("cost_metadata", {}),
            rate_limits=data.get("rate_limits", {}),
            is_open_source=bool(data.get("is_open_source", True)),
        )


class ModelRegistry:
    """
    Thread-safe registry for model metadata and loaded provider adapters.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: dict[str, ProviderAdapter] = {}
        self._models: dict[tuple[str, str], ModelMetadata] = {}

    def register_provider(self, name: str, adapter: ProviderAdapter) -> None:
        """Register a provider adapter instance."""
        with self._lock:
            self._providers[name.lower()] = adapter

    def unregister_provider(self, name: str) -> None:
        """Unregister a provider adapter instance and all its models."""
        provider_key = name.lower()
        with self._lock:
            if provider_key in self._providers:
                del self._providers[provider_key]
            # Remove associated models
            associated = [k for k in self._models.keys() if k[0] == provider_key]
            for k in associated:
                del self._models[k]

    def register_model(self, metadata: ModelMetadata) -> None:
        """Register model metadata."""
        with self._lock:
            key = (metadata.provider_name.lower(), metadata.model_name)
            self._models[key] = metadata

    def update_model_latency(self, provider_name: str, model_name: str, latency: float) -> None:
        """Update average latency for a registered model."""
        key = (provider_name.lower(), model_name)
        with self._lock:
            if key in self._models:
                # Running average updates
                current = self._models[key].latency
                if current == 0.0:
                    self._models[key].latency = latency
                else:
                    self._models[key].latency = (current * 0.7) + (latency * 0.3)

    def update_model_health(self, provider_name: str, model_name: str, status: str) -> None:
        """Update health status for a registered model."""
        key = (provider_name.lower(), model_name)
        with self._lock:
            if key in self._models:
                self._models[key].health_status = status

    def get_adapter(self, provider_name: str) -> ProviderAdapter | None:
        """Fetch a registered provider adapter."""
        with self._lock:
            return self._providers.get(provider_name.lower())

    def get_model_metadata(self, provider_name: str, model_name: str) -> ModelMetadata | None:
        """Retrieve metadata for a specific model."""
        key = (provider_name.lower(), model_name)
        with self._lock:
            return self._models.get(key)

    def list_providers(self) -> list[str]:
        """List names of all registered providers."""
        with self._lock:
            return list(self._providers.keys())

    def list_models(
        self,
        capability: str | None = None,
        active_only: bool = False,
    ) -> list[ModelMetadata]:
        """
        List metadata of all registered models, with optional capability and health filters.
        """
        with self._lock:
            models_list = list(self._models.values())
        
        if capability:
            models_list = [m for m in models_list if capability in m.capabilities]
        
        if active_only:
            models_list = [m for m in models_list if m.health_status != "unhealthy"]

        return models_list
