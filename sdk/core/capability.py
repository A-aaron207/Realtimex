"""
Base Capability for Realtimex MDK.
"""

from __future__ import annotations

from typing import Any
from sdk.core.module import ModuleContext


class BaseCapability:
    """Abstract base class for all Realtimex Capabilities."""

    def __init__(self, context: ModuleContext) -> None:
        """
        Initialize Capability.
        
        Args:
            context: Safe Sandbox ModuleContext
        """
        self.context = context

    def execute_capability(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the capability logic."""
        raise NotImplementedError("Capabilities must implement the execute_capability method.")
