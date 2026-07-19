"""
Recovery Manager orchestrator for the Realtimex Recovery System.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from events.event import Event, EventPriority
from events.event_types import RecoveryEventType
from recovery.checkpoint import CheckpointManager
from recovery.exceptions import RecoveryError, CheckpointError
from recovery.persistence import RecoveryPersistence
from recovery.planner import RecoveryPlanner
from recovery.policies import RecoveryPolicy
from recovery.report import RecoveryReport
from recovery.snapshot import SnapshotManager
from recovery.validator import StateValidator


class RecoveryManager:
    """
    Core orchestrator of state restoration. Validates and rebuilds kernel state
    from checkpoints and snapshots without auto-resuming execution.
    
    Thread-safe: All public methods are protected by internal locks to ensure
    concurrent access safety.
    """

    def __init__(
        self,
        persistence: RecoveryPersistence,
        event_bus: Any = None,
        policy: RecoveryPolicy | None = None,
        logger: logging.Logger | None = None,
        enabled: bool = True,
    ) -> None:
        self.persistence = persistence
        self.event_bus = event_bus
        self.policy = policy or RecoveryPolicy()
        self.logger = logger or logging.getLogger("realtimex.recovery")
        self.enabled = enabled

        # Core subsystems
        self.validator = StateValidator()
        self.checkpoint_manager = CheckpointManager(
            persistence=self.persistence,
            policy=self.policy,
            logger=self.logger,
        )
        self.snapshot_manager = SnapshotManager(
            persistence=self.persistence,
            policy=self.policy,
            logger=self.logger,
        )
        self.planner = RecoveryPlanner(
            validator=self.validator,
            policy=self.policy,
        )

        # Restorer callbacks (to inject states back into respective subsystems)
        self._task_restorer: Callable[[dict[str, Any]], None] | None = None
        self._workflow_restorer: Callable[[dict[str, Any]], None] | None = None
        self._memory_restorer: Callable[[dict[str, Any]], None] | None = None

        # Tracking last action details
        self.last_recovery_report: RecoveryReport | None = None
        self.last_recovery_timestamp: datetime | None = None
        
        # Thread safety lock
        self._lock = threading.RLock()

    # --- Delegated Callbacks ---

    def register_task_restorer(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register callback for injecting recovered tasks into Task System."""
        with self._lock:
            self._task_restorer = callback

    def register_workflow_restorer(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register callback for injecting recovered workflows into Workflow Engine."""
        with self._lock:
            self._workflow_restorer = callback

    def register_memory_restorer(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register callback for injecting recovered memories into Memory System."""
        with self._lock:
            self._memory_restorer = callback

    # --- Public API ---

    def recover(self) -> RecoveryReport:
        """
        Recover system state using the latest checkpoint available on disk.
        
        Thread-safe recovery operation that:
        1. Emits RecoveryStarted event
        2. Loads latest checkpoint
        3. Validates and restores state
        4. Emits RecoveryCompleted/RecoveryFailed event
        
        Returns:
            RecoveryReport: Detailed report of restoration outcomes
            
        Raises:
            RecoveryError: If recovery fails at critical stages
        """
        with self._lock:
            self._emit_event(RecoveryEventType.RECOVERY_STARTED, {})

            try:
                checkpoints = self.persistence.list_checkpoints()
                if not checkpoints:
                    report = RecoveryReport(
                        warnings=["No checkpoints found on disk. Performing clean start."],
                        suggested_actions=["Verify backup presence if crash occurred."],
                    )
                    self.last_recovery_report = report
                    self.last_recovery_timestamp = datetime.now(timezone.utc)
                    self._emit_event(RecoveryEventType.RECOVERY_COMPLETED, report.to_dict())
                    self.logger.info("Recovery completed: clean start (no checkpoints)")
                    return report

                # Recover from latest checkpoint
                latest_id = checkpoints[-1]
                self.logger.info("Starting recovery from checkpoint: %s", latest_id)
                return self.restore_checkpoint(latest_id)

            except Exception as e:
                self.logger.error("System recovery failed: %s", e, exc_info=True)
                self._emit_event(RecoveryEventType.RECOVERY_FAILED, {"error": str(e)})
                raise RecoveryError(f"System recovery failed: {e}") from e

    def create_checkpoint(
        self,
        checkpoint_id: str,
        tasks: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        memories: list[dict[str, Any]],
        kernel_metadata: dict[str, Any] | None = None,
        pending_events: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Create an automatic checkpoint file of active state.
        
        Thread-safe checkpoint creation with automatic pruning of old checkpoints.
        
        Args:
            checkpoint_id: Unique identifier for this checkpoint
            tasks: List of task state dictionaries to checkpoint
            workflows: List of workflow state dictionaries to checkpoint
            memories: List of memory reference dictionaries to checkpoint
            kernel_metadata: Optional kernel metadata (e.g., version, config)
            pending_events: Optional list of pending events awaiting processing
        """
        with self._lock:
            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tasks": tasks,
                "workflows": workflows,
                "memories": memories,
                "kernel_metadata": kernel_metadata or {},
                "pending_events": pending_events or [],
            }
            self.checkpoint_manager.save(checkpoint_id, checkpoint_data)
            self._emit_event(
                RecoveryEventType.CHECKPOINT_LOADED,
                {"checkpoint_id": checkpoint_id, "task_count": len(tasks), "workflow_count": len(workflows)}
            )
            self.logger.info("Checkpoint created: %s (tasks=%d, workflows=%d)", checkpoint_id, len(tasks), len(workflows))

    def restore_checkpoint(self, checkpoint_id: str) -> RecoveryReport:
        """
        Load and restore system state from a specific checkpoint.
        
        Thread-safe restoration that:
        1. Loads checkpoint from persistence
        2. Validates all data elements
        3. Isolates corrupted elements
        4. Re-injects valid states via registered callbacks
        5. Generates detailed recovery report
        
        Args:
            checkpoint_id: ID of checkpoint to restore
            
        Returns:
            RecoveryReport: Detailed report with restored items, failures, warnings
            
        Raises:
            CheckpointError: If checkpoint not found or corrupted
        """
        with self._lock:
            data = self.checkpoint_manager.load(checkpoint_id)
            if data is None:
                raise CheckpointError(f"Checkpoint with ID '{checkpoint_id}' not found.")

            self.logger.info("Restoring checkpoint: %s", checkpoint_id)
            
            # 1. Plan Recovery Sequence
            plan = self.planner.plan_recovery(checkpoint_id, data)

            restored_tasks: list[str] = []
            restored_workflows: list[str] = []
            failed_restorations: list[dict[str, Any]] = []

            # 2. Re-inject clean states via restorer delegates
            clean = plan.clean_data
            isolated = plan.isolated_data

            # Restore Tasks
            for t in clean.get("tasks", []):
                try:
                    if self._task_restorer is not None:
                        self._task_restorer(t)
                    restored_tasks.append(t["task_id"])
                    self._emit_event(RecoveryEventType.TASK_RECOVERED, {"task_id": t["task_id"]})
                    self.logger.debug("Task restored: %s", t["task_id"])
                except Exception as e:
                    self.logger.error("Failed to restore task %s: %s", t.get("task_id"), e)
                    failed_restorations.append({"type": "task", "id": t.get("task_id"), "error": str(e)})

            # Restore Workflows
            for w in clean.get("workflows", []):
                try:
                    if self._workflow_restorer is not None:
                        self._workflow_restorer(w)
                    restored_workflows.append(w["workflow_id"])
                    self._emit_event(RecoveryEventType.WORKFLOW_RECOVERED, {"workflow_id": w["workflow_id"]})
                    self.logger.debug("Workflow restored: %s", w["workflow_id"])
                except Exception as e:
                    self.logger.error("Failed to restore workflow %s: %s", w.get("workflow_id"), e)
                    failed_restorations.append({"type": "workflow", "id": w.get("workflow_id"), "error": str(e)})

            # Restore Memory References
            restored_memories: list[str] = []
            for m in clean.get("memories", []):
                try:
                    if self._memory_restorer is not None:
                        self._memory_restorer(m)
                    restored_memories.append(m.get("memory_id", ""))
                    self._emit_event(RecoveryEventType.MEMORY_RECOVERED, {"memory_id": m["memory_id"]})
                    self.logger.debug("Memory restored: %s", m["memory_id"])
                except Exception as e:
                    self.logger.warning("Memory reference restoration failed for %s: %s", m.get("memory_id"), e)
                    # Memory restoration failure shouldn't abort report

            # 3. Handle isolated corrupted files/states
            warnings = list(plan.warnings)
            suggested_actions: list[str] = []
            
            # Add warnings for isolated items
            for t in isolated.get("tasks", []):
                task_id = t.get('task_id', 'unknown')
                warnings.append(f"Task '{task_id}' was isolated due to schema corruption.")
                suggested_actions.append(f"Re-submit isolated task: {task_id}.")
            for w in isolated.get("workflows", []):
                wf_id = w.get('workflow_id', 'unknown')
                warnings.append(f"Workflow '{wf_id}' was isolated due to schema corruption.")
                suggested_actions.append(f"Re-submit isolated workflow: {wf_id}.")

            report = RecoveryReport(
                restored_tasks=restored_tasks,
                restored_workflows=restored_workflows,
                failed_restorations=failed_restorations,
                warnings=warnings,
                suggested_actions=suggested_actions,
            )

            self.last_recovery_report = report
            self.last_recovery_timestamp = datetime.now(timezone.utc)

            self._emit_event(RecoveryEventType.RECOVERY_COMPLETED, report.to_dict())
            self.logger.info(
                "Recovery completed: restored %d tasks, %d workflows, %d failures",
                len(restored_tasks), len(restored_workflows), len(failed_restorations)
            )

            return report

    def create_snapshot(
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
        Create a full system snapshot backup for diagnostics.
        
        Thread-safe snapshot creation that:
        1. Captures entire system state
        2. Persists to disk
        3. Enforces retention policies
        4. Emits SnapshotCreated event
        
        Args:
            snapshot_id: Unique identifier for this snapshot
            config: Current kernel configuration
            tasks: All task state dictionaries
            workflows: All workflow state dictionaries
            memories: All memory references
            permissions: Permission cache state
            module_metadata: Module registry state
            
        Returns:
            dict: The snapshot data that was created
        """
        with self._lock:
            snap_data = self.snapshot_manager.create(
                snapshot_id=snapshot_id,
                config=config,
                tasks=tasks,
                workflows=workflows,
                memories=memories,
                permissions=permissions,
                module_metadata=module_metadata,
            )
            self._emit_event(RecoveryEventType.SNAPSHOT_CREATED, {"snapshot_id": snapshot_id, "size_estimate": len(str(snap_data))})
            self.logger.info("Snapshot created: %s", snapshot_id)
            return snap_data

    def restore_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """
        Restore system backup dataset from snapshot.
        
        Thread-safe snapshot restoration that loads and returns entire system state.
        
        Args:
            snapshot_id: ID of snapshot to restore
            
        Returns:
            dict: Complete system state from snapshot
            
        Raises:
            SnapshotError: If snapshot not found or corrupted
        """
        with self._lock:
            data = self.snapshot_manager.restore(snapshot_id)
            self._emit_event(RecoveryEventType.SNAPSHOT_RESTORED, {"snapshot_id": snapshot_id})
            self.logger.info("Snapshot restored: %s", snapshot_id)
            return data

    def validate(self, checkpoint_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate checkpoint data and report warnings.
        
        Thread-safe validation that checks structural integrity of checkpoint data.
        
        Args:
            checkpoint_data: Checkpoint data to validate
            
        Returns:
            dict: Validation outcome with clean data, isolated data, and warnings
        """
        with self._lock:
            outcome = self.validator.validate_checkpoint_data(checkpoint_data)
            self._emit_event(
                name=RecoveryEventType.STATE_VALIDATED,
                payload={"warnings_count": len(outcome["warnings"]), "clean_tasks": len(outcome["clean"]["tasks"])},
            )
            self.logger.info("State validation completed: %d warnings, %d clean items", 
                           len(outcome["warnings"]), 
                           len(outcome["clean"]["tasks"]) + len(outcome["clean"]["workflows"]))
            return outcome

    def status(self) -> dict[str, Any]:
        """
        Retrieve current metadata status of recovery records on disk.
        
        Thread-safe status retrieval that lists all checkpoints and snapshots.
        
        Returns:
            dict: Status information including checkpoint/snapshot lists and recovery metadata
        """
        with self._lock:
            checkpoints = self.persistence.list_checkpoints()
            snapshots = self.persistence.list_snapshots()
            
            status_dict = {
                "total_checkpoints": len(checkpoints),
                "checkpoints": checkpoints,
                "total_snapshots": len(snapshots),
                "snapshots": snapshots,
                "last_recovery_timestamp": (
                    self.last_recovery_timestamp.isoformat() if self.last_recovery_timestamp else None
                ),
                "last_recovery_id": (
                    self.last_recovery_report.recovery_id if self.last_recovery_report else None
                ),
                "strategy": self.policy.recovery_strategy,
                "checkpoint_interval_seconds": self.policy.checkpoint_interval_seconds,
                "max_retained_checkpoints": self.policy.max_retained_checkpoints,
            }
            self.logger.debug("Recovery status: %d checkpoints, %d snapshots", len(checkpoints), len(snapshots))
            return status_dict

    # --- Internal Event Emitting ---

    def _emit_event(self, name: str, payload: dict[str, Any]) -> None:
        """
        Emit an event to the event bus with error handling.
        
        Thread-safe event emission that logs failures without propagating exceptions.
        
        Args:
            name: Event name (typically from RecoveryEventType)
            payload: Event payload dictionary
        """
        if self.event_bus is not None:
            try:
                self.event_bus.emit(
                    Event(
                        name=name,
                        source="recovery.manager",
                        task_id="",
                        priority=EventPriority.NORMAL,
                        payload=payload,
                    )
                )
            except Exception as e:
                self.logger.warning("Event dispatch failed for %s: %s", name, e)
