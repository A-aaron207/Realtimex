"""
Process Isolation for Realtimex.

Inspects system command execution and process spawning limits based on ProcessPolicy.
"""

from __future__ import annotations

import os
from typing import Optional

from security.policies import ProcessPolicy


class ProcessIsolator:
    """Enforces execution boundaries preventing unauthorized shell execution and process injection."""

    def __init__(
        self,
        policy: str = ProcessPolicy.NO_SPAWN,
        approved_commands: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize ProcessIsolator.
        
        Args:
            policy: ProcessPolicy code
            approved_commands: Whitelist of allowed executable names or command prefixes
        """
        self.policy = policy
        self.approved_commands = approved_commands or []

    def is_process_spawn_allowed(self, command_line: str) -> bool:
        """
        Check if spawning the specified command line is permitted by the policy.
        
        Args:
            command_line: Command shell string to execute
            
        Returns:
            True if permitted, False otherwise
        """
        if self.policy == ProcessPolicy.ALLOW_ALL:
            return True

        if self.policy == ProcessPolicy.NO_SPAWN:
            return False

        if self.policy == ProcessPolicy.APPROVED_ONLY:
            if not command_line:
                return False
            # Get target executable binary name
            executable = command_line.split()[0]
            basename = os.path.basename(executable)
            
            return (executable in self.approved_commands) or (basename in self.approved_commands)

        return False
