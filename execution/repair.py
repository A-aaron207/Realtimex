"""
Local Repair Engine component for Executor 2.0.

Executes fast, deterministic local repairs without LLM overhead when actions fail
due to structural issues (e.g. missing parent directories, path issues).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RepairResult:
    """Report returned after attempting a local repair."""
    success: bool
    strategy_used: str
    repaired_input: dict[str, Any] = field(default_factory=dict)
    message: str = "Repair succeeded"


class ExecutionRepairEngine:
    """
    Deterministic repair engine for Executor 2.0.
    Applies non-LLM fixes to input parameters to resolve common runtime failures.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("realtimex.execution.repair")

    def attempt_repair(
        self,
        strategy: str,
        capability: str,
        input_data: dict[str, Any],
        error_msg: str,
        fallback_dir: str | Path | None = None,
    ) -> RepairResult:
        """
        Attempt a deterministic local repair based on the identified strategy.
        """
        repaired = dict(input_data)
        fallback_path = Path(fallback_dir) if fallback_dir else Path.home() / "Documents" / "Realtimex" / "fallback"

        if strategy == "create_parent_directory":
            file_path = repaired.get("file_path") or repaired.get("destination") or repaired.get("path")
            if file_path and isinstance(file_path, str):
                p = Path(file_path)
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    self.logger.info("Created missing parent directory: %s", p.parent)
                    return RepairResult(
                        success=True,
                        strategy_used=strategy,
                        repaired_input=repaired,
                        message=f"Created missing parent directory '{p.parent}'",
                    )
                except Exception as e:
                    self.logger.warning("Failed to create parent directory %s: %s", p.parent, e)

        elif strategy == "use_fallback_directory":
            file_path = repaired.get("file_path") or repaired.get("destination") or repaired.get("path")
            if file_path and isinstance(file_path, str):
                filename = Path(file_path).name
                fallback_file = fallback_path / filename
                try:
                    fallback_file.parent.mkdir(parents=True, exist_ok=True)
                    repaired["file_path"] = str(fallback_file)
                    self.logger.info("Redirected path to fallback directory: %s", fallback_file)
                    return RepairResult(
                        success=True,
                        strategy_used=strategy,
                        repaired_input=repaired,
                        message=f"Redirected output to fallback path '{fallback_file}'",
                    )
                except Exception as e:
                    self.logger.warning("Failed to setup fallback directory %s: %s", fallback_file, e)

        elif strategy in ("retry_command", "retry_default", "retry_with_backoff", "retry_network"):
            # Pass through for retry
            return RepairResult(
                success=True,
                strategy_used=strategy,
                repaired_input=repaired,
                message="Prepared input for retry attempt",
            )

        return RepairResult(
            success=False,
            strategy_used=strategy,
            repaired_input=input_data,
            message=f"No deterministic local repair available for strategy '{strategy}'",
        )
