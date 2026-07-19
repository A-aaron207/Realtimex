"""
Rule Compiler for Realtimex Policy Engine.

Compiles policy conditions into fast callable evaluation functions.
"""

from __future__ import annotations

import re
from typing import Any, Callable


def get_nested_value(data: dict[str, Any], path: str) -> Any:
    """Retrieve a nested dictionary value using a dot-notated string (e.g. 'user.role')."""
    parts = path.split(".")
    curr = data
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return None
    return curr


class RuleCompiler:
    """Translates dictionary-based policy conditions into executable Python callables."""

    def compile_condition(self, condition: dict[str, Any]) -> Callable[[dict[str, Any]], bool]:
        """Compile a single condition structure into a context-evaluating function."""
        field = condition["field"]
        op = condition["operator"].lower()
        expected = condition["value"]

        if op in ("equals", "eq"):
            return lambda ctx: get_nested_value(ctx, field) == expected
            
        elif op in ("not_equals", "neq"):
            return lambda ctx: get_nested_value(ctx, field) != expected
            
        elif op in ("greater_than", "gt"):
            return lambda ctx: self._compare(get_nested_value(ctx, field), expected, "__gt__")
            
        elif op in ("less_than", "lt"):
            return lambda ctx: self._compare(get_nested_value(ctx, field), expected, "__lt__")
            
        elif op in ("greater_equal", "gte"):
            return lambda ctx: self._compare(get_nested_value(ctx, field), expected, "__ge__")
            
        elif op in ("less_equal", "lte"):
            return lambda ctx: self._compare(get_nested_value(ctx, field), expected, "__le__")
            
        elif op == "contains":
            return lambda ctx: expected in (get_nested_value(ctx, field) or [])
            
        elif op == "in":
            return lambda ctx: get_nested_value(ctx, field) in (expected or [])
            
        elif op == "regex":
            pattern = re.compile(str(expected))
            return lambda ctx: bool(pattern.search(str(get_nested_value(ctx, field) or "")))
            
        else:
            # Unsupported operator default false
            return lambda ctx: False

    def compile_policy(self, conditions: list[dict[str, Any]]) -> Callable[[dict[str, Any]], bool]:
        """Compile a list of conditions (conjunction AND) into a single context-evaluator callable."""
        compiled_conditions = [self.compile_condition(cond) for cond in conditions]
        return lambda ctx: all(c(ctx) for c in compiled_conditions)

    def _compare(self, left: Any, right: Any, op_method: str) -> bool:
        """Type-safe numeric comparison helper."""
        if left is None or right is None:
            return False
        try:
            return getattr(left, op_method)(right)
        except Exception:
            return False
