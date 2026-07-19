"""
Search Module entry point.

Declares the `web_search` capability. Milestone 2 only registers this
capability with the Kernel's Capability Registry; actual query
execution belongs to a future Task Manager / Scheduler milestone that
will invoke providers found through the registry.
"""

from __future__ import annotations

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the search module."""

    module_id = "search"
    capabilities = ["web_search"]

    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        return "Provides web search capability (execution not yet implemented)."
