"""
Model selection engine for the Realtimex Model Gateway.
"""

from __future__ import annotations

from typing import Any

from models.exceptions import NoCompatibleProviderError, ModelSelectionError
from models.provider import ModelRequest
from models.registry import ModelMetadata, ModelRegistry


class ModelSelector:
    """
    Selects the optimal model and provider based on request criteria,
    capability requirements, context size, health, and latency.
    """

    def __init__(self, registry: ModelRegistry, health_monitor: Any = None) -> None:
        self.registry = registry
        self.health_monitor = health_monitor

    def select_model(self, request: ModelRequest, exclude: set[tuple[str, str]] | None = None) -> ModelMetadata:
        """
        Choose the best available model for a given request.

        Args:
            request: The ModelRequest.
            exclude: Optional set of (provider_name, model_name) tuples to exclude.

        Returns:
            ModelMetadata of the selected model.

        Raises:
            NoCompatibleProviderError: If no healthy models support the required capability.
            ModelSelectionError: If selection fails for other reasons.
        """
        exclude_set = exclude or set()
        
        # 1. Fetch models matching the capability
        matching_models = self.registry.list_models(capability=request.capability_required)
        matching_models = [m for m in matching_models if (m.provider_name.lower(), m.model_name) not in exclude_set]
        
        if not matching_models:
            raise NoCompatibleProviderError(
                f"No registered model supports the capability: '{request.capability_required}'"
            )

        # 2. Filter out unhealthy models
        healthy_models = []
        for model in matching_models:
            is_unhealthy = False
            
            # Check registry health status
            if model.health_status == "unhealthy":
                is_unhealthy = True
            
            # Check Health Monitor if present
            if self.health_monitor is not None:
                if not self.health_monitor.is_model_healthy(model.provider_name, model.model_name):
                    is_unhealthy = True

            if not is_unhealthy:
                healthy_models.append(model)

        if not healthy_models:
            raise NoCompatibleProviderError(
                f"All models matching capability '{request.capability_required}' are currently unhealthy."
            )

        # 3. Check Context Size Constraints
        # Quick token estimate: 1 token ~ 4 characters
        prompt_len = len(request.prompt)
        context_len = len(str(request.context))
        estimated_tokens = (prompt_len + context_len) // 4

        eligible_models = [m for m in healthy_models if m.context_window >= estimated_tokens]
        if not eligible_models:
            raise NoCompatibleProviderError(
                f"Request context size ({estimated_tokens} tokens) exceeds context windows of all healthy models."
            )

        # 4. Check User Preference
        if request.preferred_model:
            pref = request.preferred_model.lower()
            for model in eligible_models:
                if model.model_name.lower() == pref or f"{model.provider_name.lower()}/{model.model_name.lower()}" == pref:
                    return model

        # 5. Rank by Latency & Cost (Lower is better)
        # Sort key: average latency, cost per 1k tokens, then context window size
        def ranking_key(m: ModelMetadata) -> tuple[float, float, int]:
            latency = m.latency if m.latency > 0 else 0.5
            cost = m.cost_metadata.get("input_cost_1k", 0.0) + m.cost_metadata.get("output_cost_1k", 0.0)
            # Higher context window size is a tie-breaker (negative so larger is sorted first)
            return (latency, cost, -m.context_window)

        eligible_models.sort(key=ranking_key)
        return eligible_models[0]
