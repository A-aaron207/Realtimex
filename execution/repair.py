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

        elif strategy == "resolve_missing_file_path":
            desktop_dir = Path.home() / "Desktop"
            target_dir = desktop_dir if desktop_dir.exists() else fallback_path
            content = str(repaired.get("content") or repaired.get("data") or "")
            ext = ".html" if ("<html" in content.lower() or "<!doctype" in content.lower()) else ".txt"
            target_path = target_dir / f"saved_output{ext}"
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                repaired["file_path"] = str(target_path)
                repaired["path"] = str(target_path)
                self.logger.info("Resolved missing file path to: %s", target_path)
                return RepairResult(
                    success=True,
                    strategy_used=strategy,
                    repaired_input=repaired,
                    message=f"Resolved missing file path to '{target_path}'",
                )
            except Exception as e:
                self.logger.warning("Failed to resolve missing file path: %s", e)

        elif strategy == "llm_code_repair":
            file_path = repaired.get("file_path") or repaired.get("path")
            command = repaired.get("command", "")
            # If command ran a python file e.g. "python3 test_calc.py", extract test_calc.py
            if not file_path and command:
                parts = command.split()
                for part in parts:
                    clean_part = part.strip("'\"")
                    if clean_part.endswith(".py") and os.path.exists(clean_part):
                        file_path = clean_part
                        break

            if file_path and os.path.exists(file_path):
                try:
                    from services.registry import ServiceRegistry
                    reg = ServiceRegistry.get_instance()
                    dev_service = reg.get("developer")
                    if dev_service:
                        dev_module = dev_service.metadata.get("module")
                        if dev_module:
                            fix_result = dev_module.debug_code({
                                "file_path": file_path,
                                "error_message": error_msg,
                            })
                            if fix_result.get("status") == "SUCCESS":
                                self.logger.info("LLM code repair succeeded for file %s", file_path)
                                return RepairResult(
                                    success=True,
                                    strategy_used=strategy,
                                    repaired_input=repaired,
                                    message=f"Auto-repaired code in '{file_path}' via LLM debugger",
                                )
                except Exception as ex:
                    self.logger.warning("LLM code repair failed: %s", ex)
            elif repaired.get("code"):
                try:
                    from services.registry import ServiceRegistry
                    reg = ServiceRegistry.get_instance()
                    dev_service = reg.get("developer")
                    if dev_service:
                        dev_module = dev_service.metadata.get("module")
                        if dev_module:
                            fix_result = dev_module.debug_code({
                                "code": repaired.get("code"),
                                "error_message": error_msg,
                            })
                            if fix_result.get("status") == "SUCCESS" and fix_result.get("fixed_code"):
                                repaired["code"] = fix_result["fixed_code"]
                                self.logger.info("LLM in-memory snippet repair succeeded")
                                return RepairResult(
                                    success=True,
                                    strategy_used=strategy,
                                    repaired_input=repaired,
                                    message="Auto-repaired code snippet via LLM debugger",
                                )
                except Exception as ex:
                    self.logger.warning("LLM snippet repair failed: %s", ex)

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

