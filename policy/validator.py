"""
Policy Validator for Realtimex.

Validates policy dictionaries against schema definitions.
"""

from __future__ import annotations

from typing import Any, Tuple

from policy.schema import validate_policy_dict
from policy.exceptions import PolicyValidationError


class PolicyValidator:
    """Enforces policy format validation and validation event diagnostics."""

    def validate(self, policy: dict[str, Any]) -> Tuple[bool, list[str]]:
        """
        Validate policy against schema rules.
        
        Args:
            policy: Policy dictionary to validate
            
        Returns:
            Tuple of (success_boolean, list_of_error_strings)
        """
        errors = validate_policy_dict(policy)
        return len(errors) == 0, errors

    def validate_or_raise(self, policy: dict[str, Any]) -> None:
        """
        Validate policy or raise PolicyValidationError if rules are breached.
        
        Args:
            policy: Policy dictionary
            
        Raises:
            PolicyValidationError: If validation fails
        """
        success, errors = self.validate(policy)
        if not success:
            raise PolicyValidationError(f"Policy validation failed: {errors}")
