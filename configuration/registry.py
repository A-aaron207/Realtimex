"""
Configuration Registry for Realtimex.

Manages namespace-based configuration storage with thread-safe access.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from configuration.exceptions import ConfigurationNotFoundError


class ConfigurationRegistry:
    """
    Namespace-based configuration storage.
    
    Organizes configuration into namespaces:
    - kernel.*
    - scheduler.*
    - workers.*
    - memory.*
    - etc.
    
    Thread-safe operations with RLock.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize Configuration Registry.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.registry")
        self._config: dict[str, dict[str, Any]] = {}  # namespace -> {key: value}
        self._lock = threading.RLock()

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        merge: bool = False,
    ) -> None:
        """
        Set configuration value.
        
        Args:
            namespace: Configuration namespace
            key: Configuration key
            value: Configuration value
            merge: If True and value is dict, merge instead of replace
        """
        with self._lock:
            if namespace not in self._config:
                self._config[namespace] = {}
            
            if merge and isinstance(value, dict) and isinstance(self._config[namespace].get(key), dict):
                self._config[namespace][key].update(value)
            else:
                self._config[namespace][key] = value
            
            self.logger.debug(
                "Configuration set: %s.%s = %s",
                namespace, key, type(value).__name__
            )

    def set_namespace(
        self,
        namespace: str,
        config: dict[str, Any],
        merge: bool = False,
    ) -> None:
        """
        Set entire namespace configuration.
        
        Args:
            namespace: Configuration namespace
            config: Namespace configuration dictionary
            merge: If True, merge with existing config
        """
        with self._lock:
            if merge and namespace in self._config:
                self._config[namespace].update(config)
            else:
                self._config[namespace] = config.copy()
            
            self.logger.debug(
                "Configuration namespace set: %s with %d keys",
                namespace, len(config)
            )

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            namespace: Configuration namespace
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        with self._lock:
            if namespace not in self._config:
                return default
            return self._config[namespace].get(key, default)

    def get_namespace(self, namespace: str) -> dict[str, Any]:
        """
        Get entire namespace configuration.
        
        Args:
            namespace: Configuration namespace
            
        Returns:
            Namespace configuration dictionary
        """
        with self._lock:
            if namespace not in self._config:
                return {}
            return self._config[namespace].copy()

    def get_all(self) -> dict[str, dict[str, Any]]:
        """
        Get all configuration.
        
        Returns:
            Complete configuration dictionary
        """
        with self._lock:
            return {k: v.copy() for k, v in self._config.items()}

    def has(self, namespace: str, key: str | None = None) -> bool:
        """
        Check if configuration exists.
        
        Args:
            namespace: Configuration namespace
            key: Optional key (if None, checks namespace existence)
            
        Returns:
            True if configuration exists
        """
        with self._lock:
            if namespace not in self._config:
                return False
            if key is None:
                return True
            return key in self._config[namespace]

    def delete(self, namespace: str, key: str | None = None) -> bool:
        """
        Delete configuration value.
        
        Args:
            namespace: Configuration namespace
            key: Optional key (if None, deletes entire namespace)
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if namespace not in self._config:
                return False
            
            if key is None:
                del self._config[namespace]
                self.logger.debug("Configuration namespace deleted: %s", namespace)
                return True
            
            if key in self._config[namespace]:
                del self._config[namespace][key]
                self.logger.debug(
                    "Configuration deleted: %s.%s", namespace, key
                )
                return True
            
            return False

    def clear(self, namespace: str | None = None) -> None:
        """
        Clear configuration.
        
        Args:
            namespace: Optional namespace (if None, clears all)
        """
        with self._lock:
            if namespace is None:
                self._config.clear()
                self.logger.debug("All configuration cleared")
            else:
                if namespace in self._config:
                    del self._config[namespace]
                    self.logger.debug("Configuration namespace cleared: %s", namespace)

    def list_namespaces(self) -> list[str]:
        """
        List all registered namespaces.
        
        Returns:
            List of namespace names
        """
        with self._lock:
            return list(self._config.keys())

    def count(self, namespace: str | None = None) -> int:
        """
        Count configuration entries.
        
        Args:
            namespace: Optional namespace (if None, counts all)
            
        Returns:
            Number of configuration entries
        """
        with self._lock:
            if namespace is None:
                return sum(len(v) for v in self._config.values())
            return len(self._config.get(namespace, {}))

    def merge(self, other: dict[str, dict[str, Any]]) -> None:
        """
        Merge configuration from another source.
        
        Args:
            other: Configuration dictionary to merge
        """
        with self._lock:
            for namespace, config in other.items():
                if namespace in self._config:
                    self._config[namespace].update(config)
                else:
                    self._config[namespace] = config.copy()
            
            self.logger.debug(
                "Configuration merged from %d namespaces",
                len(other)
            )
