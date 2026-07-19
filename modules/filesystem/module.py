"""
Filesystem Module entry point.

Declares the `read_file` and `write_file` capabilities. This module
requests read_write filesystem permission in its manifest; Milestone 2
stores that declaration as sandbox metadata only -- no enforcement is
implemented until a future Permission Engine milestone.
"""

from __future__ import annotations

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the filesystem module."""

    module_id = "filesystem"
    capabilities = ["read_file", "write_file"]

    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        return "Provides file read/write capabilities (execution not yet implemented)."
