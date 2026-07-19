"""
Custom exceptions for the Realtimex Model Gateway.
"""

from __future__ import annotations


class ModelGatewayError(Exception):
    """Base exception for all Model Gateway errors."""


class ProviderError(ModelGatewayError):
    """Base exception for errors originating from a provider or adapter."""


class ProviderInitializationError(ProviderError):
    """Raised when a provider adapter fails to initialize."""


class ProviderUnavailableError(ProviderError):
    """Raised when a requested provider is offline or unreachable."""


class NoCompatibleProviderError(ModelGatewayError):
    """Raised when no compatible provider matches the request requirements."""


class QuotaExceededError(ModelGatewayError):
    """Raised when request quota has been exceeded for all available models."""


class ModelSelectionError(ModelGatewayError):
    """Raised when selecting a suitable model fails."""


class FailoverError(ModelGatewayError):
    """Raised when failover routing cannot find any working alternate model."""
