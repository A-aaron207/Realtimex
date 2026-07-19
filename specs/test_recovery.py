"""
Unit tests for the Realtimex Recovery System.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from events.event import Event
from events.event_types import RecoveryEventType
from recovery.exceptions import RecoveryPlannerError, CheckpointError, RecoveryError
from recovery.manager import RecoveryManager
from recovery.persistence import RecoveryPersistence
from recovery.policies import RecoveryPolicy
from recovery.report import RecoveryReport
from recovery import api


class DummyEventBus:
    """Mock event bus to collect emitted recovery system events."""

    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class TestRecoverySystem(unittest.TestCase):
    """Test cases verifying checkpointing, snapshots, state validation, and planner policies."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.persistence_path = Path(self.temp_dir.name)
        self.persistence = RecoveryPersistence(directory=self.persistence_path)
        self.event_bus = DummyEventBus()
        
        self.policy = RecoveryPolicy(
            checkpoint_interval_seconds=10.0,
            max_retained_checkpoints=3,
            snapshot_retention_days=10,
            recovery_strategy="fail_safe",
        )

        self.manager = RecoveryManager(
            persistence=self.persistence,
            event_bus=self.event_bus,
            policy=self.policy,
        )

        # Delegate trackers
        self.restored_tasks_payloads: list[dict[str, Any]] = []
        self.restored_workflows_payloads: list[dict[str, Any]] = []

        def task_restorer(data: dict[str, Any]) -> None:
            self.restored_tasks_payloads.append(data)

        def workflow_restorer(data: dict[str, Any]) -> None:
            self.restored_workflows_payloads.append(data)

        self.manager.register_task_restorer(task_restorer)
        self.manager.register_workflow_restorer(workflow_restorer)

        # Initialize API
        api.initialize_api(self.manager)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_checkpoint_pruning(self) -> None:
        """Verify checkpoint creation and automatic pruning of oldest checkpoints."""
        # Create 5 checkpoints (limit is 3)
        for i in range(1, 6):
            self.manager.create_checkpoint(
                checkpoint_id=f"cp-{i}",
                tasks=[{"task_id": f"t-{i}", "status": "active", "action": "test"}],
                workflows=[],
                memories=[],
            )

        # Check files on disk: cp-1 and cp-2 should be pruned, cp-3, cp-4, cp-5 should remain!
        checkpoints_on_disk = self.persistence.list_checkpoints()
        self.assertEqual(len(checkpoints_on_disk), 3)
        self.assertNotIn("cp-1", checkpoints_on_disk)
        self.assertNotIn("cp-2", checkpoints_on_disk)
        self.assertIn("cp-3", checkpoints_on_disk)
        self.assertIn("cp-4", checkpoints_on_disk)
        self.assertIn("cp-5", checkpoints_on_disk)

    def test_snapshot_creation_and_restoration(self) -> None:
        """Verify snapshot backup creation and retrieval."""
        config = {"environment": "production"}
        tasks = [{"task_id": "t-snap", "status": "active", "action": "test"}]
        workflows = [{"workflow_id": "w-snap", "status": "active", "steps": []}]
        memories = [{"memory_id": "m-snap", "scope": "global"}]
        permissions = {"allow_write": True}
        module_meta = {"version": "1.0.0"}

        # 1. Create snapshot
        self.manager.create_snapshot("backup-1", config, tasks, workflows, memories, permissions, module_meta)
        
        # Verify event
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("SnapshotCreated", emitted_names)

        # 2. Restore snapshot
        restored = self.manager.restore_snapshot("backup-1")
        self.assertEqual(restored["config"], config)
        self.assertEqual(restored["tasks"], tasks)
        self.assertEqual(restored["permissions"], permissions)

        # Verify event
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("SnapshotRestored", emitted_names)

    def test_recovery_fail_safe_strategy(self) -> None:
        """Verify that fail-safe strategy recovers valid data and isolates corrupted items."""
        # 1 task is valid, 1 task is corrupted (missing status & action keys)
        tasks = [
            {"task_id": "t-valid", "status": "active", "action": "run_test"},
            {"task_id": "t-corrupt"},  # invalid: missing required fields
        ]
        workflows = [
            {"workflow_id": "w-valid", "status": "active", "steps": []},
        ]

        self.manager.create_checkpoint(
            checkpoint_id="cp-recovery",
            tasks=tasks,
            workflows=workflows,
            memories=[],
        )

        # Execute recovery (using latest checkpoint cp-recovery)
        report = self.manager.recover()

        # Check delegates
        self.assertEqual(len(self.restored_tasks_payloads), 1)
        self.assertEqual(self.restored_tasks_payloads[0]["task_id"], "t-valid")
        self.assertEqual(len(self.restored_workflows_payloads), 1)
        self.assertEqual(self.restored_workflows_payloads[0]["workflow_id"], "w-valid")

        # Check Report details
        self.assertIn("t-valid", report.restored_tasks)
        self.assertNotIn("t-corrupt", report.restored_tasks)
        self.assertTrue(any("t-corrupt" in w for w in report.warnings))

        # Check emitted events
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("RecoveryStarted", emitted_names)
        self.assertIn("TaskRecovered", emitted_names)
        self.assertIn("WorkflowRecovered", emitted_names)
        self.assertIn("RecoveryCompleted", emitted_names)

    def test_recovery_strict_strategy(self) -> None:
        """Verify that strict strategy aborts recovery completely if any corruption exists."""
        self.manager.policy.recovery_strategy = "strict"

        tasks = [
            {"task_id": "t-valid", "status": "active", "action": "run_test"},
            {"task_id": "t-corrupt"},  # invalid: missing required fields
        ]

        self.manager.create_checkpoint(
            checkpoint_id="cp-strict",
            tasks=tasks,
            workflows=[],
            memories=[],
        )

        # Recovery should fail/abort and raise RecoveryError
        with self.assertRaises(RecoveryError):
            self.manager.recover()

    def test_api_facade(self) -> None:
        """Verify functional helper APIs from recovery.api."""
        tasks = [{"task_id": "t-api", "status": "active", "action": "test"}]
        
        # Test create_checkpoint via API
        api.create_checkpoint("cp-api", tasks, [], [])

        # Test status via API
        status = api.status()
        self.assertEqual(status["total_checkpoints"], 1)
        self.assertIn("cp-api", status["checkpoints"])

        # Test validate via API
        validation = api.validate({"tasks": tasks, "workflows": [], "memories": []})
        self.assertEqual(len(validation["clean"]["tasks"]), 1)
        self.assertEqual(len(validation["warnings"]), 0)


if __name__ == "__main__":
    unittest.main()
