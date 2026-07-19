"""
Realtimex Model Gateway Package.
"""

from __future__ import annotations

from models.exceptions import (
    ModelGatewayError,
    ProviderError,
    ProviderInitializationError,
    ProviderUnavailableError,
    NoCompatibleProviderError,
    QuotaExceededError,
    ModelSelectionError,
    FailoverError,
)
from models.gateway import ModelGateway
from models.provider import ModelRequest, ModelResponse, ProviderAdapter
from models.registry import ModelMetadata, ModelRegistry
from models.selector import ModelSelector
from models.quota import QuotaManager
from models.health import HealthMonitor, HealthMetrics
from models.cache import ResponseCache
from models.routing import RequestRouter
from models.metrics import GatewayMetrics
from models.failover import FailoverEngine

__all__ = [
    "ModelGateway",
    "ModelRequest",
    "ModelResponse",
    "ProviderAdapter",
    "ModelMetadata",
    "ModelRegistry",
    "ModelSelector",
    "QuotaManager",
    "HealthMonitor",
    "HealthMetrics",
    "ResponseCache",
    "RequestRouter",
    "GatewayMetrics",
    "FailoverEngine",
    "ModelGatewayError",
    "ProviderError",
    "ProviderInitializationError",
    "ProviderUnavailableError",
    "NoCompatibleProviderError",
    "QuotaExceededError",
    "ModelSelectionError",
    "FailoverError",
]
