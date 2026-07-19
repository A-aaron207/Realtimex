"""
Rule Engine implementation for evaluating security requests in the Realtimex Permission System.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from permissions.decision import PermissionDecision
from permissions.request import PermissionRequest


class RuleEngine:
    """
    Evaluates permission requests against structural, pattern-matching safety rules.
    Highly configurable to restrict commands, environment edits, and filesystem actions.
    """

    def __init__(
        self,
        deny_sudo: bool = True,
        allow_terminal_exec: bool = False,
        allow_browser_automation: bool = False,
        allow_clipboard: bool = False,
        allow_process_management: bool = False,
        allowed_read_paths: list[str] | None = None,
        allowed_write_paths: list[str] | None = None,
        protected_delete_paths: list[str] | None = None,
        allowed_network_hosts: list[str] | None = None,
    ) -> None:
        self.deny_sudo = deny_sudo
        self.allow_terminal_exec = allow_terminal_exec
        self.allow_browser_automation = allow_browser_automation
        self.allow_clipboard = allow_clipboard
        self.allow_process_management = allow_process_management

        # Default path rules (e.g., matching workspace directories)
        self.allowed_read_paths = allowed_read_paths or ["*"]
        self.allowed_write_paths = allowed_write_paths or []
        self.protected_delete_paths = protected_delete_paths or [
            "/etc/*",
            "/var/*",
            "/usr/*",
            "/bin/*",
            "/sbin/*",
        ]
        self.allowed_network_hosts = allowed_network_hosts or []

    def evaluate(self, request: PermissionRequest) -> PermissionDecision | None:
        """
        Evaluate the request against registered rules.
        Returns a PermissionDecision if a rule explicitly approves/denies,
        or None to defer to subsequent stages (Cognitive/Policy/User).
        """
        action = request.action.lower()
        target = request.target.strip()

        # 1. Sudo operations check
        if action == "sudo" or target.startswith("sudo ") or "sudo" in request.metadata.get("tags", []):
            if self.deny_sudo:
                return PermissionDecision(
                    approved=False,
                    reason="Sudo command execution is strictly denied by Rule Engine safety policies.",
                    reviewer="rule_engine",
                )

        # 2. Terminal execution check
        if action == "terminal_exec":
            if not self.allow_terminal_exec:
                return PermissionDecision(
                    approved=False,
                    reason="Terminal execution is disabled in the current workspace rules.",
                    reviewer="rule_engine",
                )

        # 3. Browser automation check
        if action == "browser_automation":
            if not self.allow_browser_automation:
                return PermissionDecision(
                    approved=False,
                    reason="Browser automation actions are blocked under rules.",
                    reviewer="rule_engine",
                )

        # 4. Clipboard operations
        if action == "clipboard":
            if not self.allow_clipboard:
                return PermissionDecision(
                    approved=False,
                    reason="System clipboard access is disabled under rules.",
                    reviewer="rule_engine",
                )

        # 5. Process management (kill, start, etc.)
        if action == "process_management":
            if not self.allow_process_management:
                return PermissionDecision(
                    approved=False,
                    reason="External OS process management is restricted.",
                    reviewer="rule_engine",
                )

        # 6. File deletion check
        if action == "file_delete":
            for pattern in self.protected_delete_paths:
                if fnmatch.fnmatch(target, pattern):
                    return PermissionDecision(
                        approved=False,
                        reason=f"File deletion targeted protected system path: '{target}'.",
                        reviewer="rule_engine",
                    )

        # 7. File write check
        if action == "file_write":
            allowed = False
            for pattern in self.allowed_write_paths:
                if fnmatch.fnmatch(target, pattern):
                    allowed = True
                    break
            if not allowed and self.allowed_write_paths:
                return PermissionDecision(
                    approved=False,
                    reason=f"Write operations are restricted to approved paths. Path '{target}' is not approved.",
                    reviewer="rule_engine",
                )

        # 8. File read check
        if action == "file_read":
            allowed = False
            for pattern in self.allowed_read_paths:
                if fnmatch.fnmatch(target, pattern):
                    allowed = True
                    break
            if not allowed:
                return PermissionDecision(
                    approved=False,
                    reason=f"Read operations are restricted. Path '{target}' is not in allowed paths.",
                    reviewer="rule_engine",
                )

        # 9. Network access check
        if action == "network_access":
            allowed = False
            for pattern in self.allowed_network_hosts:
                if fnmatch.fnmatch(target, pattern):
                    allowed = True
                    break
            if not allowed and self.allowed_network_hosts:
                return PermissionDecision(
                    approved=False,
                    reason=f"Network access to host '{target}' is not whitelisted.",
                    reviewer="rule_engine",
                )

        # Defer decision to next pipeline stages
        return None
