"""
Base Provider for Realtimex MDK.
"""

from __future__ import annotations

from typing import Any
from sdk.core.module import ModuleContext


class BaseProvider:
    """Abstract base class for all Realtimex Model Providers."""

    def __init__(self, context: ModuleContext) -> None:
        """
        Initialize Provider.
        
        Args:
            context: Safe Sandbox ModuleContext
        """
        self.context = context

    def generate(self, prompt: str, **kwargs: Any) -> Any:
        """Execute text generation request against target provider APIs."""
        raise NotImplementedError("Providers must implement the generate method.")
