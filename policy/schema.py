"""
Policy Schema definition for Realtimex.

Defines the structure and validation constraints for system policies.
"""

from __future__ import annotations

import re
from typing import Any


POLICY_SCHEMA = {
    "policy_id": {"type": str, "required": True, "regex": r"^[a-z0-9_-]+$"},
    "name": {"type": str, "required": True},
    "version": {"type": str, "required": True, "regex": r"^\d+\.\d+\.\d+$"},
    "category": {"type": str, "required": True, "allowed": [
        "security", "permissions", "memory", "scheduler",
        "worker", "models", "resource", "interfaces"
    ]},
    "conditions": {"type": list, "required": True},
    "effect": {"type": str, "required": True, "allowed": ["allow", "deny"]},
    "priority": {"type": int, "required": True},
    "enabled": {"type": bool, "required": True},
    "metadata": {"type": dict, "required": False}
}


def validate_policy_dict(policy: dict[str, Any]) -> list[str]:
    """
    Validate a policy dictionary against the POLICY_SCHEMA rules.
    
    Returns:
        List of validation error messages. Empty list means validation passed.
    """
    errors = []
    
    for field, rule in POLICY_SCHEMA.items():
        if rule["required"] and field not in policy:
            errors.append(f"Missing required field: '{field}'")
            continue
            
        if field in policy:
            value = policy[field]
            expected_type = rule["type"]
            if not isinstance(value, expected_type):
                errors.append(
                    f"Invalid type for '{field}': expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )
                continue
                
            if "regex" in rule and isinstance(value, str):
                if not re.match(rule["regex"], value):
                    errors.append(f"Format error on '{field}': does not match expected patterns.")
                    
            if "allowed" in rule:
                if value not in rule["allowed"]:
                    errors.append(f"Value error on '{field}': must be one of {rule['allowed']}.")
                    
    # Validate condition structures
    if "conditions" in policy and isinstance(policy["conditions"], list):
        for idx, cond in enumerate(policy["conditions"]):
            if not isinstance(cond, dict):
                errors.append(f"Condition at index {idx} must be a dictionary.")
                continue
            for req_key in ["field", "operator", "value"]:
                if req_key not in cond:
                    errors.append(f"Condition at index {idx} missing required key: '{req_key}'")
                    
    return errors
