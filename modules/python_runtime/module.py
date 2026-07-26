"""
Python Runtime Module entry point.

Provides safe, isolated Python code execution capabilities:
- execute_script  — run a .py file from disk
- execute_snippet — run an inline code string
- install_package — pip-install a package into the environment
- list_packages   — list currently installed packages
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
from typing import Any

from loader.module_base import ModuleEntryPoint

# Hard cap on execution time to prevent runaway scripts.
_EXEC_TIMEOUT = 30.0
_PIP_TIMEOUT = 60.0


def _run(args: list[str], cwd: str | None = None, timeout: float = _EXEC_TIMEOUT) -> dict[str, Any]:
    """Run a subprocess and return a structured result."""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"status": "FAILED", "error": "Execution timed out.", "exit_code": -1}
    except Exception as e:
        return {"status": "FAILED", "error": str(e), "exit_code": -1}


class Module(ModuleEntryPoint):
    """Entry point for the Python Runtime Module."""

    module_id = "python_runtime"
    capabilities = ["execute_script", "execute_snippet", "install_package", "list_packages"]

    def describe(self) -> str:
        return "Provides isolated Python script and snippet execution, package installation, and environment introspection."

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def execute_script(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a Python script file from disk."""
        script_path = input_data.get("script_path") or input_data.get("path")
        cwd = input_data.get("cwd")
        args = input_data.get("args", [])  # extra CLI args passed to the script

        if not script_path:
            return {"status": "FAILED", "error": "No script_path provided."}

        script_path = os.path.abspath(script_path)
        if not os.path.isfile(script_path):
            return {"status": "FAILED", "error": f"Script not found: {script_path}"}

        cmd = [sys.executable, script_path] + [str(a) for a in args]
        result = _run(cmd, cwd=cwd or os.path.dirname(script_path))
        result["script_path"] = script_path
        return result

    def execute_snippet(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute an inline Python code snippet in an isolated temp file."""
        code = input_data.get("code") or input_data.get("snippet")
        cwd = input_data.get("cwd")

        if not code:
            return {"status": "FAILED", "error": "No code snippet provided."}

        # Write snippet to a temp file so tracebacks have a real path.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="rtx_snippet_",
            delete=False
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            cmd = [sys.executable, tmp_path]
            result = _run(cmd, cwd=cwd)
            result["snippet_file"] = tmp_path
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def install_package(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Install a PyPI package using pip with package name and existence validation."""
        package = input_data.get("package") or input_data.get("name")
        version = input_data.get("version")  # optional pinned version, e.g. "1.2.3"
        upgrade = input_data.get("upgrade", False)

        if not package:
            return {"status": "FAILED", "error": "No package name provided."}

        # Validate package name format
        import re
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", package):
            return {"status": "FAILED", "error": f"Invalid package name format: '{package}'."}

        # Check if package exists on PyPI (non-blocking fallback if offline)
        import urllib.request
        import urllib.error
        try:
            url = f"https://pypi.org/pypi/{package}/json"
            with urllib.request.urlopen(url, timeout=2.0) as response:
                pass
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"status": "FAILED", "error": f"Package '{package}' does not exist on PyPI."}
        except Exception:
            # Network timeout/offline: allow execution to fall through to pip directly
            pass

        pkg_spec = f"{package}=={version}" if version else package
        cmd = [sys.executable, "-m", "pip", "install", pkg_spec]
        if upgrade:
            cmd.append("--upgrade")

        result = _run(cmd, timeout=_PIP_TIMEOUT)
        result["package"] = pkg_spec
        return result

    def list_packages(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """List all packages installed in the current Python environment."""
        fmt = input_data.get("format", "columns")  # columns | json | freeze
        cmd = [sys.executable, "-m", "pip", "list"]

        if fmt == "json":
            cmd += ["--format", "json"]
        elif fmt == "freeze":
            cmd = [sys.executable, "-m", "pip", "freeze"]
        else:
            cmd += ["--format", "columns"]

        result = _run(cmd)
        result["format"] = fmt
        return result

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        if capability == "execute_script":
            return self.execute_script(context.input)
        elif capability == "execute_snippet":
            return self.execute_snippet(context.input)
        elif capability == "install_package":
            return self.install_package(context.input)
        elif capability == "list_packages":
            return self.list_packages(context.input)
        else:
            raise NotImplementedError(f"Capability '{capability}' not supported by Python Runtime Module.")
