"""
Unit tests for the Realtimex Memory System.
"""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from events.event import Event
from events.event_types import MemoryEventType
from memory.exceptions import (
    MemoryNotFoundError,
    MemoryPolicyViolationError,
    MemoryValidationError,
)
from memory.manager import MemoryManager
from memory.persistence import FileMemoryPersistence
from memory.policies import MemoryPolicy
from memory.registry import MemoryRecord
from memory.search import MemorySearchQuery




class DummyEventBus:
    """Mock event bus to collect emitted memory system events."""

    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class TestMemorySystem(unittest.TestCase):
    """Test cases verifying Memory System scopes, persistence, policies, and lifecycle."""

    def setUp(self) -> None:
        # Create a temporary directory for file persistence tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.persistence_path = Path(self.temp_dir.name)
        self.persistence = FileMemoryPersistence(directory=self.persistence_path)
        self.event_bus = DummyEventBus()
        
        self.policy = MemoryPolicy(
            max_records_per_task=3,
            retention_period_days=30,
            default_ephemeral_ttl_seconds=1, # short TTL for quick expiration tests
        )

        self.manager = MemoryManager(
            persistence=self.persistence,
            event_bus=self.event_bus,
            policy=self.policy,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_serialization(self) -> None:
        """Verify serialization of memory records to and from dictionary."""
        rec = MemoryRecord(
            content="My project details",
            scope="global",
            owner="user-1",
            source="user",
            tags=["project", "info"],
        )
        data = rec.to_dict()
        self.assertEqual(data["content"], "My project details")
        self.assertEqual(data["scope"], "global")

        rec2 = MemoryRecord.from_dict(data)
        self.assertEqual(rec2.content, "My project details")
        self.assertEqual(rec2.scope, "global")
        self.assertEqual(rec2.tags, ["project", "info"])

        with self.assertRaises(MemoryValidationError):
            # Invalid scope
            MemoryRecord(content="foo", scope="invalid"  # type: ignore
                         , owner="bar", source="test")

    def test_create_and_exact_lookup(self) -> None:
        """Verify memory creation and exact lookup across all scopes."""
        # 1. Global
        g_rec = self.manager.create("global", "system", "Theme: dark", "user_preferences")
        # 2. Task
        t_rec = self.manager.create("task", "task-101", "Plan details", "planner", tags=["plan"])
        # 3. Ephemeral
        e_rec = self.manager.create("ephemeral", "session-1", "Temp math calculation", "worker")

        # Verify lookups
        self.assertEqual(self.manager.retrieve(g_rec.memory_id).content, "Theme: dark")
        self.assertEqual(self.manager.retrieve(t_rec.memory_id).content, "Plan details")
        self.assertEqual(self.manager.retrieve(e_rec.memory_id).content, "Temp math calculation")

        # Verify events
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertEqual(emitted_names.count("MemoryCreated"), 3)

    def test_persistence_scopes(self) -> None:
        """Verify task and global scopes persist to disk, while ephemeral remains in memory."""
        g_rec = self.manager.create("global", "system", "Global info", "user")
        t_rec = self.manager.create("task", "task-abc", "Task info", "worker")
        e_rec = self.manager.create("ephemeral", "temp", "Ephemeral info", "scheduler")

        # Check files on disk
        global_file = self.persistence_path / "global" / "global_store.json"
        task_file = self.persistence_path / "task" / "task-abc.json"

        self.assertTrue(global_file.exists())
        self.assertTrue(task_file.exists())

        # Verify ephemeral is not on disk (no ephemeral folder)
        self.assertFalse((self.persistence_path / "ephemeral").exists())

        # Load fresh manager on same directory
        manager2 = MemoryManager(persistence=self.persistence)
        # Global should be pre-loaded
        self.assertEqual(manager2.retrieve(g_rec.memory_id).content, "Global info")
        # Task should lazy load on query
        self.assertEqual(manager2.retrieve(t_rec.memory_id).content, "Task info")
        # Ephemeral is gone
        with self.assertRaises(MemoryNotFoundError):
            manager2.retrieve(e_rec.memory_id)

    def test_ephemeral_expiration(self) -> None:
        """Verify ephemeral records auto-expire based on TTL."""
        rec = self.manager.create(
            "ephemeral",
            "session-2",
            "Short-lived data",
            "test",
            ttl_seconds=0.1, # expires in 100ms
        )
        self.assertEqual(self.manager.retrieve(rec.memory_id).content, "Short-lived data")

        # Wait past expiration
        time.sleep(0.15)

        with self.assertRaises(MemoryNotFoundError):
            self.manager.retrieve(rec.memory_id)

        # Check that MemoryExpired event was emitted
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("MemoryExpired", emitted_names)

    def test_policy_limits(self) -> None:
        """Verify task capacity enforcement policies."""
        # Create maximum allowed (3)
        self.manager.create("task", "task-limit", "Record 1", "test")
        self.manager.create("task", "task-limit", "Record 2", "test")
        self.manager.create("task", "task-limit", "Record 3", "test")

        # Adding a 4th should raise PolicyViolationError
        with self.assertRaises(MemoryPolicyViolationError):
            self.manager.create("task", "task-limit", "Record 4", "test")

    def test_lifecycle_transitions(self) -> None:
        """Verify memory archiving, deleting, and lifecycle state changes."""
        rec = self.manager.create("global", "system", "Status record", "test")
        self.assertEqual(rec.status, "active")

        # 1. Archive
        archived = self.manager.archive(rec.memory_id)
        self.assertEqual(archived.status, "archived")

        # 2. Delete
        self.manager.delete(rec.memory_id)
        with self.assertRaises(MemoryNotFoundError):
            self.manager.retrieve(rec.memory_id)

        # Check emitted events
        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("MemoryArchived", emitted_names)
        self.assertIn("MemoryDeleted", emitted_names)

    def test_scope_migration_moving(self) -> None:
        """Verify moving memories between scopes handles updates and disk syncs correctly."""
        # Start as ephemeral
        rec = self.manager.create("ephemeral", "task-id-1", "Draft analysis", "worker")
        self.assertEqual(rec.scope, "ephemeral")

        # 1. Move Ephemeral -> Task
        moved_task = self.manager.move(rec.memory_id, "task")
        self.assertEqual(moved_task.scope, "task")
        self.assertTrue((self.persistence_path / "task" / "task-id-1.json").exists())
        self.assertEqual(self.manager.retrieve(rec.memory_id).scope, "task")

        # 2. Move Task -> Global
        moved_global = self.manager.move(rec.memory_id, "global")
        self.assertEqual(moved_global.scope, "global")
        # Task file should be pruned as partition is empty
        self.assertFalse((self.persistence_path / "task" / "task-id-1.json").exists())
        self.assertTrue((self.persistence_path / "global" / "global_store.json").exists())
        self.assertEqual(self.manager.retrieve(rec.memory_id).scope, "global")

    def test_retrieval_and_searches(self) -> None:
        """Verify tag search, task list, and simple semantic query filtering."""
        self.manager.create("task", "t-search", "First draft code", "coder", tags=["code", "draft"])
        self.manager.create("task", "t-search", "Code implementation rules", "architect", tags=["code", "standards"])
        self.manager.create("global", "system", "API secrets", "admin", tags=["security"])

        # 1. Lookup by Tag
        code_mems = self.manager.retrieval.get_by_tag("code")
        self.assertEqual(len(code_mems), 2)

        security_mems = self.manager.retrieval.get_by_tag("security")
        self.assertEqual(len(security_mems), 1)

        # 2. Search query structure
        query = MemorySearchQuery(tags=["code"], owner="t-search")
        results = self.manager.search(query)
        self.assertEqual(len(results), 2)

        # 3. Simple semantic search keyword ranking
        sem_results = self.manager.retrieval.semantic_search("draft coder implementation")
        self.assertEqual(sem_results[0].content, "First draft code") # matches 'draft' and 'coder' (source)


if __name__ == "__main__":
    unittest.main()
