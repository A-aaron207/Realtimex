"""
Configuration Manager for Realtimex.

The central coordinator for the Configuration System.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable, Optional

from configuration.defaults import get_all_defaults
from configuration.environment import EnvironmentManager
from configuration.exceptions import (
    ConfigurationError,
    ConfigurationNotFoundError,
    ConfigurationValidationError,
)
from configuration.hot_reload import HotReloadEngine
from configuration.loader import ConfigurationLoader
from configuration.persistence import ConfigurationPersistence
from configuration.profiles import ProfileManager
from configuration.registry import ConfigurationRegistry
from configuration.validator import ConfigurationValidator
from events.bus import EventBus
from events.event import Event, EventPriority
from events.event_types import ConfigurationEventType


class ConfigurationManager:
    """
    Central coordinator for the Configuration System.
    
    Orchestrates Registry, Loader, Validator, ProfileManager, 
    EnvironmentManager, and HotReloadEngine.
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        config_dir: str = "config",
        environment: Optional[str] = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Configuration Manager.
        
        Args:
            event_bus: Optional Event Bus for emitting events
            config_dir: Root directory for configuration files
            environment: Optional environment override
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.manager")
        self.bus = event_bus
        self.config_dir = config_dir

        # Initialize components
        self.registry = ConfigurationRegistry(self.logger)
        self.loader = ConfigurationLoader(self.logger)
        self.validator = ConfigurationValidator(self.logger)
        self.profiles = ProfileManager(self.logger)
        self.environment_mgr = EnvironmentManager(environment, self.logger)
        self.hot_reload = HotReloadEngine(self.logger)
        self.persistence = ConfigurationPersistence(self.logger)

        self._lock = threading.RLock()
        self._initialized = False

    def initialize(self) -> None:
        """
        Initialize the configuration system.
        
        Loading precedence:
        1. Default values
        2. Files in config_dir
        3. Environment-specific overrides (directory or EnvironmentManager)
        4. Environment variables (REALTIMEX_*)
        """
        with self._lock:
            if self._initialized:
                return

            self.logger.info("Initializing Configuration System...")

            # 1. Load defaults
            defaults = get_all_defaults()
            for namespace, config in defaults.items():
                self.registry.set_namespace(namespace, config)

            # 2. Load from config directory
            dir_config = self.loader.load_directory(self.config_dir)
            for namespace, config in dir_config.items():
                self.registry.set_namespace(namespace, config, merge=True)

            # 3. Apply environment overrides
            env_name = self.environment_mgr.get_environment()
            env_config_dir = os.path.join(self.config_dir, env_name)
            if os.path.isdir(env_config_dir):
                env_dir_config = self.loader.load_directory(env_config_dir)
                for namespace, config in env_dir_config.items():
                    self.registry.set_namespace(namespace, config, merge=True)

            # Apply EnvironmentManager's built-in overrides
            all_config = self.registry.get_all()
            overridden_config = self.environment_mgr.apply_overrides(all_config)
            for namespace, config in overridden_config.items():
                self.registry.set_namespace(namespace, config, merge=True)

            # 4. Load from environment variables
            env_vars = self.loader.load_env()
            for namespace, config in env_vars.items():
                self.registry.set_namespace(namespace, config, merge=True)

            # 5. Validate initial configuration
            is_valid, errors = self.validator.validate_all(self.registry.get_all())
            if not is_valid:
                self._emit_event(
                    ConfigurationEventType.CONFIGURATION_VALIDATION_FAILED,
                    {"errors": errors}
                )
                self.logger.error(
                    "Initial configuration validation failed: %s", errors
                )
            
            # Start background monitoring of config directory for changes
            self.hot_reload.start_monitoring(self.config_dir, self.reload)
            
            self._initialized = True
            self._emit_event(
                ConfigurationEventType.CONFIGURATION_LOADED,
                self.registry.get_all()
            )
            self.logger.info("Configuration System initialized.")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (e.g., "kernel.debug" or "kernel")
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        parts = key.split(".", 1)
        if len(parts) == 1:
            return self.registry.get_namespace(parts[0])
        
        return self.registry.get(parts[0], parts[1], default)

    def set(self, key: str, value: Any, persist: bool = False) -> None:
        """
        Set configuration value.
        
        Args:
            key: Configuration key (e.g., "kernel.debug")
            value: Configuration value
            persist: If True, save to disk
            
        Raises:
            ConfigurationError: If key is invalid
            ConfigurationValidationError: If validation fails
        """
        parts = key.split(".", 1)
        if len(parts) != 2:
            raise ConfigurationError(
                f"Invalid configuration key: {key}. Use 'namespace.key'"
            )
        
        namespace, config_key = parts
        
        # Validate
        is_valid, error = self.validator.validate_value(namespace, config_key, value)
        if not is_valid:
            self._emit_event(
                ConfigurationEventType.CONFIGURATION_VALIDATION_FAILED,
                {"namespace": namespace, "key": config_key, "error": error}
            )
            raise ConfigurationValidationError(error)

        # Set in registry
        self.registry.set(namespace, config_key, value)
        
        # Notify hot reload subscribers
        self.hot_reload.notify_reload(
            namespace, self.registry.get_namespace(namespace)
        )
        
        # Emit event
        self._emit_event(ConfigurationEventType.CONFIGURATION_UPDATED, {
            "namespace": namespace,
            "key": config_key,
            "value": value
        })

        if persist:
            self.save(namespace)

    def reload(self, namespace: Optional[str] = None) -> None:
        """
        Reload configuration from sources.
        
        Args:
            namespace: Optional namespace to reload (if None, reloads all)
        """
        with self._lock:
            if namespace is None:
                self._initialized = False
                self.initialize()
                self._emit_event(
                    ConfigurationEventType.CONFIGURATION_RELOADED,
                    self.registry.get_all()
                )
            else:
                # Reload specific namespace from directory
                dir_config = self.loader.load_directory(self.config_dir)
                if namespace in dir_config:
                    # Validate before reload
                    is_valid, errors = self.validator.validate_namespace(namespace, dir_config[namespace])
                    if not is_valid:
                        self.logger.error("Hot reload validation failed for namespace %s: %s", namespace, errors)
                        self._emit_event(
                            ConfigurationEventType.CONFIGURATION_VALIDATION_FAILED,
                            {"namespace": namespace, "errors": errors}
                        )
                        raise ConfigurationValidationError(f"Validation failed during reload: {errors}")
                        
                    self.registry.set_namespace(
                        namespace, dir_config[namespace], merge=True
                    )
                    self.hot_reload.notify_reload(
                        namespace, self.registry.get_namespace(namespace)
                    )
                    self._emit_event(
                        ConfigurationEventType.CONFIGURATION_RELOADED,
                        {namespace: self.registry.get_namespace(namespace)}
                    )

    def shutdown(self) -> None:
        """Shutdown configuration manager and stop monitoring thread."""
        with self._lock:
            self.hot_reload.stop_monitoring()
            self.logger.info("Configuration Manager shutdown complete.")

    def save(self, namespace: str, format: str = "json") -> None:
        """
        Save namespace configuration to disk.
        
        Args:
            namespace: Configuration namespace
            format: Output format ('json', 'yaml', 'toml')
        """
        config = self.registry.get_namespace(namespace)
        path = os.path.join(self.config_dir, f"{namespace}.{format}")
        
        if format == "json":
            self.persistence.save_json(path, {namespace: config})
        elif format == "yaml":
            self.persistence.save_yaml(path, {namespace: config})
        elif format == "toml":
            self.persistence.save_toml(path, {namespace: config})
        else:
            raise ConfigurationError(f"Unsupported persistence format: {format}")

    def profile(self, name: Optional[str] = None) -> str | None:
        """
        Get or set active profile.
        
        Args:
            name: Optional profile name to activate
            
        Returns:
            Current or newly activated profile name
        """
        if name is None:
            return self.profiles.get_profile()
        
        self.profiles.set_profile(name)
        
        # Re-apply effective config from profile to registry
        # (This is a simplified implementation of profile switching)
        for namespace in self.registry.list_namespaces():
            defaults = get_all_defaults().get(namespace, {})
            effective = self.profiles.get_effective_config(namespace, defaults)
            if effective:
                self.registry.set_namespace(namespace, effective, merge=True)
                self.hot_reload.notify_reload(namespace, effective)
        
        self._emit_event(
            ConfigurationEventType.PROFILE_CHANGED,
            {"profile": name}
        )
        return name

    def environment(self) -> str:
        """
        Get current environment.
        
        Returns:
            Environment name
        """
        return self.environment_mgr.get_environment()

    def validate(self) -> tuple[bool, dict[str, list[str]]]:
        """
        Validate all configuration.
        
        Returns:
            Tuple of (is_valid, errors_dict)
        """
        return self.validator.validate_all(self.registry.get_all())

    def subscribe(
        self,
        namespace: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Subscribe to configuration changes for namespace.
        
        Args:
            namespace: Configuration namespace
            callback: Callback function
        """
        self.hot_reload.subscribe(namespace, callback)

    def unsubscribe(self, namespace: str, callback: Callable) -> bool:
        """
        Unsubscribe from configuration changes.
        
        Args:
            namespace: Configuration namespace
            callback: Callback function
            
        Returns:
            True if unsubscribed
        """
        return self.hot_reload.unsubscribe(namespace, callback)

    def _emit_event(self, event_type: str, data: Any) -> None:
        """
        Emit event to Event Bus.
        
        Args:
            event_type: Type of event
            data: Event payload
        """
        if self.bus:
            event = Event(
                name=event_type,
                source="configuration_manager",
                payload=data,
                priority=EventPriority.NORMAL
            )
            self.bus.publish(event)
