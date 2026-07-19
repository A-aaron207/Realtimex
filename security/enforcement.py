"""
Safety Enforcer for Realtimex.

Intercepts execution operations and enforces sandbox constraints.
"""

from __future__ import annotations

from typing import Any

from security.sandbox import Sandbox
from security.exceptions import SandboxViolationError


class SafetyEnforcer:
    """Enforcement engine checks path, connection, and shell boundaries, raising errors on violations."""

    def __init__(self, auditor: Any = None, event_bus: Any = None) -> None:
        """
        Initialize SafetyEnforcer.
        
        Args:
            auditor: Optional SecurityAuditor instance to record violations
            event_bus: Optional Event Bus to emit SecurityViolation events
        """
        self.auditor = auditor
        self.bus = event_bus

    def enforce_filesystem(self, sandbox: Sandbox, path: str, write: bool = False) -> None:
        """
        Enforce filesystem boundary rules.
        
        Raises:
            SandboxViolationError: If operation is blocked
        """
        if not sandbox.fs.is_path_allowed(path, write):
            op = "write" if write else "read"
            details = {
                "sandbox_id": sandbox.sandbox_id,
                "task_id": sandbox.context.task_id,
                "operation": f"filesystem_{op}",
                "target": path,
            }
            
            self._handle_violation("filesystem_boundary_violation", details)
            raise SandboxViolationError(f"Sandbox filesystem {op} boundary violation: {path}")

    def enforce_network(self, sandbox: Sandbox, url_or_host: str) -> None:
        """
        Enforce network boundary rules.
        
        Raises:
            SandboxViolationError: If connection is blocked
        """
        if not sandbox.net.is_connection_allowed(url_or_host):
            details = {
                "sandbox_id": sandbox.sandbox_id,
                "task_id": sandbox.context.task_id,
                "operation": "network_connect",
                "target": url_or_host,
            }
            
            self._handle_violation("network_boundary_violation", details)
            raise SandboxViolationError(f"Sandbox network connection boundary violation: {url_or_host}")

    def enforce_process(self, sandbox: Sandbox, command_line: str) -> None:
        """
        Enforce process spawning boundary rules.
        
        Raises:
            SandboxViolationError: If execution is blocked
        """
        if not sandbox.proc.is_process_spawn_allowed(command_line):
            details = {
                "sandbox_id": sandbox.sandbox_id,
                "task_id": sandbox.context.task_id,
                "operation": "process_spawn",
                "target": command_line,
            }
            
            self._handle_violation("process_spawn_violation", details)
            raise SandboxViolationError(f"Sandbox process execution boundary violation: {command_line}")

    def _handle_violation(self, violation_type: str, details: dict[str, Any]) -> None:
        """Log violation in auditor and emit SecurityViolation event."""
        if self.auditor:
            self.auditor.record("SecurityViolation", "VIOLATED", {**details, "violation_type": violation_type})

        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name="SecurityViolation",
                        source="security.enforcement",
                        payload={
                            "violation_type": violation_type,
                            "sandbox_id": details.get("sandbox_id"),
                            "task_id": details.get("task_id"),
                            "operation": details.get("operation"),
                            "target": details.get("target"),
                        },
                        priority=EventPriority.CRITICAL,
                    )
                )
            except Exception:
                pass
