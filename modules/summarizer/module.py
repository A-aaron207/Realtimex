"""
Summarizer Module entry point.

Declares the `summarize_text` capability. This module also declares a
dependency on the `model_gateway` service, which does not yet exist in
the Kernel -- Milestone 2's loader logs that gap as a warning rather
than failing the module, since service resolution is a future
milestone's responsibility.
"""

from __future__ import annotations

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the summarizer module."""

    module_id = "summarizer"
    capabilities = ["summarize_text"]

    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        return "Provides text summarization capability (execution not yet implemented)."
