"""
Security Manager for Realtimex.

The central orchestration manager for the Security & Sandboxing System.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from security.policies import SecurityContext, SandboxLevel
from security.capabilities import CapabilityEnforcer
from security.sandbox import Sandbox, SandboxManager
from security.resources import ResourceMonitor
from security.audit import SecurityAuditor
from security.enforcement import SafetyEnforcer
from security.exceptions import SecurityError


class SecurityManager:
    """
    Central engine orchestrating Contexts, Sandboxes, Capabilities, Isolators, and Auditing.
    
    Exposes the public contract:
    - create_context()
    - verify()
    - enforce()
    - create_sandbox()
    - destroy_sandbox()
    - audit()
    - status()
    """

    def __init__(
        self,
        event_bus: Any = None,
        audit_filepath: Optional[str] = None,
    ) -> None:
        """
        Initialize SecurityManager.
        
        Args:
            event_bus: Optional Event Bus for event-driven updates
            audit_filepath: Optional filepath to write append-only audit trail
        """
        self.bus = event_bus
        self.auditor = SecurityAuditor(event_bus=event_bus, filepath=audit_filepath)
        self.enforcer = SafetyEnforcer(auditor=self.auditor, event_bus=event_bus)
        self.sandbox_mgr = SandboxManager(event_bus=event_bus)
        self.resource_monitor = ResourceMonitor()
        self.cap_enforcer = CapabilityEnforcer()
        self._lock = threading.RLock()

    # --- Public API Contract ---

    def create_context(
        self,
        task_id: str,
        module_id: str,
        worker_id: str,
        permission_profile: str = "default",
        allowed_capabilities: Optional[list[str]] = None,
        resource_limits: Optional[dict[str, Any]] = None,
        sandbox_level: str = SandboxLevel.LEVEL_2,
    ) -> SecurityContext:
        """Create a new security context defining execution parameters."""
        return SecurityContext(
            task_id=task_id,
            module_id=module_id,
            worker_id=worker_id,
            permission_profile=permission_profile,
            allowed_capabilities=allowed_capabilities,
            resource_limits=resource_limits,
            sandbox_level=sandbox_level,
        )

    def verify(self, context: SecurityContext, capability: str) -> bool:
        """
        Verify if context permits execution of the capability, logging the audit.
        
        Args:
            context: SecurityContext to verify
            capability: Capability token description
            
        Returns:
            True if allowed, False otherwise
        """
        allowed = self.cap_enforcer.verify_capability(context, capability)
        status_label = "ALLOWED" if allowed else "DENIED"
        
        # Log to auditor
        self.auditor.record(
            event_type="PermissionDecision",
            status=status_label,
            details={
                "task_id": context.task_id,
                "module_id": context.module_id,
                "capability": capability,
            },
        )

        # Emit PermissionVerified event
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name="PermissionVerified",
                        source="security.manager",
                        payload={
                            "task_id": context.task_id,
                            "capability": capability,
                            "decision": status_label,
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass

        return allowed

    def enforce(
        self,
        sandbox_id: str,
        operation_type: str,
        target: str,
        **kwargs: Any,
    ) -> None:
        """
        Enforce isolation constraints on an active sandbox session.
        
        Args:
            sandbox_id: UUID of active sandbox
            operation_type: 'filesystem_read', 'filesystem_write', 'network_connect', 'process_spawn'
            target: Path, URL, or command string
            
        Raises:
            SecurityError: If sandbox not found
            SandboxViolationError: If boundary check fails
        """
        sandbox = self.sandbox_mgr.get_sandbox(sandbox_id)
        if not sandbox:
            raise SecurityError(f"Sandbox session '{sandbox_id}' not found.")

        if operation_type == "filesystem_read":
            self.enforcer.enforce_filesystem(sandbox, target, write=False)
        elif operation_type == "filesystem_write":
            self.enforcer.enforce_filesystem(sandbox, target, write=True)
        elif operation_type == "network_connect":
            self.enforcer.enforce_network(sandbox, target)
        elif operation_type == "process_spawn":
            self.enforcer.enforce_process(sandbox, target)
        else:
            raise SecurityError(f"Unknown operation type for enforcement: {operation_type}")

    def create_sandbox(
        self,
        context: SecurityContext,
        workspace_dir: Optional[str] = None,
        approved_dirs: Optional[list[str]] = None,
        approved_domains: Optional[list[str]] = None,
        approved_commands: Optional[list[str]] = None,
    ) -> Sandbox:
        """Instantiate sandbox boundary for security context."""
        return self.sandbox_mgr.create_sandbox(
            context=context,
            workspace_dir=workspace_dir,
            approved_dirs=approved_dirs,
            approved_domains=approved_domains,
            approved_commands=approved_commands,
        )

    def destroy_sandbox(self, sandbox_id: str) -> None:
        """Tear down active sandbox session."""
        self.sandbox_mgr.destroy_sandbox(sandbox_id)

    def audit(self, event_type: str, status: str, details: dict[str, Any]) -> None:
        """Record manual security audit entry."""
        self.auditor.record(event_type, status, details)

    def status(self, sandbox_id: Optional[str] = None) -> dict[str, Any]:
        """
        Get diagnostics status info.
        
        Args:
            sandbox_id: Optional sandbox UUID to inspect
            
        Returns:
            Status summary dictionary
        """
        with self._lock:
            stats = {
                "active_sandboxes": len(self.sandbox_mgr._sandboxes),
                "audit_records_count": len(self.auditor.get_records()),
            }
            if sandbox_id:
                sandbox = self.sandbox_mgr.get_sandbox(sandbox_id)
                if sandbox:
                    stats["sandbox"] = {
                        "sandbox_id": sandbox.sandbox_id,
                        "task_id": sandbox.context.task_id,
                        "sandbox_level": sandbox.context.sandbox_level,
                        "fs_policy": sandbox.fs.policy,
                        "net_policy": sandbox.net.policy,
                        "proc_policy": sandbox.proc.policy,
                    }
            return stats
