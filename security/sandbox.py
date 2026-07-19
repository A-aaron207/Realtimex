"""
Sandbox and SandboxManager for Realtimex.

Coordinates security context policies with filesystem, network, and process isolators.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Optional

from security.policies import SecurityContext, SandboxLevel, DEFAULT_LEVEL_POLICIES
from security.filesystem import FilesystemIsolator
from security.network import NetworkIsolator
from security.processes import ProcessIsolator
from security.exceptions import SandboxError


class Sandbox:
    """Represents an isolated sandboxed execution environment."""

    def __init__(
        self,
        sandbox_id: str,
        context: SecurityContext,
        fs_isolator: FilesystemIsolator,
        net_isolator: NetworkIsolator,
        proc_isolator: ProcessIsolator,
    ) -> None:
        self.sandbox_id = sandbox_id
        self.context = context
        self.fs = fs_isolator
        self.net = net_isolator
        self.proc = proc_isolator


class SandboxManager:
    """Responsible for creating, tracking, and destroying execution sandboxes."""

    def __init__(self, event_bus: Any = None) -> None:
        self.bus = event_bus
        self._sandboxes: dict[str, Sandbox] = {}
        self._lock = threading.RLock()

    def create_sandbox(
        self,
        context: SecurityContext,
        workspace_dir: Optional[str] = None,
        approved_dirs: Optional[list[str]] = None,
        approved_domains: Optional[list[str]] = None,
        approved_commands: Optional[list[str]] = None,
    ) -> Sandbox:
        """
        Instantiate an isolated Sandbox wrapper for a SecurityContext.
        
        Args:
            context: SecurityContext defining limits and level
            workspace_dir: Directory path for WORKSPACE_ONLY checks
            approved_dirs: Directory paths allowed under APPROVED_DIRECTORIES
            approved_domains: Domains allowed under APPROVED_DOMAINS
            approved_commands: Commands allowed under APPROVED_ONLY
            
        Returns:
            Sandbox object containing isolators
        """
        with self._lock:
            sandbox_id = str(uuid.uuid4())
            level_policy = DEFAULT_LEVEL_POLICIES.get(context.sandbox_level)
            
            if not level_policy:
                raise SandboxError(f"Unsupported sandbox level: {context.sandbox_level}")

            # Instantiate isolators
            fs = FilesystemIsolator(
                policy=level_policy["fs"],
                workspace_dir=workspace_dir,
                approved_dirs=approved_dirs,
            )
            net = NetworkIsolator(
                policy=level_policy["net"],
                approved_domains=approved_domains,
            )
            proc = ProcessIsolator(
                policy=level_policy["proc"],
                approved_commands=approved_commands,
            )

            sandbox = Sandbox(sandbox_id, context, fs, net, proc)
            self._sandboxes[sandbox_id] = sandbox

            # Emit SandboxCreated event
            self._emit_sandbox_event("SandboxCreated", sandbox_id, context)
            
            return sandbox

    def destroy_sandbox(self, sandbox_id: str) -> None:
        """Destroy sandbox boundaries and remove from active tracking."""
        with self._lock:
            if sandbox_id not in self._sandboxes:
                raise SandboxError(f"Sandbox '{sandbox_id}' not found.")
            sandbox = self._sandboxes.pop(sandbox_id)
            
            # Emit SandboxDestroyed event
            self._emit_sandbox_event("SandboxDestroyed", sandbox_id, sandbox.context)

    def get_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        """Fetch active sandbox wrapper."""
        with self._lock:
            return self._sandboxes.get(sandbox_id)

    def _emit_sandbox_event(self, event_type: str, sandbox_id: str, context: SecurityContext) -> None:
        """Emit sandbox lifecycle event via Event Bus."""
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name=event_type,
                        source="security.sandbox",
                        payload={
                            "sandbox_id": sandbox_id,
                            "task_id": context.task_id,
                            "module_id": context.module_id,
                            "sandbox_level": context.sandbox_level,
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass
