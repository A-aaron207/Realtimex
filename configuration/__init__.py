"""
Configuration System for Realtimex.

The Configuration System is the single source of truth for all runtime configuration.
"""

from __future__ import annotations

from configuration.exceptions import (
    ConfigurationError,
    ConfigurationLoadError,
    ConfigurationNotFoundError,
    ConfigurationPersistenceError,
    ConfigurationValidationError,
    EnvironmentNotSupportedError,
    ProfileNotFoundError,
)
from configuration.manager import ConfigurationManager
from configuration.registry import ConfigurationRegistry
from configuration.loader import ConfigurationLoader
from configuration.validator import ConfigurationValidator
from configuration.profiles import ProfileManager
from configuration.environment import EnvironmentManager
from configuration.hot_reload import HotReloadEngine
from configuration.persistence import ConfigurationPersistence
from configuration.defaults import get_default, get_all_defaults

__all__ = [
    "ConfigurationManager",
    "ConfigurationRegistry",
    "ConfigurationLoader",
    "ConfigurationValidator",
    "ProfileManager",
    "EnvironmentManager",
    "HotReloadEngine",
    "ConfigurationPersistence",
    "ConfigurationError",
    "ConfigurationLoadError",
    "ConfigurationNotFoundError",
    "ConfigurationPersistenceError",
    "ConfigurationValidationError",
    "EnvironmentNotSupportedError",
    "ProfileNotFoundError",
    "get_default",
    "get_all_defaults",
]
