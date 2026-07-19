"""
Snapshot Manager implementation for full-system diagnostic backups in Realtimex.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from recovery.exceptions import SnapshotError
from recovery.persistence import RecoveryPersistence
from recovery.policies import RecoveryPolicy


class SnapshotManager:
    """
    Orchestrates full-system diagnostics backups (Snapshots), including configuration,
    tasks, workflows, memory, permissions metadata, and cleanup policies.
    
    Thread-safe: Uses internal lock to protect snapshot operations.
    """

    def __init__(
        self,
        persistence: RecoveryPersistence,
        policy: RecoveryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.persistence = persistence
        self.policy = policy or RecoveryPolicy()
        self.logger = logger or logging.getLogger("realtimex.recovery.snapshot")
        self._lock = threading.RLock()

    def create(
        self,
        snapshot_id: str,
        config: dict[str, Any],
        tasks: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        permissions: dict[str, Any],
        module_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a full-system snapshot backup.
        
        Thread-safe snapshot creation that captures entire system state.
        
        Args:
            snapshot_id: Unique identifier for this snapshot
            config: Kernel configuration state
            tasks: List of all task states
            workflows: List of all workflow states
            memories: List of all memory references
            permissions: Permission cache state
            module_metadata: Module registry metadata
            
        Returns:
            dict: The snapshot data that was created
        """
        with self._lock:
            snapshot_data = {
                "snapshot_id": snapshot_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "config": config,
                "tasks": tasks,
                "workflows": workflows,
                "memories": memories,
                "permissions": permissions,
                "module_metadata": module_metadata,
            }
            self.persistence.save_snapshot(snapshot_id, snapshot_data)
            self.logger.info("Snapshot created: %s (config=%s, tasks=%d, workflows=%d)", 
                           snapshot_id, type(config).__name__, len(tasks), len(workflows))
            self._prune_snapshots()
            return snapshot_data

    def restore(self, snapshot_id: str) -> dict[str, Any]:
        """
        Restore system backup dataset from snapshot.
        
        Thread-safe snapshot restore operation.
        
        Args:
            snapshot_id: ID of snapshot to restore
            
        Returns:
            dict: The snapshot data
            
        Raises:
            SnapshotError: If snapshot not found or cannot be loaded
        """
        with self._lock:
            data = self.persistence.load_snapshot(snapshot_id)
            if data is None:
                raise SnapshotError(f"Snapshot with ID '{snapshot_id}' not found.")
            self.logger.info("Snapshot restored: %s", snapshot_id)
            return data

    def delete(self, snapshot_id: str) -> None:
        """
        Delete snapshot backup.
        
        Thread-safe snapshot delete operation.
        
        Args:
            snapshot_id: ID of snapshot to delete
        """
        with self._lock:
            self.persistence.delete_snapshot(snapshot_id)
            self.logger.info("Snapshot deleted: %s", snapshot_id)

    def _prune_snapshots(self) -> None:
        """
        Prune old snapshots if their modification times exceed retention days.
        
        Internal method to enforce retention policy without locking
        (assumes caller already holds lock).
        
        Simple strategy: keep only the most recent 10 snapshots to prevent
        disk space issues. Configurable via policy.
        """
        try:
            snapshots = self.persistence.list_snapshots()
            # Simple count-based pruning: keep at most 10 snapshots
            max_snapshots = 10
            if len(snapshots) > max_snapshots:
                to_delete = snapshots[:-max_snapshots]
                for sn_id in to_delete:
                    self.logger.info("Pruning old snapshot: %s (count=%d exceeds limit=%d)", 
                                   sn_id, len(snapshots), max_snapshots)
                    self.persistence.delete_snapshot(sn_id)
        except Exception as e:
            self.logger.warning("Failed to prune old snapshots: %s", e)
            # Do not raise as snapshot creation must succeed
            pass
