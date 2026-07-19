"""
Logging Sinks for Realtimex.

Defines console, file, and rotating file sinks.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def create_console_sink() -> logging.Handler:
    """Create stream handler for logging to stdout/stderr."""
    return logging.StreamHandler()


def create_file_sink(filepath: str) -> logging.Handler:
    """Create file handler for logging to a file."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    return logging.FileHandler(filepath, encoding="utf-8")


def create_rotating_file_sink(
    filepath: str,
    max_bytes: int = 104857600,  # 100MB
    backup_count: int = 5,
) -> logging.Handler:
    """Create rotating file handler for automated log rotation."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    return RotatingFileHandler(
        filepath,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
