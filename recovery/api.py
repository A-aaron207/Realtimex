"""
API facade for the Realtimex Recovery System.

This module provides a clean, global API for recovery operations.
It uses a singleton pattern to manage a single RecoveryManager instance
that can be accessed throughout the application.

Usage:
    from recovery import api
    
    # Initialize on kernel startup
    api.initialize_api(manager_instance)
    
    # Use recovery functions
    api.recover()
    api.create_checkpoint("cp-1", tasks, workflows, memories)
    status = api.status()
"""

from __future__ import annotations

import logging
from typing import Any

from recovery.manager import RecoveryManager

logger = logging.getLogger("realtimex.recovery.api")

_manager_instance: RecoveryManager | None = None


def get_manager() -> RecoveryManager:
    """
    Get the initialized RecoveryManager instance.
    
    Returns:
        RecoveryManager: The global recovery manager instance
        
    Raises:
        RuntimeError: If manager hasn't been initialized via initialize_api()
    """
    global _manager_instance
    if _manager_instance is None:
        raise RuntimeError("Recovery API has not been initialized. Call initialize_api() first.")
    return _manager_instance


def initialize_api(manager: RecoveryManager) -> None:
    """
    Initialize the global API context with a RecoveryManager instance.
    
    Should be called during kernel initialization before any recovery operations.
    
    Args:
        manager: Initialized RecoveryManager instance to use globally
    """
    global _manager_instance
    _manager_instance = manager
    logger.info("Recovery API initialized with manager instance")


def recover() -> Any:
    """
    Recover the system using the latest checkpoint on disk.
    
    Initiates full system recovery from the most recent checkpoint.
    Returns a detailed recovery report.
    
    Returns:
        RecoveryReport: Comprehensive report of recovery outcomes
        
    Raises:
        RecoveryError: If recovery fails critically
    """
    logger.info("Recovery API: recover() called")
    return get_manager().recover()


def create_checkpoint(
    checkpoint_id: str,
    tasks: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    kernel_metadata: dict[str, Any] | None = None,
    pending_events: list[dict[str, Any]] | None = None,
) -> None:
    """
    Create a checkpoint of the active system state.
    
    Captures current tasks, workflows, and memories for later recovery.
    Old checkpoints are automatically pruned based on retention policy.
    
    Args:
        checkpoint_id: Unique identifier for this checkpoint
        tasks: List of active task states
        workflows: List of active workflow states
        memories: List of memory references
        kernel_metadata: Optional kernel version and config info
        pending_events: Optional queue of unprocessed events
    """
    logger.info("Recovery API: create_checkpoint(%s)", checkpoint_id)
    get_manager().create_checkpoint(
        checkpoint_id=checkpoint_id,
        tasks=tasks,
        workflows=workflows,
        memories=memories,
        kernel_metadata=kernel_metadata,
        pending_events=pending_events,
    )


def restore_checkpoint(checkpoint_id: str) -> Any:
    """
    Load and restore system state from a specific checkpoint.
    
    Restores a particular checkpoint, re-injecting all valid state
    back into kernel subsystems via registered callbacks.
    
    Args:
        checkpoint_id: ID of checkpoint to restore
        
    Returns:
        RecoveryReport: Report of what was restored
        
    Raises:
        CheckpointError: If checkpoint not found or corrupted
    """
    logger.info("Recovery API: restore_checkpoint(%s)", checkpoint_id)
    return get_manager().restore_checkpoint(checkpoint_id)


def create_snapshot(
    snapshot_id: str,
    config: dict[str, Any],
    tasks: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    permissions: dict[str, Any],
    module_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate a diagnostic backup snapshot of the entire system.
    
    Creates a full system backup including configuration, all state,
    and metadata for diagnostics and disaster recovery.
    
    Args:
        snapshot_id: Unique identifier for this snapshot
        config: Current kernel configuration
        tasks: All task states
        workflows: All workflow states
        memories: All memory references
        permissions: Permission cache state
        module_metadata: Module registry metadata
        
    Returns:
        dict: The snapshot data that was created
    """
    logger.info("Recovery API: create_snapshot(%s)", snapshot_id)
    return get_manager().create_snapshot(
        snapshot_id=snapshot_id,
        config=config,
        tasks=tasks,
        workflows=workflows,
        memories=memories,
        permissions=permissions,
        module_metadata=module_metadata,
    )


def restore_snapshot(snapshot_id: str) -> dict[str, Any]:
    """
    Restore the system dataset from a snapshot backup file.
    
    Loads and returns complete system state from a diagnostic snapshot.
    
    Args:
        snapshot_id: ID of snapshot to restore
        
    Returns:
        dict: Complete system state from snapshot
        
    Raises:
        SnapshotError: If snapshot not found or corrupted
    """
    logger.info("Recovery API: restore_snapshot(%s)", snapshot_id)
    return get_manager().restore_snapshot(snapshot_id)


def validate(checkpoint_data: dict[str, Any]) -> dict[str, Any]:
    """
    Run schema validation checks on checkpoint data.
    
    Validates structural integrity without performing full recovery.
    Useful for diagnostics and pre-recovery checks.
    
    Args:
        checkpoint_data: Checkpoint data to validate
        
    Returns:
        dict: Validation outcome with clean/isolated data and warnings
    """
    logger.info("Recovery API: validate() called")
    return get_manager().validate(checkpoint_data)


def status() -> dict[str, Any]:
    """
    Retrieve metadata information about recovery records on disk.
    
    Lists all checkpoints and snapshots, shows last recovery metadata,
    and current recovery policy settings.
    
    Returns:
        dict: Status information with:
            - total_checkpoints: Number of checkpoints on disk
            - checkpoints: List of checkpoint IDs
            - total_snapshots: Number of snapshots on disk
            - snapshots: List of snapshot IDs
            - last_recovery_timestamp: When recovery last ran
            - last_recovery_id: ID of last recovery
            - strategy: Current recovery strategy
            - checkpoint_interval_seconds: Checkpoint frequency
            - max_retained_checkpoints: Retention limit
    """
    logger.info("Recovery API: status() called")
    return get_manager().status()
