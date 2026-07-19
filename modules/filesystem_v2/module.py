"""
Filesystem v2 Module entry point.

Advanced file management capabilities:
- read_file       — read text or binary content from a file
- write_file      — write/append text content to a file
- list_directory  — list directory contents with metadata
- search_files    — search files by name pattern or content substring
- copy            — copy a file or directory tree
- delete          — delete a file or directory
"""

from __future__ import annotations

import os
import re
import shutil
import fnmatch
from pathlib import Path
from typing import Any

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the Filesystem v2 Module."""

    module_id = "filesystem_v2"
    capabilities = ["read_file", "write_file", "list_directory", "search_files", "copy", "delete"]

    def describe(self) -> str:
        return "Advanced filesystem operations: read, write, list, search, copy, and delete files and directories."

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def read_file(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Read a file and return its content."""
        path = input_data.get("path")
        encoding = input_data.get("encoding", "utf-8")
        start_line = input_data.get("start_line")  # 1-indexed, optional
        end_line = input_data.get("end_line")       # 1-indexed inclusive, optional

        if not path:
            return {"status": "FAILED", "error": "No path provided."}

        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return {"status": "FAILED", "error": f"File not found: {path}"}

        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()

            if start_line or end_line:
                s = (start_line or 1) - 1
                e = end_line or len(lines)
                lines = lines[s:e]

            content = "".join(lines)
            return {
                "status": "SUCCESS",
                "path": path,
                "content": content,
                "size_bytes": os.path.getsize(path),
                "line_count": len(lines)
            }
        except Exception as ex:
            return {"status": "FAILED", "error": str(ex)}

    def write_file(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Write or append text content to a file. Creates parent dirs if needed."""
        path = input_data.get("path")
        content = input_data.get("content", "")
        mode = input_data.get("mode", "write")   # write | append
        encoding = input_data.get("encoding", "utf-8")

        if not path:
            return {"status": "FAILED", "error": "No path provided."}

        path = os.path.abspath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        file_mode = "a" if mode == "append" else "w"

        try:
            with open(path, file_mode, encoding=encoding) as f:
                f.write(content)
            return {
                "status": "SUCCESS",
                "path": path,
                "bytes_written": len(content.encode(encoding)),
                "mode": mode
            }
        except Exception as ex:
            return {"status": "FAILED", "error": str(ex)}

    def list_directory(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """List the contents of a directory with type and size metadata."""
        path = input_data.get("path", ".")
        recursive = input_data.get("recursive", False)
        pattern = input_data.get("pattern", "*")  # glob pattern filter

        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return {"status": "FAILED", "error": f"Directory not found: {path}"}

        entries = []
        try:
            if recursive:
                for root, dirs, files in os.walk(path):
                    for name in dirs + files:
                        full = os.path.join(root, name)
                        rel = os.path.relpath(full, path)
                        if fnmatch.fnmatch(name, pattern):
                            entries.append(_entry_meta(full, rel))
            else:
                for name in os.listdir(path):
                    full = os.path.join(path, name)
                    if fnmatch.fnmatch(name, pattern):
                        entries.append(_entry_meta(full, name))

            return {
                "status": "SUCCESS",
                "path": path,
                "entry_count": len(entries),
                "entries": entries
            }
        except Exception as ex:
            return {"status": "FAILED", "error": str(ex)}

    def search_files(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Search for files by name pattern and/or content substring."""
        root = input_data.get("root", ".")
        name_pattern = input_data.get("name_pattern")   # e.g. "*.py"
        content_query = input_data.get("content_query") # substring to grep for
        max_results = int(input_data.get("max_results", 50))
        case_sensitive = input_data.get("case_sensitive", False)

        root = os.path.abspath(root)
        if not os.path.isdir(root):
            return {"status": "FAILED", "error": f"Root directory not found: {root}"}

        matches = []
        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            for dirpath, _, filenames in os.walk(root):
                for fname in filenames:
                    if name_pattern and not fnmatch.fnmatch(fname, name_pattern):
                        continue
                    full = os.path.join(dirpath, fname)
                    rel = os.path.relpath(full, root)

                    if content_query:
                        try:
                            text = Path(full).read_text(encoding="utf-8", errors="ignore")
                            hits = [
                                (i + 1, line.rstrip())
                                for i, line in enumerate(text.splitlines())
                                if re.search(content_query, line, flags)
                            ]
                            if hits:
                                matches.append({"path": rel, "hits": hits})
                        except Exception:
                            pass
                    else:
                        matches.append({"path": rel})

                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break

            return {
                "status": "SUCCESS",
                "root": root,
                "match_count": len(matches),
                "matches": matches
            }
        except Exception as ex:
            return {"status": "FAILED", "error": str(ex)}

    def copy(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Copy a file or directory to a destination path."""
        src = input_data.get("src") or input_data.get("source")
        dst = input_data.get("dst") or input_data.get("destination")
        overwrite = input_data.get("overwrite", False)

        if not src or not dst:
            return {"status": "FAILED", "error": "Both src and dst paths are required."}

        src = os.path.abspath(src)
        dst = os.path.abspath(dst)

        if not os.path.exists(src):
            return {"status": "FAILED", "error": f"Source not found: {src}"}
        if os.path.exists(dst) and not overwrite:
            return {"status": "FAILED", "error": f"Destination already exists: {dst}. Set overwrite=true to replace."}

        try:
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            return {"status": "SUCCESS", "src": src, "dst": dst}
        except Exception as ex:
            return {"status": "FAILED", "error": str(ex)}

    def delete(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Delete a file or directory."""
        path = input_data.get("path")
        recursive = input_data.get("recursive", False)  # required for non-empty dirs

        if not path:
            return {"status": "FAILED", "error": "No path provided."}

        path = os.path.abspath(path)
        if not os.path.exists(path):
            return {"status": "FAILED", "error": f"Path not found: {path}"}

        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                if recursive:
                    shutil.rmtree(path)
                else:
                    os.rmdir(path)  # fails if non-empty — intentional
            return {"status": "SUCCESS", "deleted": path}
        except Exception as ex:
            return {"status": "FAILED", "error": str(ex)}

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        dispatch = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "list_directory": self.list_directory,
            "search_files": self.search_files,
            "copy": self.copy,
            "delete": self.delete,
        }
        if capability not in dispatch:
            raise NotImplementedError(f"Capability '{capability}' not supported by Filesystem v2 Module.")
        return dispatch[capability](context.input)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _entry_meta(full_path: str, display_name: str) -> dict[str, Any]:
    """Return a metadata dict for a single filesystem entry."""
    is_dir = os.path.isdir(full_path)
    meta: dict[str, Any] = {
        "name": display_name,
        "type": "directory" if is_dir else "file",
    }
    if not is_dir:
        try:
            meta["size_bytes"] = os.path.getsize(full_path)
        except OSError:
            meta["size_bytes"] = None
    return meta
