"""
Recovery Report definition for compiling recovery outcomes in Realtimex.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RecoveryReport:
    """
    Structured diagnostic report generated after executing a recovery planning cycle.
    
    Provides comprehensive information about what was recovered, what failed,
    what warnings were encountered, and suggested next steps for operators.
    
    Attributes:
        recovery_id: Unique identifier for this recovery operation
        timestamp: When the recovery was performed
        restored_tasks: IDs of successfully restored tasks
        restored_workflows: IDs of successfully restored workflows
        failed_restorations: Details of items that failed to restore
        missing_components: Components that couldn't be found or loaded
        warnings: Non-fatal issues encountered during recovery
        suggested_actions: Recommended actions for the operator to take
    """
    
    restored_tasks: list[str] = field(default_factory=list)
    """List of task IDs that were successfully restored from checkpoint"""
    
    restored_workflows: list[str] = field(default_factory=list)
    """List of workflow IDs that were successfully restored from checkpoint"""
    
    failed_restorations: list[dict[str, Any]] = field(default_factory=list)
    """List of items that failed to restore, with error details"""
    
    missing_components: list[str] = field(default_factory=list)
    """Names of kernel components that were not found during recovery"""
    
    warnings: list[str] = field(default_factory=list)
    """Non-fatal warnings (e.g., corrupted items isolated, missing optional data)"""
    
    suggested_actions: list[str] = field(default_factory=list)
    """Recommended next steps for the operator (e.g., re-submit isolated tasks)"""
    
    recovery_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique identifier for this recovery session"""
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    """Timestamp when recovery was performed"""

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize recovery report to dictionary.
        
        Returns:
            dict: Report data suitable for JSON serialization or event payloads
        """
        return {
            "recovery_id": self.recovery_id,
            "timestamp": self.timestamp.isoformat(),
            "restored_tasks": self.restored_tasks,
            "restored_workflows": self.restored_workflows,
            "failed_restorations": self.failed_restorations,
            "missing_components": self.missing_components,
            "warnings": self.warnings,
            "suggested_actions": self.suggested_actions,
        }
    
    @property
    def is_successful(self) -> bool:
        """Check if recovery was fully successful (no failures or warnings)."""
        return len(self.failed_restorations) == 0 and len(self.warnings) == 0
    
    @property
    def items_restored(self) -> int:
        """Total count of items successfully restored."""
        return len(self.restored_tasks) + len(self.restored_workflows)
    
    @property
    def items_failed(self) -> int:
        """Total count of items that failed to restore."""
        return len(self.failed_restorations)
