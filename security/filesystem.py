"""
Filesystem Isolation for Realtimex.

Checks file operations path safety based on the FilesystemPolicy and workspace rules.
"""

from __future__ import annotations

import os
from typing import Optional

from security.policies import FilesystemPolicy


class FilesystemIsolator:
    """Enforces directory restrictions and path isolation for file reads and writes."""

    def __init__(
        self,
        policy: str = FilesystemPolicy.WORKSPACE_ONLY,
        workspace_dir: Optional[str] = None,
        approved_dirs: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize FilesystemIsolator.
        
        Args:
            policy: FilesystemPolicy code
            workspace_dir: Root workspace path for WORKSPACE_ONLY checks
            approved_dirs: List of directory paths allowed for APPROVED_DIRECTORIES checks
        """
        self.policy = policy
        self.workspace_dir = os.path.abspath(workspace_dir) if workspace_dir else None
        self.approved_dirs = [os.path.abspath(d) for d in (approved_dirs or [])]

    def is_path_allowed(self, path: str, write: bool = False) -> bool:
        """
        Check if the path is permitted under the active policy.
        
        Args:
            path: Target file/directory path to check
            write: True if performing a write operation, False if read
            
        Returns:
            True if permitted, False otherwise
        """
        if self.policy == FilesystemPolicy.NO_ACCESS:
            return False

        abs_path = os.path.abspath(path)

        # READ_ONLY policy prevents any write operations
        if self.policy == FilesystemPolicy.READ_ONLY and write:
            return False

        if self.policy == FilesystemPolicy.WORKSPACE_ONLY:
            if not self.workspace_dir:
                return False
            try:
                # Check for path containment and prevent path traversal
                common = os.path.commonpath([self.workspace_dir, abs_path])
                return common == self.workspace_dir
            except ValueError:
                return False

        if self.policy == FilesystemPolicy.APPROVED_DIRECTORIES:
            for app_dir in self.approved_dirs:
                try:
                    common = os.path.commonpath([app_dir, abs_path])
                    if common == app_dir:
                        # For READ_ONLY checks inside approved directories, reject writing
                        if self.policy == FilesystemPolicy.READ_ONLY and write:
                            return False
                        return True
                except ValueError:
                    continue
            return False

        # READ_WRITE allows all (except if write is prohibited under some base rule)
        return True
