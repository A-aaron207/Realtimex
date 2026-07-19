"""
Centralized logging for the Realtimex Kernel.

All Kernel components and future modules should obtain their logger
through `KernelLogger.get_logger()` rather than instantiating their
own, so that log formatting, levels, and output destinations remain
consistent across the entire runtime.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


class KernelLogger:
    """
    Factory and configurator for Kernel-wide logging.

    Responsibilities:
        - Configure a root "realtimex" logger with console and file handlers.
        - Provide timestamped, leveled log output.
        - Expose named child loggers for reuse by any module or service.
    """

    _ROOT_LOGGER_NAME = "realtimex"
    _LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    _DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    _configured = False

    @classmethod
    def configure(
        cls,
        log_directory: Path,
        log_filename: str = "kernel.log",
        level: str = "INFO",
    ) -> logging.Logger:
        """
        Configure the root Kernel logger with console and file handlers.

        Safe to call multiple times; configuration is only applied once
        per process to avoid duplicate log handlers.

        Args:
            log_directory: Directory in which the log file should be written.
                Created automatically if it does not exist.
            log_filename: Name of the log file within `log_directory`.
            level: Logging level name (e.g. "DEBUG", "INFO", "WARNING").

        Returns:
            The configured root Kernel logger.
        """
        root_logger = logging.getLogger(cls._ROOT_LOGGER_NAME)

        if cls._configured:
            return root_logger

        log_directory.mkdir(parents=True, exist_ok=True)
        log_path = log_directory / log_filename

        resolved_level = getattr(logging, level.upper(), logging.INFO)
        root_logger.setLevel(resolved_level)
        root_logger.propagate = False

        formatter = logging.Formatter(fmt=cls._LOG_FORMAT, datefmt=cls._DATE_FORMAT)

        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(resolved_level)

        file_handler = logging.FileHandler(filename=str(log_path), encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(resolved_level)

        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        cls._configured = True
        return root_logger

    @classmethod
    def get_logger(cls, name: str | None = None) -> logging.Logger:
        """
        Retrieve a logger for use by any Kernel component or module.

        Args:
            name: Optional child logger name (e.g. "kernel.boot"). If
                omitted, the root Kernel logger is returned.

        Returns:
            A logger namespaced under the Kernel's root logger.
        """
        if name is None:
            return logging.getLogger(cls._ROOT_LOGGER_NAME)
        return logging.getLogger(f"{cls._ROOT_LOGGER_NAME}.{name}")
