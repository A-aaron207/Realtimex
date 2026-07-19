"""
Custom exceptions for the Realtimex Configuration System.
"""

from __future__ import annotations


class ConfigurationError(Exception):
    """Base exception for all Configuration System errors."""


class ConfigurationNotFoundError(ConfigurationError):
    """Raised when configuration key is not found."""


class ConfigurationValidationError(ConfigurationError):
    """Raised when configuration validation fails."""


class ConfigurationTypeError(ConfigurationError):
    """Raised when configuration value has wrong type."""


class ConfigurationRangeError(ConfigurationError):
    """Raised when configuration value is out of range."""


class ProfileNotFoundError(ConfigurationError):
    """Raised when profile is not found."""


class EnvironmentNotSupportedError(ConfigurationError):
    """Raised when environment is not supported."""


class ConfigurationLoadError(ConfigurationError):
    """Raised when configuration fails to load."""


class ConfigurationHotReloadError(ConfigurationError):
    """Raised when hot reload fails."""


class ConfigurationPersistenceError(ConfigurationError):
    """Raised when configuration persistence fails."""
