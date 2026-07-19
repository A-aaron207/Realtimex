"""
Validation Engine for Realtimex Modules.

Combines directory layout check, manifest schema validation, and syntax/inheritance linting.
"""

from __future__ import annotations

import json
import os
from typing import Any, Tuple

from sdk.validation.schema import validate_dict_schema
from sdk.validation.lint import lint_python_file
from sdk.exceptions import SDKValidationError


def validate_module(module_dir: str, event_bus: Any = None) -> Tuple[bool, list[str]]:
    """
    Validate a module folder's structure, manifest, and entrypoint code integrity.
    
    Args:
        module_dir: Path to the target module directory
        event_bus: Optional Event Bus for event-driven updates
        
    Returns:
        Tuple of (validation_success_boolean, list_of_errors_or_warnings)
    """
    errors = []
    
    if not os.path.isdir(module_dir):
        errors.append(f"Module path is not a directory: {module_dir}")
        return False, errors

    # 1. Manifest existence
    manifest_path = os.path.join(module_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        errors.append(f"Missing required file: manifest.json")
        return False, errors

    # 2. Manifest load & parsing
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse JSON in manifest.json: {e}")
        return False, errors

    # 3. Validate manifest schema
    schema_errors = validate_dict_schema(manifest)
    errors.extend(schema_errors)
    if schema_errors:
        # Raise event and return early to prevent secondary parsing errors
        _emit_validation_event(module_dir, False, errors, event_bus)
        return False, errors

    # 4. Check folder structure
    required_dirs = ["tests", "prompts", "assets"]
    for r_dir in required_dirs:
        dir_path = os.path.join(module_dir, r_dir)
        if not os.path.isdir(dir_path):
            errors.append(f"Folder structure check warning: Missing '{r_dir}' folder.")

    # 5. Check entrypoint python script
    entrypoint = manifest["entrypoint"]
    entrypoint_path = os.path.join(module_dir, entrypoint)
    if not os.path.exists(entrypoint_path):
        errors.append(f"Missing entrypoint source file: {entrypoint}")
    else:
        # Run lint rules (AST inheritance)
        lint_errors = lint_python_file(entrypoint_path, manifest["type"])
        errors.extend(lint_errors)

    success = len([e for e in errors if not e.startswith("Folder structure check warning:") and not e.startswith("Source check warning:")]) == 0
    
    # Emit validation results
    _emit_validation_event(module_dir, success, errors, event_bus)

    return success, errors


def _emit_validation_event(
    module_dir: str,
    success: bool,
    errors: list[str],
    event_bus: Any,
) -> None:
    """Helper to emit ValidationPassed / ValidationFailed events."""
    if event_bus:
        try:
            from events.event import Event, EventPriority
            name = "ValidationPassed" if success else "ValidationFailed"
            event_bus.publish(
                Event(
                    name=name,
                    source="sdk.validation",
                    payload={"path": os.path.abspath(module_dir), "errors": errors},
                    priority=EventPriority.NORMAL,
                )
            )
        except Exception:
            pass
