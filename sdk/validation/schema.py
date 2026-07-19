"""
Manifest Schema rules for Realtimex MDK.

Defines the structure, types, and constraints for extension manifests.
"""

from __future__ import annotations

import re
from typing import Any, Optional


MANIFEST_SCHEMA = {
    "name": {
        "type": str,
        "required": True,
        "regex": r"^[a-z0-9_-]+$",
        "error": "name must be lowercase alphanumeric, underscores, or hyphens."
    },
    "version": {
        "type": str,
        "required": True,
        "regex": r"^\d+\.\d+\.\d+$",
        "error": "version must follow semantic versioning syntax (e.g. 1.0.0)."
    },
    "type": {
        "type": str,
        "required": True,
        "allowed": ["module", "worker", "provider", "service"],
        "error": "type must be one of 'module', 'worker', 'provider', or 'service'."
    },
    "entrypoint": {
        "type": str,
        "required": True,
        "regex": r"^.*\.py$",
        "error": "entrypoint must be a path pointing to a Python file (.py)."
    },
    "dependencies": {
        "type": dict,
        "required": False
    },
    "permissions": {
        "type": list,
        "required": False
    },
    "capabilities": {
        "type": list,
        "required": False
    }
}


def validate_dict_schema(manifest: dict[str, Any]) -> list[str]:
    """
    Validate a manifest dictionary against MANIFEST_SCHEMA rules.
    
    Returns:
        List of validation error messages. Empty list means validation passed.
    """
    errors = []
    
    # 1. Check required fields and types
    for field, rule in MANIFEST_SCHEMA.items():
        if rule["required"] and field not in manifest:
            errors.append(f"Missing required field: '{field}'")
            continue
            
        if field in manifest:
            value = manifest[field]
            expected_type = rule["type"]
            if not isinstance(value, expected_type):
                errors.append(
                    f"Invalid type for '{field}': expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
                continue
                
            # Regex checks
            if "regex" in rule:
                if not re.match(rule["regex"], value):
                    errors.append(f"Format error on '{field}': {rule.get('error', 'invalid format')}")
                    
            # Allowed value sets
            if "allowed" in rule:
                if value not in rule["allowed"]:
                    errors.append(f"Value error on '{field}': {rule.get('error', 'value not allowed')}")
                    
    return errors
