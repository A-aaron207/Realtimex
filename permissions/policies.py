"""
Permission policies and policy evaluator for the Realtimex Permission System.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any

from permissions.decision import PermissionDecision
from permissions.request import PermissionRequest


@dataclass
class PermissionPolicy:
    """
    Externally configurable rules enforcing high-level security mandates.
    """
    require_sudo_user_confirmation: bool = True
    read_only_mode: bool = False
    allowed_folders: list[str] = field(default_factory=lambda: ["*"])
    network_restricted_modules: dict[str, list[str]] = field(default_factory=dict)
    restrict_browser_automation: bool = True


class PolicyEvaluator:
    """
    Evaluates permission requests against the active PermissionPolicy configuration.
    """

    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self.policy = policy or PermissionPolicy()

    def evaluate(self, request: PermissionRequest) -> PermissionDecision | None:
        """
        Evaluate request against policy rules.
        """
        action = request.action.lower()
        target = request.target.strip()
        worker_id = request.worker_id

        # 1. Read-Only Mode enforcement
        if self.policy.read_only_mode:
            if action in ("file_write", "file_delete", "sudo", "terminal_exec"):
                return PermissionDecision(
                    approved=False,
                    reason=f"Action '{action}' is denied because the kernel is operating in read-only mode.",
                    reviewer="policy_evaluator",
                )

        # 2. Folder confinement (allowed folders)
        if action == "file_read":
            allowed = False
            for pattern in self.policy.allowed_folders:
                if fnmatch.fnmatch(target, pattern):
                    allowed = True
                    break
            if not allowed:
                return PermissionDecision(
                    approved=False,
                    reason=f"Policy violation: Read target path '{target}' is outside configured allowed folders.",
                    reviewer="policy_evaluator",
                )

        # 3. Sudo user confirmation flag
        if action == "sudo" or target.startswith("sudo"):
            if self.policy.require_sudo_user_confirmation:
                # Add marker in request metadata indicating explicit user confirmation is needed
                request.metadata["user_confirmation_required"] = True

        # 4. Limit network access for selected modules
        if action == "network_access" and worker_id in self.policy.network_restricted_modules:
            allowed_hosts = self.policy.network_restricted_modules[worker_id]
            allowed = False
            for host_pattern in allowed_hosts:
                if fnmatch.fnmatch(target, host_pattern):
                    allowed = True
                    break
            if not allowed:
                return PermissionDecision(
                    approved=False,
                    reason=f"Policy violation: Network access to '{target}' is restricted for worker '{worker_id}'.",
                    reviewer="policy_evaluator",
                )

        # 5. Restrict browser automation policy
        if action == "browser_automation" and self.policy.restrict_browser_automation:
            return PermissionDecision(
                approved=False,
                reason="Browser automation is restricted by default safety policy.",
                reviewer="policy_evaluator",
            )

        # Defer decision if no policy overrides
        return None
