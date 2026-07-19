"""
Configuration loading for the Realtimex Kernel.

Reads Kernel configuration from a JSON file. If the file does not
exist, a sensible default configuration is generated and written to
disk so that subsequent boots have a stable, inspectable config file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KernelConfig:
    """
    Strongly-typed view over Kernel configuration values.

    Attributes:
        kernel_name: Human-readable name of this Kernel instance.
        version: Kernel version string.
        environment: Deployment environment (e.g. "development", "production").
        log_level: Logging level name applied to the Kernel logger.
        log_filename: Filename used for the Kernel's log file.
        raw: The full underlying configuration dictionary, including any
            keys not yet promoted to a typed field. Future milestones
            (Scheduler, Memory Manager, etc.) will read their own
            sections from here.
    """

    kernel_name: str
    version: str
    environment: str
    log_level: str
    log_filename: str
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "KernelConfig":
        """Build a KernelConfig from a raw configuration dictionary."""
        kernel_section = data.get("kernel", {})
        logging_section = data.get("logging", {})

        return KernelConfig(
            kernel_name=kernel_section.get("name", "realtimex-kernel"),
            version=kernel_section.get("version", "0.1.0"),
            environment=kernel_section.get("environment", "development"),
            log_level=logging_section.get("level", "INFO"),
            log_filename=logging_section.get("filename", "kernel.log"),
            raw=data,
        )


class ConfigLoader:
    """
    Loads Kernel configuration from disk, generating a default file
    when none exists.

    Responsibilities:
        - Locate and read config/config.json.
        - Generate and persist a default configuration if missing.
        - Parse raw JSON into a typed KernelConfig.
    """

    def __init__(self, config_path: Path) -> None:
        """
        Initialize the loader.

        Args:
            config_path: Full path to the configuration JSON file.
        """
        self._config_path = config_path

    @property
    def config_path(self) -> Path:
        """Path to the configuration file this loader reads from."""
        return self._config_path

    def load(self) -> KernelConfig:
        """
        Load Kernel configuration, creating a default file if needed.

        Returns:
            A populated KernelConfig instance.
        """
        if not self._config_path.exists():
            self._write_default_config()

        with self._config_path.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)

        return KernelConfig.from_dict(data)

    def _write_default_config(self) -> None:
        """Generate and persist a default configuration file."""
        default_config = self._default_config_dict()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        with self._config_path.open("w", encoding="utf-8") as config_file:
            json.dump(default_config, config_file, indent=2)
            config_file.write("\n")

    @staticmethod
    def _default_config_dict() -> dict[str, Any]:
        """Return the default configuration as a plain dictionary."""
        return {
            "kernel": {
                "name": "realtimex-kernel",
                "version": "0.1.0",
                "environment": "development",
            },
            "logging": {
                "level": "INFO",
                "filename": "kernel.log",
            },
            "event_bus": {
                "enabled": True,
            },
            "service_registry": {
                "enabled": True,
            },
            "capability_registry": {
                "enabled": True,
            },
            "recovery_manager": {
                "enabled": True,
            },
        }
