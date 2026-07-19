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
        return "Provides file read/write capabilities."

    def read_file(self, input_data: dict[str, Any] | str) -> dict[str, Any]:
        """
        Read a file from disk.
        """
        import os
        if isinstance(input_data, dict):
            file_path = input_data.get("file_path") or input_data.get("target") or input_data.get("path")
        else:
            file_path = str(input_data)

        if not file_path:
            return {"error": "No file path provided."}

        # Resolve path
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {
                "file_contents": content,
                "file_path": file_path,
                "status": "SUCCESS"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "FAILED"
            }

    def write_file(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Write content to a file on disk.
        """
        import os
        file_path = input_data.get("file_path") or input_data.get("target") or input_data.get("path")
        content = input_data.get("content") or input_data.get("data") or ""

        if not file_path:
            return {"error": "No file path provided."}

        # Resolve path
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "bytes_written": len(content),
                "file_path": file_path,
                "status": "SUCCESS"
            }
        except Exception as e:
            return {
                "error": str(e),
                "status": "FAILED"
            }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized execution entry point mapping capabilities to methods."""
        if capability == "read_file":
            return self.read_file(context.input)
        elif capability == "write_file":
            return self.write_file(context.input)
        else:
            raise NotImplementedError(f"Capability {capability} not supported by this module.")


