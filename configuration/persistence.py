"""
Configuration Persistence for Realtimex.

Handles saving configuration to disk in various formats.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from configuration.exceptions import ConfigurationPersistenceError


def _serialize_yaml(config: dict[str, Any], indent_level: int = 0) -> str:
    """Helper to serialize a config dict to YAML string without dependencies."""
    lines = []
    indent = "  " * indent_level
    for k, v in config.items():
        if isinstance(v, dict):
            lines.append(f"{indent}{k}:")
            lines.append(_serialize_yaml(v, indent_level + 1))
        elif isinstance(v, bool):
            val_str = "true" if v else "false"
            lines.append(f"{indent}{k}: {val_str}")
        elif isinstance(v, (int, float)):
            lines.append(f"{indent}{k}: {v}")
        elif isinstance(v, str):
            lines.append(f"{indent}{k}: \"{v}\"")
        elif isinstance(v, list):
            # Encode simple lists
            list_str = "[" + ", ".join(f'"{x}"' if isinstance(x, str) else str(x) for x in v) + "]"
            lines.append(f"{indent}{k}: {list_str}")
        else:
            lines.append(f"{indent}{k}: \"{v}\"")
    return "\n".join(lines)


def _serialize_toml(config: dict[str, Any]) -> str:
    """Helper to serialize a config dict to TOML string without dependencies."""
    lines = []
    for namespace, ns_config in config.items():
        lines.append(f"[{namespace}]")
        for k, v in ns_config.items():
            if isinstance(v, dict):
                # Nested tables
                lines.append(f"\n[{namespace}.{k}]")
                for sub_k, sub_v in v.items():
                    val_str = _toml_value_format(sub_v)
                    lines.append(f"{sub_k} = {val_str}")
            else:
                val_str = _toml_value_format(v)
                lines.append(f"{k} = {val_str}")
        lines.append("")
    return "\n".join(lines)


def _toml_value_format(v: Any) -> str:
    """Format single value for TOML."""
    if isinstance(v, bool):
        return "true" if v else "false"
    elif isinstance(v, (int, float)):
        return str(v)
    elif isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    elif isinstance(v, list):
        items = [f'"{x}"' if isinstance(x, str) else str(x) for x in v]
        return "[" + ", ".join(items) + "]"
    else:
        return f'"{v}"'


class ConfigurationPersistence:
    """
    Saves configuration to disk.
    
    Supports:
    - JSON files
    - YAML files
    - TOML files
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize Configuration Persistence.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.persistence")

    def save_json(self, path: str, config: dict[str, Any]) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            path: Path to JSON file
            config: Configuration dictionary
            
        Raises:
            ConfigurationPersistenceError: If saving fails
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(config, f, indent=4)
            self.logger.info("Configuration saved to JSON: %s", path)
        except Exception as e:
            raise ConfigurationPersistenceError(f"Failed to save JSON: {e}") from e

    def save_yaml(self, path: str, config: dict[str, Any]) -> None:
        """
        Save configuration to YAML file with fallback to custom serializer.
        
        Args:
            path: Path to YAML file
            config: Configuration dictionary
            
        Raises:
            ConfigurationPersistenceError: If saving fails
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            try:
                import yaml
                with open(path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
            except ImportError:
                # Fallback to pure-python serializer
                self.logger.debug("PyYAML not installed, using fallback YAML serializer.")
                yaml_content = _serialize_yaml(config)
                with open(path, 'w') as f:
                    f.write(yaml_content)
                    
            self.logger.info("Configuration saved to YAML: %s", path)
        except Exception as e:
            raise ConfigurationPersistenceError(f"Failed to save YAML: {e}") from e

    def save_toml(self, path: str, config: dict[str, Any]) -> None:
        """
        Save configuration to TOML file with fallback to custom serializer.
        
        Args:
            path: Path to TOML file
            config: Configuration dictionary
            
        Raises:
            ConfigurationPersistenceError: If saving fails
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            try:
                import tomli_w
                with open(path, 'wb') as f:
                    tomli_w.dump(config, f)
            except ImportError:
                # Fallback to pure-python serializer
                self.logger.debug("tomli_w not installed, using fallback TOML serializer.")
                toml_content = _serialize_toml(config)
                with open(path, 'w') as f:
                    f.write(toml_content)
                    
            self.logger.info("Configuration saved to TOML: %s", path)
        except Exception as e:
            raise ConfigurationPersistenceError(f"Failed to save TOML: {e}") from e
