"""
Checkpoint Manager implementation for saving, loading, and pruning checkpoints.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from recovery.exceptions import CheckpointError
from recovery.persistence import RecoveryPersistence
from recovery.policies import RecoveryPolicy


class CheckpointManager:
    """
    Manages automated and explicit checkpoint operations, including loading, saving,
    and pruning old files according to retention limits.
    
    Thread-safe: Uses internal lock to protect checkpoint operations.
    """

    def __init__(
        self,
        persistence: RecoveryPersistence,
        policy: RecoveryPolicy | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.persistence = persistence
        self.policy = policy or RecoveryPolicy()
        self.logger = logger or logging.getLogger("realtimex.recovery.checkpoint")
        self._lock = threading.RLock()

    def save(self, checkpoint_id: str, checkpoint_data: dict[str, Any]) -> None:
        """
        Save a new checkpoint and prune oldest checkpoints if limits are exceeded.
        
        Thread-safe checkpoint save operation.
        
        Args:
            checkpoint_id: Unique identifier for this checkpoint
            checkpoint_data: Checkpoint state dictionary
        """
        with self._lock:
            self.persistence.save_checkpoint(checkpoint_id, checkpoint_data)
            self.logger.info("Checkpoint saved: %s", checkpoint_id)
            self._prune_checkpoints()

    def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        Load checkpoint data by ID.
        
        Thread-safe checkpoint load operation.
        
        Args:
            checkpoint_id: ID of checkpoint to load
            
        Returns:
            Checkpoint data dictionary or None if not found
        """
        with self._lock:
            data = self.persistence.load_checkpoint(checkpoint_id)
            if data:
                self.logger.debug("Checkpoint loaded: %s", checkpoint_id)
            else:
                self.logger.warning("Checkpoint not found: %s", checkpoint_id)
            return data

    def delete(self, checkpoint_id: str) -> None:
        """
        Delete checkpoint by ID.
        
        Thread-safe checkpoint delete operation.
        
        Args:
            checkpoint_id: ID of checkpoint to delete
        """
        with self._lock:
            self.persistence.delete_checkpoint(checkpoint_id)
            self.logger.info("Checkpoint deleted: %s", checkpoint_id)

    def _prune_checkpoints(self) -> None:
        """
        Prune older checkpoints if total count exceeds policy limits.
        
        Internal method to enforce retention policy without locking
        (assumes caller already holds lock).
        """
        try:
            checkpoints = self.persistence.list_checkpoints()
            limit = self.policy.max_retained_checkpoints
            if len(checkpoints) > limit:
                to_delete = checkpoints[:-limit]  # list_checkpoints is sorted oldest first
                for cp_id in to_delete:
                    self.logger.info("Pruning old checkpoint: %s (count=%d exceeds limit=%d)", 
                                   cp_id, len(checkpoints), limit)
                    self.persistence.delete_checkpoint(cp_id)
        except Exception as e:
            self.logger.warning("Failed to prune old checkpoints: %s", e)
            # Do not raise as saving must succeed
            pass
