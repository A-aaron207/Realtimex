"""
Metrics Exporters for Realtimex.

Defines log and file exporters for metrics.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any


class MetricExporter:
    """Base class for all metric exporters."""

    def export(self, metrics: dict[str, Any]) -> None:
        """Export a snapshot of all metrics."""
        raise NotImplementedError


class LogExporter(MetricExporter):
    """Exports metrics to the system logger."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("realtimex.observability.metrics.exporter")

    def export(self, metrics: dict[str, Any]) -> None:
        self.logger.info("Metrics Snapshot: %s", json.dumps(metrics, default=str))


class FileExporter(MetricExporter):
    """Exports metrics as a JSON file to disk."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def export(self, metrics: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=4, default=str)
