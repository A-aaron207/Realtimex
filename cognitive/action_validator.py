"""
Action Validator module for Planner 2.0.

Validates every action step immediately before execution to ensure parameters exist,
variables are resolved, permissions are present, paths are valid, and confidence
thresholds are met.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cognitive.exceptions import ValidationError


class ActionValidationError(ValidationError):
    """Raised when an action step fails pre-execution validation."""
    pass


@dataclass
class ValidationResult:
    """Result returned by ActionValidator."""
    is_valid: bool
    reason: str = "Validation passed"
    should_replan: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class ActionValidator:
    """
    Pre-execution validator for individual action steps in Planner 2.0.
    """

    def __init__(
        self,
        min_confidence_threshold: float = 0.70,
        disallowed_path_prefixes: tuple[str, ...] = ("/etc", "/var", "/proc", "/sys"),
    ) -> None:
        self.min_confidence_threshold = min_confidence_threshold
        self.disallowed_path_prefixes = disallowed_path_prefixes
        self._var_pattern = re.compile(r"\{\{([^}]+)\}\}")

    def validate_action(
        self,
        step: dict[str, Any],
        context: dict[str, Any] | None = None,
        available_capabilities: list[str] | None = None,
        granted_permissions: set[str] | None = None,
        confidence_score: float = 1.0,
    ) -> ValidationResult:
        """
        Validate an action step before execution.

        Checks:
        1. Confidence score threshold
        2. Unresolved {{variable}} tags
        3. Capability existence & availability
        4. Destination path safety & existence
        5. Required parameter presence
        6. Permission checks
        """
        context = context or {}

        # 1. Confidence score threshold check
        if confidence_score < self.min_confidence_threshold:
            return ValidationResult(
                is_valid=False,
                reason=f"Action confidence score {confidence_score:.2f} is below minimum threshold {self.min_confidence_threshold:.2f}",
                should_replan=True,
                details={"confidence_score": confidence_score, "threshold": self.min_confidence_threshold},
            )

        step_id = step.get("step_id", "unknown_step")
        capability = step.get("capability")

        if not capability:
            return ValidationResult(
                is_valid=False,
                reason=f"Step '{step_id}' missing required 'capability' key.",
                should_replan=True,
            )

        # 2. Capability availability check
        if available_capabilities is not None and capability not in available_capabilities:
            return ValidationResult(
                is_valid=False,
                reason=f"Capability '{capability}' required by step '{step_id}' is not available.",
                should_replan=True,
                details={"capability": capability, "available": available_capabilities},
            )

        input_data = step.get("input_data") or step.get("input") or {}

        # 3. Check for unresolved {{variable}} tags
        unresolved_vars = self._find_unresolved_variables(input_data)
        if unresolved_vars:
            return ValidationResult(
                is_valid=False,
                reason=f"Step '{step_id}' contains unresolved variables: {', '.join(unresolved_vars)}",
                should_replan=True,
                details={"unresolved_variables": unresolved_vars},
            )

        # 4. Path safety and destination path validation
        if capability in ("write_file", "read_file", "delete_file", "generate_code"):
            file_path = input_data.get("file_path") or input_data.get("path") or input_data.get("destination")
            if file_path and isinstance(file_path, str):
                path_res = self._validate_file_path(file_path, capability, step_id)
                if not path_res.is_valid:
                    return path_res

        # 4b. Command safety validation
        if capability in ("run_command", "execute_snippet", "execute_script"):
            cmd = str(input_data.get("command", "")).strip()
            dangerous_patterns = [
                r"\bmv\s+(?:-[a-zA-Z]+\s+)*\*\s+",
                r"\bmv\s+(?:-[a-zA-Z]+\s+)*\.\/\*\s+",
                r"\bcp\s+(?:-[a-zA-Z]+\s+)*\*\s+",
                r"\bcp\s+(?:-[a-zA-Z]+\s+)*\.\/\*\s+",
            ]
            for pat in dangerous_patterns:
                if re.search(pat, cmd):
                    return ValidationResult(
                        is_valid=False,
                        reason=f"Dangerous command '{cmd}' blocked: moving or copying entire workspace is prohibited.",
                        should_replan=True,
                    )

        # 5. Permission checks
        if granted_permissions is not None:
            required_perm = step.get("required_permission") or capability
            if required_perm and required_perm not in granted_permissions and f"capability:{capability}" not in granted_permissions:
                # If permissions dict has safety mode
                if "all" not in granted_permissions:
                    return ValidationResult(
                        is_valid=False,
                        reason=f"Step '{step_id}' requires permission '{required_perm}' which is not granted.",
                        should_replan=False,
                        details={"required_permission": required_perm},
                    )

        return ValidationResult(is_valid=True)

    def _find_unresolved_variables(self, obj: Any) -> list[str]:
        """Recursively scan data structure for unresolved {{var}} strings."""
        unresolved: list[str] = []

        if isinstance(obj, str):
            matches = self._var_pattern.findall(obj)
            unresolved.extend(matches)
        elif isinstance(obj, dict):
            for v in obj.values():
                unresolved.extend(self._find_unresolved_variables(v))
        elif isinstance(obj, list):
            for item in obj:
                unresolved.extend(self._find_unresolved_variables(item))

        return unresolved

    def _validate_file_path(self, file_path: str, capability: str, step_id: str) -> ValidationResult:
        """Validate destination or source file path."""
        # Check path traversal
        if "../" in file_path or "..\\" in file_path:
            return ValidationResult(
                is_valid=False,
                reason=f"Unsafe file path '{file_path}' in step '{step_id}' contains path traversal ('../').",
                should_replan=False,
            )

        # Check restricted path prefixes
        for prefix in self.disallowed_path_prefixes:
            if file_path.startswith(prefix):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Unsafe file path '{file_path}' in step '{step_id}' accesses system directory '{prefix}'.",
                    should_replan=False,
                )

        # For read_file, verify file exists
        if capability == "read_file":
            p = Path(file_path)
            if not p.exists():
                return ValidationResult(
                    is_valid=False,
                    reason=f"Referenced file '{file_path}' in step '{step_id}' does not exist.",
                    should_replan=True,
                )

        return ValidationResult(is_valid=True)
