"""
Configuration Validator for Realtimex.

Validates configuration values against rules and constraints.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from configuration.exceptions import (
    ConfigurationValidationError,
    ConfigurationTypeError,
    ConfigurationRangeError,
)


class ConfigurationValidator:
    """
    Validates configuration values.
    
    Supports:
    - Required fields
    - Type validation
    - Range validation
    - Custom validators
    - Version compatibility
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize Configuration Validator.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.validator")
        self._rules: dict[str, dict] = {}  # namespace.key -> rules
        self._custom_validators: dict[str, Callable] = {}

    def register_rule(
        self,
        namespace: str,
        key: str,
        required: bool = False,
        expected_type: type | None = None,
        min_value: Any | None = None,
        max_value: Any | None = None,
        allowed_values: list[Any] | None = None,
        validator: Callable[[Any], bool] | None = None,
    ) -> None:
        """
        Register validation rule for configuration key.
        
        Args:
            namespace: Configuration namespace
            key: Configuration key
            required: Whether value is required
            expected_type: Expected Python type
            min_value: Minimum value (for numbers/strings)
            max_value: Maximum value (for numbers/strings)
            allowed_values: List of allowed values
            validator: Custom validator function
        """
        rule_key = f"{namespace}.{key}"
        self._rules[rule_key] = {
            "namespace": namespace,
            "key": key,
            "required": required,
            "expected_type": expected_type,
            "min_value": min_value,
            "max_value": max_value,
            "allowed_values": allowed_values,
            "validator": validator,
        }

    def validate_value(
        self,
        namespace: str,
        key: str,
        value: Any,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a single configuration value.
        
        Args:
            namespace: Configuration namespace
            key: Configuration key
            value: Value to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        rule_key = f"{namespace}.{key}"
        
        if rule_key not in self._rules:
            # No rules defined for this key
            return True, None
        
        rule = self._rules[rule_key]
        
        # Check required
        if rule["required"] and value is None:
            error = f"Required configuration {namespace}.{key} is missing"
            self.logger.warning(error)
            return False, error
        
        if value is None:
            return True, None
        
        # Check type
        if rule["expected_type"] is not None:
            if not isinstance(value, rule["expected_type"]):
                error = (
                    f"Configuration {namespace}.{key} has wrong type: "
                    f"expected {rule['expected_type'].__name__}, "
                    f"got {type(value).__name__}"
                )
                self.logger.warning(error)
                return False, error
        
        # Check allowed values
        if rule["allowed_values"] is not None:
            if value not in rule["allowed_values"]:
                error = (
                    f"Configuration {namespace}.{key} has invalid value: "
                    f"{value}. Allowed: {rule['allowed_values']}"
                )
                self.logger.warning(error)
                return False, error
        
        # Check range (numeric)
        if isinstance(value, (int, float)):
            if rule["min_value"] is not None and value < rule["min_value"]:
                error = (
                    f"Configuration {namespace}.{key} is below minimum: "
                    f"{value} < {rule['min_value']}"
                )
                self.logger.warning(error)
                return False, error
            
            if rule["max_value"] is not None and value > rule["max_value"]:
                error = (
                    f"Configuration {namespace}.{key} is above maximum: "
                    f"{value} > {rule['max_value']}"
                )
                self.logger.warning(error)
                return False, error
        
        # Check range (string length)
        if isinstance(value, str):
            if rule["min_value"] is not None and len(value) < rule["min_value"]:
                error = (
                    f"Configuration {namespace}.{key} string too short: "
                    f"{len(value)} < {rule['min_value']}"
                )
                self.logger.warning(error)
                return False, error
            
            if rule["max_value"] is not None and len(value) > rule["max_value"]:
                error = (
                    f"Configuration {namespace}.{key} string too long: "
                    f"{len(value)} > {rule['max_value']}"
                )
                self.logger.warning(error)
                return False, error
        
        # Check custom validator
        if rule["validator"] is not None:
            try:
                if not rule["validator"](value):
                    error = (
                        f"Configuration {namespace}.{key} failed custom validation: {value}"
                    )
                    self.logger.warning(error)
                    return False, error
            except Exception as e:
                error = (
                    f"Configuration {namespace}.{key} custom validator raised: {e}"
                )
                self.logger.warning(error)
                return False, error
        
        return True, None

    def validate_namespace(
        self,
        namespace: str,
        config: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate entire namespace configuration.
        
        Args:
            namespace: Configuration namespace
            config: Configuration dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        for key, value in config.items():
            is_valid, error = self.validate_value(namespace, key, value)
            if not is_valid:
                errors.append(error)
        
        # Check for required keys that are missing
        for rule_key, rule in self._rules.items():
            if rule["namespace"] != namespace:
                continue
            
            if rule["required"] and rule["key"] not in config:
                error = f"Required configuration {rule_key} is missing"
                errors.append(error)
                self.logger.warning(error)
        
        return len(errors) == 0, errors

    def validate_all(
        self,
        config: dict[str, dict[str, Any]],
    ) -> tuple[bool, dict[str, list[str]]]:
        """
        Validate entire configuration.
        
        Args:
            config: Complete configuration dictionary
            
        Returns:
            Tuple of (is_valid, {namespace: [errors]})
        """
        all_errors = {}
        is_valid = True
        
        # Get all namespaces that have rules
        namespaces_with_rules = set()
        for rule_key in self._rules:
            namespace = rule_key.rsplit(".", 1)[0]
            namespaces_with_rules.add(namespace)
        
        # Validate namespaces with rules
        for namespace in namespaces_with_rules:
            ns_config = config.get(namespace, {})
            valid, errors = self.validate_namespace(namespace, ns_config)
            if not valid:
                all_errors[namespace] = errors
                is_valid = False
        
        return is_valid, all_errors

    def register_custom_validator(
        self,
        name: str,
        validator: Callable[[Any], bool],
    ) -> None:
        """
        Register a custom validator function.
        
        Args:
            name: Validator name
            validator: Validator function
        """
        self._custom_validators[name] = validator
        self.logger.debug("Custom validator registered: %s", name)

    def get_validator(self, name: str) -> Optional[Callable]:
        """
        Get custom validator by name.
        
        Args:
            name: Validator name
            
        Returns:
            Validator function or None
        """
        return self._custom_validators.get(name)

    def list_rules(self, namespace: str | None = None) -> list[dict]:
        """
        List validation rules.
        
        Args:
            namespace: Optional filter by namespace
            
        Returns:
            List of rule dictionaries
        """
        rules = []
        for rule_key, rule in self._rules.items():
            if namespace is None or rule["namespace"] == namespace:
                rules.append(rule)
        return rules
