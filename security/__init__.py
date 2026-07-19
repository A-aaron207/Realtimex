"""
Realtimex Security & Sandboxing System.

Enforces execution policies, directory workspace confinement, network whitelists,
process spawning boundaries, resource limit monitoring, and append-only audits.
"""

from __future__ import annotations

from security.manager import SecurityManager
from security.policies import (
    SecurityContext,
    SandboxLevel,
    FilesystemPolicy,
    NetworkPolicy,
    ProcessPolicy,
    DEFAULT_LEVEL_POLICIES,
)
from security.sandbox import Sandbox
from security.capabilities import Capabilities

from security.exceptions import (
    SecurityError,
    SandboxError,
    SandboxViolationError,
    ResourceLimitExceededError,
    PolicyValidationError,
)

__all__ = [
    # Manager
    "SecurityManager",
    
    # Models & Policies
    "SecurityContext",
    "SandboxLevel",
    "FilesystemPolicy",
    "NetworkPolicy",
    "ProcessPolicy",
    "DEFAULT_LEVEL_POLICIES",
    
    # Sandbox
    "Sandbox",
    "Capabilities",
    
    # Exceptions
    "SecurityError",
    "SandboxError",
    "SandboxViolationError",
    "ResourceLimitExceededError",
    "PolicyValidationError",
]
