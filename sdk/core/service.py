"""
Base Service for Realtimex MDK.
"""

from __future__ import annotations

from sdk.core.module import ModuleContext


class BaseService:
    """Abstract base class for all Realtimex Services."""

    def __init__(self, context: ModuleContext) -> None:
        """
        Initialize Service.
        
        Args:
            context: Safe Sandbox ModuleContext
        """
        self.context = context

    def start(self) -> None:
        """Start execution of service background loops."""
        pass

    def stop(self) -> None:
        """Stop execution of service background loops."""
        pass
