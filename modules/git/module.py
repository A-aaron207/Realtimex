"""
Git Module entry point.

Provides capabilities for:
- clone_repo
- commit
- branch
- diff
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from loader.module_base import ModuleEntryPoint


def _run_git(args: list[str], cwd: str | None = None, timeout: float = 30.0) -> dict[str, Any]:
    """Run a git command and return a structured result dict."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"status": "FAILED", "error": "Git command timed out.", "exit_code": -1}
    except FileNotFoundError:
        return {"status": "FAILED", "error": "git executable not found.", "exit_code": -1}
    except Exception as e:
        return {"status": "FAILED", "error": str(e), "exit_code": -1}


class Module(ModuleEntryPoint):
    """Entry point for the Git Module."""

    module_id = "git"
    capabilities = ["clone_repo", "commit", "branch", "diff"]

    def describe(self) -> str:
        """Return a human-readable description of this module."""
        return "Provides Git version control operations: clone, commit, branch, and diff."

    def clone_repo(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Clone a remote repository to a local path."""
        url = input_data.get("url")
        destination = input_data.get("destination") or input_data.get("dest")

        if not url:
            return {"status": "FAILED", "error": "No repository URL provided."}

        args = ["clone", url]
        if destination:
            args.append(destination)

        result = _run_git(args, timeout=60.0)
        if result["status"] == "SUCCESS":
            result["cloned_to"] = destination or url.split("/")[-1].replace(".git", "")
        return result

    def commit(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Stage all changes and create a commit in a given repo directory."""
        repo_path = input_data.get("repo_path") or os.getcwd()
        message = input_data.get("message")
        add_all = input_data.get("add_all", True)

        if not message:
            return {"status": "FAILED", "error": "No commit message provided."}

        repo_path = os.path.abspath(repo_path)

        if add_all:
            add_result = _run_git(["add", "-A"], cwd=repo_path)
            if add_result["status"] == "FAILED":
                return add_result

        result = _run_git(["commit", "-m", message], cwd=repo_path)
        return result

    def branch(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Create, switch, delete, or list branches."""
        repo_path = input_data.get("repo_path") or os.getcwd()
        action = input_data.get("action", "list")  # list | create | switch | delete
        branch_name = input_data.get("name")

        repo_path = os.path.abspath(repo_path)

        if action == "list":
            return _run_git(["branch", "--list"], cwd=repo_path)

        if not branch_name:
            return {"status": "FAILED", "error": f"Branch name is required for action '{action}'."}

        if action == "create":
            return _run_git(["checkout", "-b", branch_name], cwd=repo_path)
        elif action == "switch":
            return _run_git(["checkout", branch_name], cwd=repo_path)
        elif action == "delete":
            return _run_git(["branch", "-d", branch_name], cwd=repo_path)
        else:
            return {"status": "FAILED", "error": f"Unknown branch action: '{action}'. Use list|create|switch|delete."}

    def diff(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Return the diff of the working tree or between two refs."""
        repo_path = input_data.get("repo_path") or os.getcwd()
        ref_a = input_data.get("ref_a")
        ref_b = input_data.get("ref_b")
        staged = input_data.get("staged", False)

        repo_path = os.path.abspath(repo_path)

        if ref_a and ref_b:
            args = ["diff", ref_a, ref_b]
        elif staged:
            args = ["diff", "--cached"]
        else:
            args = ["diff"]

        result = _run_git(args, cwd=repo_path)
        result["diff_output"] = result.pop("stdout", "")
        return result

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        if capability == "clone_repo":
            return self.clone_repo(context.input)
        elif capability == "commit":
            return self.commit(context.input)
        elif capability == "branch":
            return self.branch(context.input)
        elif capability == "diff":
            return self.diff(context.input)
        else:
            raise NotImplementedError(f"Capability '{capability}' not supported by Git Module.")
