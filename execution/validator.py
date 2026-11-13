"""
Result Validator component for Executor 2.0.

Validates that observed runtime outcomes meet target expectations and post-conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from execution.observer import ExecutionObservation


@dataclass
class ExecutionValidationResult:
    """Validation report produced after observing an action step."""
    is_valid: bool
    reason: str = "Result validated"
    requires_repair: bool = False
    repair_strategy: str | None = None


class ExecutionResultValidator:
    """
    Validates execution observations against capability-specific post-conditions.
    """

    def validate_observation(
        self,
        observation: ExecutionObservation,
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionValidationResult:
        """
        Validate an ExecutionObservation.
        """
        input_data = input_data or {}

        # 1. Base status check
        if not observation.is_success:
            err = observation.error or f"Execution status was '{observation.status}'"
            strategy = self._determine_repair_strategy(observation.capability, err, input_data)
            return ExecutionValidationResult(
                is_valid=False,
                reason=err,
                requires_repair=strategy is not None,
                repair_strategy=strategy,
            )

        cap = observation.capability

        # 2. Capability post-condition checks
        if cap in ("write_file", "generate_code"):
            file_path = input_data.get("file_path") or input_data.get("destination") or observation.output.get("file_path")
            if file_path and isinstance(file_path, str):
                p = Path(file_path)
                if not p.exists():
                    return ExecutionValidationResult(
                        is_valid=False,
                        reason=f"Post-condition failed: Target file '{file_path}' does not exist after write operation.",
                        requires_repair=True,
                        repair_strategy="create_parent_directory",
                    )

        elif cap in ("run_command", "execute_snippet", "execute_script"):
            exit_code = observation.exit_code
            if exit_code is not None and exit_code != 0:
                err_text = observation.error or ""
                strategy = self._determine_repair_strategy(cap, err_text, input_data) or "retry_command"
                return ExecutionValidationResult(
                    is_valid=False,
                    reason=f"Command exited with non-zero status code: {exit_code}. Output: {err_text}",
                    requires_repair=True,
                    repair_strategy=strategy,
                )

        return ExecutionValidationResult(is_valid=True)

    def _determine_repair_strategy(self, capability: str, error_msg: str, input_data: dict[str, Any]) -> str | None:
        """Categorize error message into a deterministic or LLM repair strategy."""
        err_lower = error_msg.lower()

        if any(term in err_lower for term in [
            "traceback", "syntaxerror", "zerodivisionerror", "nameerror",
            "attributeerror", "typeerror", "modulenotfounderror", "importerror",
            "indexerror", "keyerror", "valueerror", "assertionerror"
        ]):
            return "llm_code_repair"

        if "no such file or directory" in err_lower or "directory missing" in err_lower or "filenotfound" in err_lower:
            return "create_parent_directory"
        if "no file path provided" in err_lower or "no path provided" in err_lower:
            return "resolve_missing_file_path"
        if "permission denied" in err_lower or "permissionerror" in err_lower:
            return "use_fallback_directory"
        if "timeout" in err_lower or "timed out" in err_lower:
            return "retry_with_backoff"
        if "connection refused" in err_lower or "network" in err_lower:
            return "retry_network"

        return "retry_default"

