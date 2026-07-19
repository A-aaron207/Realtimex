"""
Capability Enforcer for Realtimex.

Defines and verifies capabilities against the execution security context.
"""

from __future__ import annotations

from security.policies import SecurityContext, SandboxLevel


class Capabilities:
    """Standard capability token constants."""
    FILESYSTEM_READ = "CAP_FILESYSTEM_READ"
    FILESYSTEM_WRITE = "CAP_FILESYSTEM_WRITE"
    NETWORK_CONNECT = "CAP_NETWORK_CONNECT"
    PROCESS_SPAWN = "CAP_PROCESS_SPAWN"
    MODULE_LOAD = "CAP_MODULE_LOAD"
    RECOVERY_SNAPSHOT = "CAP_RECOVERY_SNAPSHOT"
    MODEL_CALL = "CAP_MODEL_CALL"
    MEMORY_READ = "CAP_MEMORY_READ"
    MEMORY_WRITE = "CAP_MEMORY_WRITE"


class CapabilityEnforcer:
    """Verifies if a specific capability request is permitted by the SecurityContext."""

    def verify_capability(self, context: SecurityContext, capability: str) -> bool:
        """
        Verify if the given security context permits execution of the capability.
        
        Args:
            context: SecurityContext of the execution
            capability: Capability token requested
            
        Returns:
            True if permitted, False otherwise
        """
        # LEVEL_0 always allowed
        if context.sandbox_level == SandboxLevel.LEVEL_0:
            return True

        # LEVEL_1 allowed most things except raw OS process spawning (unless explicitly granted)
        if context.sandbox_level == SandboxLevel.LEVEL_1:
            if capability == Capabilities.PROCESS_SPAWN:
                return capability in context.allowed_capabilities
            return True

        # Other levels must explicitly possess the capability token
        return capability in context.allowed_capabilities
