"""
Manifest Generator for Realtimex MDK.

Generates manifest.json structures for Realtimex extensions.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def generate_manifest(
    name: str,
    version: str = "1.0.0",
    module_type: str = "module",
    entrypoint: str = "module.py",
    dependencies: Optional[dict[str, str]] = None,
    permissions: Optional[list[str]] = None,
    capabilities: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Generate manifest dictionary structure.
    
    Args:
        name: Extension name
        version: Semantic version string
        module_type: Extension type ('module', 'worker', 'provider', 'service')
        entrypoint: Script path or class name
        dependencies: Map of dependency requirements
        permissions: List of permission tokens requested
        capabilities: List of capability specifications
        
    Returns:
        Structured manifest dictionary
    """
    return {
        "name": name,
        "version": version,
        "type": module_type,
        "entrypoint": entrypoint,
        "dependencies": dependencies or {},
        "permissions": permissions or [],
        "capabilities": capabilities or [],
    }
