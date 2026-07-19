"""
Base Worker for Realtimex MDK.
"""

from __future__ import annotations

from typing import Any
from sdk.core.module import ModuleContext


class BaseWorker:
    """Abstract base class for all Realtimex Workers."""

    def __init__(self, context: ModuleContext) -> None:
        """
        Initialize Worker.
        
        Args:
            context: Safe Sandbox ModuleContext
        """
        self.context = context

    def run_task(self, task: Any) -> Any:
        """Main execution method to implement."""
        raise NotImplementedError("Workers must implement the run_task method.")
