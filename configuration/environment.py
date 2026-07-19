"""
Environment Manager for Realtimex Configuration System.

Manages environment-specific configuration overrides.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

from configuration.exceptions import EnvironmentNotSupportedError


class EnvironmentManager:
    """
    Manages environment-specific configuration.
    
    Supports environments:
    - development: Verbose logging, debugging enabled
    - staging: Pre-production testing
    - production: Optimized, security hardened
    - testing: Mock services, minimal output
    
    Environment can be set via:
    - Constructor parameter
    - Environment variable (REALTIMEX_ENV)
    - Default (development)
    """

    # Supported environments
    ENVIRONMENT_DEVELOPMENT = "development"
    ENVIRONMENT_STAGING = "staging"
    ENVIRONMENT_PRODUCTION = "production"
    ENVIRONMENT_TESTING = "testing"

    SUPPORTED_ENVIRONMENTS = {
        ENVIRONMENT_DEVELOPMENT,
        ENVIRONMENT_STAGING,
        ENVIRONMENT_PRODUCTION,
        ENVIRONMENT_TESTING,
    }

    # Environment variables
    ENV_VAR_NAME = "REALTIMEX_ENV"
    ENV_VAR_CONFIG_DIR = "REALTIMEX_CONFIG_DIR"
    ENV_VAR_LOG_LEVEL = "REALTIMEX_LOG_LEVEL"

    def __init__(
        self,
        environment: Optional[str] = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Environment Manager.
        
        Args:
            environment: Optional environment name
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.environment")
        
        # Determine environment
        if environment:
            self._environment = environment
        else:
            self._environment = os.getenv(
                self.ENV_VAR_NAME,
                self.ENVIRONMENT_DEVELOPMENT
            )
        
        if self._environment not in self.SUPPORTED_ENVIRONMENTS:
            raise EnvironmentNotSupportedError(
                f"Environment '{self._environment}' not supported. "
                f"Supported: {self.SUPPORTED_ENVIRONMENTS}"
            )
        
        # Environment-specific overrides
        self._overrides: dict[str, dict[str, Any]] = {}
        self._setup_default_overrides()
        
        self._lock = threading.RLock()
        
        self.logger.info("Environment initialized: %s", self._environment)

    def _setup_default_overrides(self) -> None:
        """Setup default configuration overrides for current environment."""
        if self._environment == self.ENVIRONMENT_DEVELOPMENT:
            self._overrides = {
                "kernel": {"debug": True},
                "logging": {"level": "DEBUG"},
                "interfaces": {"rest_enabled": True, "websocket_enabled": True},
            }
        
        elif self._environment == self.ENVIRONMENT_STAGING:
            self._overrides = {
                "kernel": {"debug": False},
                "logging": {"level": "INFO"},
                "interfaces": {"rest_enabled": True, "websocket_enabled": True},
            }
        
        elif self._environment == self.ENVIRONMENT_PRODUCTION:
            self._overrides = {
                "kernel": {"debug": False},
                "logging": {"level": "WARNING"},
                "scheduler": {"max_workers": 16},
                "memory": {"capacity": 5000000},
                "interfaces": {"rest_enabled": True, "websocket_enabled": False},
            }
        
        elif self._environment == self.ENVIRONMENT_TESTING:
            self._overrides = {
                "kernel": {"debug": True},
                "logging": {"level": "ERROR"},
                "scheduler": {"max_workers": 2},
                "models": {"default_model": "mock"},
            }

    def get_environment(self) -> str:
        """
        Get current environment.
        
        Returns:
            Environment name
        """
        with self._lock:
            return self._environment

    def is_development(self) -> bool:
        """Check if environment is development."""
        return self._environment == self.ENVIRONMENT_DEVELOPMENT

    def is_staging(self) -> bool:
        """Check if environment is staging."""
        return self._environment == self.ENVIRONMENT_STAGING

    def is_production(self) -> bool:
        """Check if environment is production."""
        return self._environment == self.ENVIRONMENT_PRODUCTION

    def is_testing(self) -> bool:
        """Check if environment is testing."""
        return self._environment == self.ENVIRONMENT_TESTING

    def set_override(
        self,
        namespace: str,
        key: str,
        value: Any,
    ) -> None:
        """
        Set environment-specific override.
        
        Args:
            namespace: Configuration namespace
            key: Configuration key
            value: Override value
        """
        with self._lock:
            if namespace not in self._overrides:
                self._overrides[namespace] = {}
            
            self._overrides[namespace][key] = value
            self.logger.debug(
                "Environment override set: %s.%s = %s",
                namespace, key, type(value).__name__
            )

    def get_override(
        self,
        namespace: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get environment-specific override.
        
        Args:
            namespace: Configuration namespace
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Override value or default
        """
        with self._lock:
            if namespace not in self._overrides:
                return default
            return self._overrides[namespace].get(key, default)

    def get_all_overrides(self) -> dict[str, dict[str, Any]]:
        """
        Get all environment overrides.
        
        Returns:
            Complete overrides dictionary
        """
        with self._lock:
            return {k: v.copy() for k, v in self._overrides.items()}

    def has_override(self, namespace: str, key: Optional[str] = None) -> bool:
        """
        Check if override exists.
        
        Args:
            namespace: Configuration namespace
            key: Optional key (if None, checks namespace existence)
            
        Returns:
            True if override exists
        """
        with self._lock:
            if namespace not in self._overrides:
                return False
            if key is None:
                return True
            return key in self._overrides[namespace]

    def clear_override(self, namespace: str, key: Optional[str] = None) -> bool:
        """
        Clear environment override.
        
        Args:
            namespace: Configuration namespace
            key: Optional key (if None, clears entire namespace)
            
        Returns:
            True if cleared, False if not found
        """
        with self._lock:
            if namespace not in self._overrides:
                return False
            
            if key is None:
                del self._overrides[namespace]
                self.logger.debug("Environment overrides cleared: %s", namespace)
                return True
            
            if key in self._overrides[namespace]:
                del self._overrides[namespace][key]
                self.logger.debug(
                    "Environment override cleared: %s.%s",
                    namespace, key
                )
                return True
            
            return False

    def get_config_dir(self) -> str:
        """
        Get configuration directory for environment.
        
        Returns:
            Configuration directory path
        """
        return os.getenv(
            self.ENV_VAR_CONFIG_DIR,
            f"config/{self._environment}"
        )

    def get_log_level(self) -> str:
        """
        Get log level for environment.
        
        Returns:
            Log level name
        """
        return os.getenv(self.ENV_VAR_LOG_LEVEL, "INFO")

    def apply_overrides(
        self,
        config: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """
        Apply environment overrides to configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration with overrides applied
        """
        with self._lock:
            result = {k: v.copy() for k, v in config.items()}
            
            for namespace, overrides in self._overrides.items():
                if namespace not in result:
                    result[namespace] = {}
                
                result[namespace].update(overrides)
            
            return result

    def list_supported_environments(self) -> list[str]:
        """
        List all supported environments.
        
        Returns:
            List of environment names
        """
        return sorted(list(self.SUPPORTED_ENVIRONMENTS))
