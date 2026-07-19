"""
Security Policies and Context for Realtimex.

Defines Sandbox Levels, Filesystem, Network, Process Policies, and the SecurityContext.
"""

from __future__ import annotations

from typing import Any, Optional


class SandboxLevel:
    """Security Sandbox levels determining extension constraints."""
    LEVEL_0 = "LEVEL_0"  # Kernel Internal (no limits)
    LEVEL_1 = "LEVEL_1"  # Trusted Modules (minor restrictions)
    LEVEL_2 = "LEVEL_2"  # Standard Modules (workspace only, approved network)
    LEVEL_3 = "LEVEL_3"  # Untrusted Modules (no network, sandbox workspace only)
    LEVEL_4 = "LEVEL_4"  # Restricted Sandbox (extremely isolated, no OS access)


class FilesystemPolicy:
    """Filesystem access policy types."""
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"
    WORKSPACE_ONLY = "WORKSPACE_ONLY"
    APPROVED_DIRECTORIES = "APPROVED_DIRECTORIES"
    NO_ACCESS = "NO_ACCESS"


class NetworkPolicy:
    """Network connection policy types."""
    NO_NETWORK = "NO_NETWORK"
    APPROVED_DOMAINS = "APPROVED_DOMAINS"
    LOCALHOST_ONLY = "LOCALHOST_ONLY"
    FULL_NETWORK = "FULL_NETWORK"


class ProcessPolicy:
    """OS Process spawning policy types."""
    ALLOW_ALL = "ALLOW_ALL"
    APPROVED_ONLY = "APPROVED_ONLY"
    NO_SPAWN = "NO_SPAWN"


class SecurityContext:
    """
    Representation of an execution's security context.
    
    Contains credentials, limits, levels, and capabilities.
    """

    def __init__(
        self,
        task_id: str,
        module_id: str,
        worker_id: str,
        permission_profile: str = "default",
        allowed_capabilities: Optional[list[str]] = None,
        resource_limits: Optional[dict[str, Any]] = None,
        sandbox_level: str = SandboxLevel.LEVEL_2,
    ) -> None:
        self.task_id = task_id
        self.module_id = module_id
        self.worker_id = worker_id
        self.permission_profile = permission_profile
        self.allowed_capabilities = allowed_capabilities or []
        self.resource_limits = resource_limits or {}
        self.sandbox_level = sandbox_level

    def to_dict(self) -> dict[str, Any]:
        """Convert security context to dictionary format."""
        return {
            "task_id": self.task_id,
            "module_id": self.module_id,
            "worker_id": self.worker_id,
            "permission_profile": self.permission_profile,
            "allowed_capabilities": self.allowed_capabilities,
            "resource_limits": self.resource_limits,
            "sandbox_level": self.sandbox_level,
        }


# Default policy settings mapped by SandboxLevel
DEFAULT_LEVEL_POLICIES = {
    SandboxLevel.LEVEL_0: {
        "fs": FilesystemPolicy.READ_WRITE,
        "net": NetworkPolicy.FULL_NETWORK,
        "proc": ProcessPolicy.ALLOW_ALL,
        "resource_limits": {
            "max_cpu_percent": 100.0,
            "max_memory_mb": 0.0,  # Unlimited
            "max_duration_sec": 0.0,  # Unlimited
        }
    },
    SandboxLevel.LEVEL_1: {
        "fs": FilesystemPolicy.READ_WRITE,
        "net": NetworkPolicy.APPROVED_DOMAINS,
        "proc": ProcessPolicy.APPROVED_ONLY,
        "resource_limits": {
            "max_cpu_percent": 90.0,
            "max_memory_mb": 4096.0,
            "max_duration_sec": 1800.0,  # 30 mins
        }
    },
    SandboxLevel.LEVEL_2: {
        "fs": FilesystemPolicy.WORKSPACE_ONLY,
        "net": NetworkPolicy.APPROVED_DOMAINS,
        "proc": ProcessPolicy.NO_SPAWN,
        "resource_limits": {
            "max_cpu_percent": 75.0,
            "max_memory_mb": 2048.0,
            "max_duration_sec": 600.0,  # 10 mins
        }
    },
    SandboxLevel.LEVEL_3: {
        "fs": FilesystemPolicy.WORKSPACE_ONLY,
        "net": NetworkPolicy.NO_NETWORK,
        "proc": ProcessPolicy.NO_SPAWN,
        "resource_limits": {
            "max_cpu_percent": 50.0,
            "max_memory_mb": 1024.0,
            "max_duration_sec": 300.0,  # 5 mins
        }
    },
    SandboxLevel.LEVEL_4: {
        "fs": FilesystemPolicy.NO_ACCESS,
        "net": NetworkPolicy.NO_NETWORK,
        "proc": ProcessPolicy.NO_SPAWN,
        "resource_limits": {
            "max_cpu_percent": 25.0,
            "max_memory_mb": 512.0,
            "max_duration_sec": 60.0,  # 1 min
        }
    }
}
