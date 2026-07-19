"""
Terminal Module entry point.

Provides capabilities for:
- run_command
- spawn_session
- execute_session_command
"""

from __future__ import annotations

import os
import uuid
import subprocess
from typing import Any

from loader.module_base import ModuleEntryPoint


class Module(ModuleEntryPoint):
    """Entry point for the Terminal Module."""

    module_id = "terminal"
    capabilities = ["run_command", "spawn_session", "execute_session_command"]

    def __init__(self) -> None:
        """Initialize the terminal module."""
        self._sessions: dict[str, dict[str, Any]] = {}

    def describe(self) -> str:
        """Return a human-readable description of this module."""
        return "Provides generic terminal command execution and persistent shell session capabilities."

    def run_command(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a one-off shell command."""
        command = input_data.get("command")
        cwd = input_data.get("cwd")

        if not command:
            return {"status": "FAILED", "error": "No command provided for execution."}

        if cwd:
            cwd = os.path.abspath(cwd)
        else:
            cwd = os.getcwd()

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=20.0
            )
            return {
                "status": "SUCCESS" if result.returncode == 0 else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired as e:
            return {
                "status": "FAILED",
                "error": "Command execution timed out.",
                "stdout": e.stdout or "",
                "stderr": e.stderr or ""
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": f"Failed to run command: {e}"
            }

    def spawn_session(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Spawn a new persistent terminal session."""
        session_id = str(uuid.uuid4())
        initial_cwd = input_data.get("cwd") or os.getcwd()
        initial_cwd = os.path.abspath(initial_cwd)

        # Copy current environment
        session_env = dict(os.environ)

        self._sessions[session_id] = {
            "cwd": initial_cwd,
            "env": session_env
        }

        return {
            "status": "SUCCESS",
            "session_id": session_id,
            "cwd": initial_cwd
        }

    def execute_session_command(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a command within a persistent terminal session."""
        session_id = input_data.get("session_id")
        command = input_data.get("command")

        if not session_id or session_id not in self._sessions:
            return {"status": "FAILED", "error": f"Invalid or missing session_id: {session_id}"}

        if not command:
            return {"status": "FAILED", "error": "No command provided for execution."}

        session = self._sessions[session_id]
        cwd = session["cwd"]
        env = session["env"]

        # Intercept directory change command: 'cd path'
        cmd_stripped = command.strip()
        if cmd_stripped.startswith("cd "):
            target_dir = cmd_stripped[3:].strip()
            resolved_dir = os.path.abspath(os.path.join(cwd, target_dir))
            if os.path.exists(resolved_dir) and os.path.isdir(resolved_dir):
                session["cwd"] = resolved_dir
                return {
                    "status": "SUCCESS",
                    "stdout": f"Directory changed to {resolved_dir}",
                    "stderr": "",
                    "exit_code": 0,
                    "cwd": resolved_dir
                }
            else:
                return {
                    "status": "FAILED",
                    "error": f"cd: no such file or directory: {target_dir}",
                    "exit_code": 1
                }

        # Intercept environment exports: 'export VAR=val'
        if cmd_stripped.startswith("export "):
            export_part = cmd_stripped[7:].strip()
            if "=" in export_part:
                var_name, var_val = export_part.split("=", 1)
                var_name = var_name.strip()
                var_val = var_val.strip().strip('"').strip("'")
                env[var_name] = var_val
                return {
                    "status": "SUCCESS",
                    "stdout": f"Exported environment variable: {var_name}={var_val}",
                    "stderr": "",
                    "exit_code": 0
                }

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=20.0
            )
            return {
                "status": "SUCCESS" if result.returncode == 0 else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "cwd": cwd
            }
        except subprocess.TimeoutExpired as e:
            return {
                "status": "FAILED",
                "error": "Session command timed out.",
                "stdout": e.stdout or "",
                "stderr": e.stderr or "",
                "cwd": cwd
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": f"Failed to run session command: {e}",
                "cwd": cwd
            }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        if capability == "run_command":
            return self.run_command(context.input)
        elif capability == "spawn_session":
            return self.spawn_session(context.input)
        elif capability == "execute_session_command":
            return self.execute_session_command(context.input)
        else:
            raise NotImplementedError(f"Capability {capability} not supported by Terminal Module.")
