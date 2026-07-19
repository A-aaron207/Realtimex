"""
Policy Versioning Manager for Realtimex.

Coordinates multiple policy versions, rollback, and archival states.
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from policy.exceptions import PolicyVersionError


class PolicyVersionManager:
    """Manages active, historic, and archived version states for loaded policies."""

    def __init__(self) -> None:
        # policy_id -> {version_str -> policy_dict}
        self._history: dict[str, dict[str, dict[str, Any]]] = {}
        # policy_id -> active_version_str
        self._active_versions: dict[str, str] = {}
        # policy_id -> [archived_versions]
        self._archived_versions: dict[str, list[str]] = {}
        self._lock = threading.RLock()

    def add_version(self, policy: dict[str, Any]) -> None:
        """Register a new policy version in the historical record."""
        with self._lock:
            pid = policy["policy_id"]
            ver = policy["version"]

            if pid not in self._history:
                self._history[pid] = {}
                self._archived_versions[pid] = []

            self._history[pid][ver] = policy
            
            # Set the newly added version as the active one
            self._active_versions[pid] = ver

    def activate_version(self, policy_id: str, version: str) -> None:
        """Set a historical version as the active policy version."""
        with self._lock:
            if policy_id not in self._history or version not in self._history[policy_id]:
                raise PolicyVersionError(f"Policy '{policy_id}' version '{version}' not found.")
            
            if version in self._archived_versions.get(policy_id, []):
                raise PolicyVersionError(f"Cannot activate archived version '{version}' for policy '{policy_id}'.")

            self._active_versions[policy_id] = version

    def rollback(self, policy_id: str) -> str:
        """
        Rollback policy to the previous lexicographical version.
        
        Returns:
            The version string rolled back to
        """
        with self._lock:
            if policy_id not in self._history:
                raise PolicyVersionError(f"No history found for policy '{policy_id}'.")

            versions = sorted(list(self._history[policy_id].keys()))
            if len(versions) < 2:
                raise PolicyVersionError(f"No older version exists to rollback to for policy '{policy_id}'.")

            current_active = self._active_versions.get(policy_id)
            if current_active in versions:
                idx = versions.index(current_active)
                if idx > 0:
                    prev_version = versions[idx - 1]
                else:
                    prev_version = versions[-1]  # Wrap around
            else:
                prev_version = versions[-2]

            self._active_versions[policy_id] = prev_version
            return prev_version

    def archive_version(self, policy_id: str, version: str) -> None:
        """Archive a policy version, preventing it from being activated."""
        with self._lock:
            if policy_id not in self._history or version not in self._history[policy_id]:
                raise PolicyVersionError(f"Policy '{policy_id}' version '{version}' not found.")

            if self._active_versions.get(policy_id) == version:
                raise PolicyVersionError(f"Cannot archive the active version '{version}' for policy '{policy_id}'.")

            if version not in self._archived_versions[policy_id]:
                self._archived_versions[policy_id].append(version)

    def get_active(self, policy_id: str) -> Optional[dict[str, Any]]:
        """Retrieve active policy definition dictionary."""
        with self._lock:
            active_ver = self._active_versions.get(policy_id)
            if not active_ver or policy_id not in self._history:
                return None
            return self._history[policy_id].get(active_ver)

    def list_versions(self, policy_id: str) -> list[str]:
        """List all registered version strings for a policy."""
        with self._lock:
            if policy_id not in self._history:
                return []
            return sorted(list(self._history[policy_id].keys()))
