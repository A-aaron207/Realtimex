"""
Linter for Realtimex Module source code.

Analyzes Python entrypoint source code via AST analysis to verify base class inheritance.
"""

from __future__ import annotations

import ast
import os
from typing import Any


def lint_python_file(filepath: str, expected_type: str) -> list[str]:
    """
    Statically analyze a Python file to check for syntax correctness
    and base class inheritance using Python's built-in AST.
    
    Args:
        filepath: Path to the Python file
        expected_type: Extension type ('module', 'worker', 'provider', 'service')
        
    Returns:
        List of lint warning and error messages.
    """
    errors = []
    if not os.path.exists(filepath):
        errors.append(f"Entrypoint source file not found: {filepath}")
        return errors

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
            
        tree = ast.parse(source, filename=filepath)
        
        # Gather Class definitions
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if not classes:
            errors.append(f"No Python class definitions found in: {os.path.basename(filepath)}")
            return errors

        # Determine expected base class name
        expected_bases = {
            "module": "BaseModule",
            "worker": "BaseWorker",
            "provider": "BaseProvider",
            "service": "BaseService",
        }
        target_base = expected_bases.get(expected_type)
        
        if not target_base:
            return errors  # No base class restriction

        inherits_correctly = False
        for cls in classes:
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id == target_base:
                    inherits_correctly = True
                    break
                elif isinstance(base, ast.Attribute) and base.attr == target_base:
                    inherits_correctly = True
                    break
            if inherits_correctly:
                break

        if not inherits_correctly:
            errors.append(
                f"Source check warning: Class in {os.path.basename(filepath)} should "
                f"inherit from base class '{target_base}'."
            )

    except SyntaxError as se:
        errors.append(f"Syntax error in {os.path.basename(filepath)} (line {se.lineno}): {se.msg}")
    except Exception as e:
        errors.append(f"AST lint analysis failed for {os.path.basename(filepath)}: {e}")

    return errors
