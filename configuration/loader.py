"""
Configuration Loader for Realtimex.

Loads configuration from multiple sources with defined precedence.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from configuration.exceptions import ConfigurationLoadError


class ConfigurationLoader:
    """
    Loads configuration from multiple sources.
    
    Supports:
    - JSON files
    - YAML files
    - TOML files
    - Environment variables
    - Default values
    
    Precedence: Env vars > TOML > YAML > JSON > Defaults
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize Configuration Loader.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.loader")

    def load_json(self, path: str) -> dict[str, Any]:
        """
        Load configuration from JSON file.
        
        Args:
            path: Path to JSON file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationLoadError: If loading fails
        """
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            
            with open(path, 'r') as f:
                config = json.load(f)
            
            self.logger.info("Configuration loaded from JSON: %s", path)
            return config
        except Exception as e:
            raise ConfigurationLoadError(f"Failed to load JSON: {e}") from e

    def load_yaml(self, path: str) -> dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Args:
            path: Path to YAML file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationLoadError: If loading fails
        """
        try:
            import yaml
        except ImportError:
            raise ConfigurationLoadError("PyYAML not installed")
        
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.logger.info("Configuration loaded from YAML: %s", path)
            return config or {}
        except Exception as e:
            raise ConfigurationLoadError(f"Failed to load YAML: {e}") from e

    def load_toml(self, path: str) -> dict[str, Any]:
        """
        Load configuration from TOML file.
        
        Args:
            path: Path to TOML file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationLoadError: If loading fails
        """
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                raise ConfigurationLoadError("tomllib/tomli not installed")
        
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            
            with open(path, 'rb') as f:
                config = tomllib.load(f)
            
            self.logger.info("Configuration loaded from TOML: %s", path)
            return config
        except Exception as e:
            raise ConfigurationLoadError(f"Failed to load TOML: {e}") from e

    def load_env(self, prefix: str = "REALTIMEX_") -> dict[str, dict[str, str]]:
        """
        Load configuration from environment variables.
        
        Format: {PREFIX}{NAMESPACE}_{KEY}=value
        Example: REALTIMEX_KERNEL_DEBUG=true
        
        Args:
            prefix: Environment variable prefix
            
        Returns:
            Configuration dictionary
        """
        config: dict[str, dict[str, str]] = {}
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Remove prefix
            key_without_prefix = key[len(prefix):]
            
            # Split namespace and key
            parts = key_without_prefix.split('_', 1)
            if len(parts) != 2:
                continue
            
            namespace = parts[0].lower()
            config_key = parts[1].lower()
            
            if namespace not in config:
                config[namespace] = {}
            
            # Try to convert value to appropriate type
            config[namespace][config_key] = self._convert_value(value)
        
        if config:
            self.logger.info(
                "Configuration loaded from environment variables: %d values",
                sum(len(v) for v in config.values())
            )
        
        return config

    def _convert_value(self, value: str) -> Any:
        """
        Convert string value to appropriate type.
        
        Args:
            value: String value
            
        Returns:
            Converted value
        """
        # Boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float
        try:
            return float(value)
        except ValueError:
            pass
        
        # String
        return value

    def load_directory(
        self,
        directory: str,
        pattern: Optional[str] = None,
    ) -> dict[str, dict]:
        """
        Load configuration from directory of files.
        
        Args:
            directory: Directory path
            pattern: Optional file pattern (*.json, *.yaml, etc.). If None, loads all supported files.
            
        Returns:
            Merged configuration dictionary
        """
        config: dict[str, dict] = {}
        
        if not os.path.isdir(directory):
            self.logger.warning("Configuration directory not found: %s", directory)
            return config
        
        import glob
        
        patterns = [pattern] if pattern else ["*.json", "*.yaml", "*.yml", "*.toml"]
        
        for pat in patterns:
            for filepath in glob.glob(os.path.join(directory, pat)):
                try:
                    if filepath.endswith('.json'):
                        file_config = self.load_json(filepath)
                    elif filepath.endswith('.yaml') or filepath.endswith('.yml'):
                        file_config = self.load_yaml(filepath)
                    elif filepath.endswith('.toml'):
                        file_config = self.load_toml(filepath)
                    else:
                        continue
                    
                    # Merge configuration
                    for namespace, ns_config in file_config.items():
                        if namespace not in config:
                            config[namespace] = {}
                        if isinstance(ns_config, dict):
                            config[namespace].update(ns_config)
                
                except Exception as e:
                    self.logger.error("Failed to load configuration file %s: %s", filepath, e)
        
        if config:
            self.logger.info(
                "Configuration loaded from directory: %s",
                directory
            )
        
        return config

