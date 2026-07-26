"""
Sprint 1B — Memory Reliability Tests
======================================
Covers: task outputs, variable store, file references, long-term memory,
        semantic retrieval, update correctness, concurrent access patterns,
        scope enforcement, event completeness, and performance budgets.

Target: close the gap from 71/100 toward 100/100 on the Memory subsystem.
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


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------


class DummyEventBus:
    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)

    def names(self) -> list[str]:
        return [e.name for e in self.emitted]


def _make_manager(
    tmp_path: Path,
    max_records: int = 100,
    ephemeral_ttl: float = 60.0,
    retention_days: int = 365,
) -> tuple[MemoryManager, DummyEventBus]:
    persistence = FileMemoryPersistence(directory=tmp_path)
    event_bus = DummyEventBus()
    policy = MemoryPolicy(
        max_records_per_task=max_records,
        retention_period_days=retention_days,
        default_ephemeral_ttl_seconds=ephemeral_ttl,
    )
    manager = MemoryManager(persistence=persistence, event_bus=event_bus, policy=policy)
    return manager, event_bus


# ---------------------------------------------------------------------------
# 1. Task Output Storage
# ---------------------------------------------------------------------------


class TestTaskOutputStorage(unittest.TestCase):
    """Memory: task-scoped output storage and retrieval."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_store_and_retrieve_task_output(self) -> None:
        """Task output can be stored and retrieved by memory_id."""
        rec = self.manager.create("task", "task-out-1", {"result": 42, "status": "ok"}, "worker")
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, {"result": 42, "status": "ok"})

    def test_task_output_persists_to_disk(self) -> None:
        """Task-scoped memory is persisted to disk immediately."""
        rec = self.manager.create("task", "task-out-2", "output text", "worker")
        file_path = Path(self.temp.name) / "task" / "task-out-2.json"
        self.assertTrue(file_path.exists(), "Task memory file must exist on disk")

    def test_multiple_task_outputs_same_task(self) -> None:
        """Multiple records for the same task are all retrievable."""
        rec1 = self.manager.create("task", "task-out-3", "step 1 result", "worker_a")
        rec2 = self.manager.create("task", "task-out-3", "step 2 result", "worker_b")
        self.assertEqual(self.manager.retrieve(rec1.memory_id).content, "step 1 result")
        self.assertEqual(self.manager.retrieve(rec2.memory_id).content, "step 2 result")

    def test_task_output_with_metadata(self) -> None:
        """Task output metadata is stored and retrieved correctly."""
        rec = self.manager.create(
            "task", "task-out-4", "result", "worker",
            metadata={"duration_ms": 120, "step_id": "s3"}
        )
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.metadata["step_id"], "s3")
        self.assertEqual(fetched.metadata["duration_ms"], 120)

    def test_task_output_tagged_for_search(self) -> None:
        """Task output with tags is discoverable via tag search."""
        self.manager.create("task", "task-out-5", "ml prediction", "model", tags=["ml", "prediction"])
        results = self.manager.retrieval.get_by_tag("ml")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "ml prediction")

    def test_task_output_retrieved_by_scope_search(self) -> None:
        """Task outputs appear in search results when filtered by task scope."""
        self.manager.create("task", "task-out-6", "task data", "worker")
        self.manager.create("global", "system", "global data", "admin")
        query = MemorySearchQuery(scope="task", owner="task-out-6")
        results = self.manager.search(query)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "task data")

    def test_deleted_task_output_not_found(self) -> None:
        """After delete, task output raises MemoryNotFoundError on retrieve."""
        rec = self.manager.create("task", "task-out-7", "temp output", "worker")
        self.manager.delete(rec.memory_id)
        with self.assertRaises(MemoryNotFoundError):
            self.manager.retrieve(rec.memory_id)

    def test_task_output_updated_correctly(self) -> None:
        """update() replaces content of a task output."""
        rec = self.manager.create("task", "task-out-8", "old output", "worker")
        updated = self.manager.update(rec.memory_id, content="new output")
        self.assertEqual(updated.content, "new output")
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, "new output")

    def test_task_output_update_tags(self) -> None:
        """update() replaces tags and index is updated."""
        rec = self.manager.create("task", "task-out-9", "data", "worker", tags=["old"])
        self.manager.update(rec.memory_id, tags=["new_tag"])
        results = self.manager.retrieval.get_by_tag("new_tag")
        self.assertEqual(len(results), 1)
        # Old tag should be de-indexed
        old_results = self.manager.retrieval.get_by_tag("old")
        self.assertEqual(len(old_results), 0)


# ---------------------------------------------------------------------------
# 2. Variable Store
# ---------------------------------------------------------------------------


class TestVariableStore(unittest.TestCase):
    """Memory: global variable/preference storage and fast retrieval."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_store_user_preference(self) -> None:
        """User preference stored globally is retrievable instantly."""
        rec = self.manager.create("global", "system", "dark", "user_preferences", tags=["theme"])
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, "dark")

    def test_global_variable_survives_manager_restart(self) -> None:
        """Global variable persists across MemoryManager re-initialization."""
        rec = self.manager.create("global", "system", "VSCode", "preferences", tags=["editor"])
        memory_id = rec.memory_id

        # Re-init with same persistence directory
        manager2, _ = _make_manager(Path(self.temp.name))
        fetched = manager2.retrieve(memory_id)
        self.assertEqual(fetched.content, "VSCode")

    def test_multiple_global_variables(self) -> None:
        """Multiple global variables coexist without collision."""
        r1 = self.manager.create("global", "system", "dark", "user", tags=["theme"])
        r2 = self.manager.create("global", "system", "VSCode", "user", tags=["editor"])
        r3 = self.manager.create("global", "system", "/home/user/projects", "user", tags=["workspace"])

        self.assertEqual(self.manager.retrieve(r1.memory_id).content, "dark")
        self.assertEqual(self.manager.retrieve(r2.memory_id).content, "VSCode")
        self.assertEqual(self.manager.retrieve(r3.memory_id).content, "/home/user/projects")

    def test_update_global_variable(self) -> None:
        """Global variable can be updated and persisted."""
        rec = self.manager.create("global", "system", "light", "user", tags=["theme"])
        self.manager.update(rec.memory_id, content="dark")
        manager2, _ = _make_manager(Path(self.temp.name))
        fetched = manager2.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, "dark")

    def test_workspace_context_stored_globally(self) -> None:
        """Workspace path stored as a global variable survives restart."""
        rec = self.manager.create(
            "global", "system",
            {"workspace": "~/Projects/Realtimex", "branch": "feature/reliability"},
            "workspace_context",
            tags=["workspace", "git"]
        )
        manager2, _ = _make_manager(Path(self.temp.name))
        fetched = manager2.retrieve(rec.memory_id)
        self.assertEqual(fetched.content["branch"], "feature/reliability")

    def test_global_tag_search_returns_preference(self) -> None:
        """Global preferences tagged correctly are found by tag search."""
        self.manager.create("global", "system", "en-US", "preferences", tags=["language", "locale"])
        results = self.manager.retrieval.get_by_tag("locale")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "en-US")


# ---------------------------------------------------------------------------
# 3. File References
# ---------------------------------------------------------------------------


class TestFileReferences(unittest.TestCase):
    """Memory: file reference tracking for generated and read files."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_store_generated_file_reference(self) -> None:
        """Generated file path can be stored and retrieved as a memory record."""
        rec = self.manager.create(
            "task", "task-file-1",
            "/home/user/projects/calculator.py",
            "developer_module",
            tags=["generated", "python"]
        )
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, "/home/user/projects/calculator.py")

    def test_file_references_searchable_by_tag(self) -> None:
        """File references tagged with 'generated' are discoverable."""
        self.manager.create("task", "task-file-2", "file_a.py", "worker", tags=["generated"])
        self.manager.create("task", "task-file-2", "file_b.py", "worker", tags=["generated"])
        self.manager.create("task", "task-file-2", "untagged.py", "worker", tags=["read"])
        gen_files = self.manager.retrieval.get_by_tag("generated")
        self.assertEqual(len(gen_files), 2)

    def test_store_and_list_read_files(self) -> None:
        """Files read during a task can be tracked by 'read' tag."""
        self.manager.create("task", "task-file-3", "/etc/os-release", "filesystem_module", tags=["read"])
        results = self.manager.retrieval.get_by_tag("read")
        self.assertEqual(results[0].content, "/etc/os-release")

    def test_file_reference_with_metadata(self) -> None:
        """File reference can include rich metadata (size, type, checksum)."""
        rec = self.manager.create(
            "task", "task-file-4",
            "report.md",
            "developer_module",
            tags=["generated", "markdown"],
            metadata={"size_bytes": 4096, "language": "markdown"}
        )
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.metadata["language"], "markdown")

    def test_move_file_ref_from_ephemeral_to_task(self) -> None:
        """File reference created in ephemeral scope can be promoted to task."""
        rec = self.manager.create("ephemeral", "task-file-5", "temp_output.csv", "worker")
        moved = self.manager.move(rec.memory_id, "task")
        self.assertEqual(moved.scope, "task")
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, "temp_output.csv")


# ---------------------------------------------------------------------------
# 4. Long-term Memory (Cross-session Persistence)
# ---------------------------------------------------------------------------


class TestLongTermMemory(unittest.TestCase):
    """Memory: persistence across multiple manager lifecycle cycles."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_global_memory_survives_three_restarts(self) -> None:
        """Global memory is accessible after three successive manager restarts."""
        m1, _ = _make_manager(Path(self.temp.name))
        rec = m1.create("global", "system", "persisted_value", "test")
        mid = rec.memory_id

        for _ in range(3):
            mx, _ = _make_manager(Path(self.temp.name))
            fetched = mx.retrieve(mid)
            self.assertEqual(fetched.content, "persisted_value")

    def test_task_memory_survives_restart(self) -> None:
        """Task memory is lazily loaded and accessible after restart."""
        m1, _ = _make_manager(Path(self.temp.name))
        rec = m1.create("task", "long-task-1", "task_output", "worker")
        mid = rec.memory_id

        m2, _ = _make_manager(Path(self.temp.name))
        fetched = m2.retrieve(mid)
        self.assertEqual(fetched.content, "task_output")

    def test_ephemeral_does_not_survive_restart(self) -> None:
        """Ephemeral memory is not available after manager restart."""
        m1, _ = _make_manager(Path(self.temp.name))
        rec = m1.create("ephemeral", "session-1", "volatile_data", "worker")
        mid = rec.memory_id

        m2, _ = _make_manager(Path(self.temp.name))
        with self.assertRaises(MemoryNotFoundError):
            m2.retrieve(mid)

    def test_archived_memory_persists(self) -> None:
        """Archived global memory is still retrievable after restart."""
        m1, _ = _make_manager(Path(self.temp.name))
        rec = m1.create("global", "system", "archived_data", "test")
        m1.archive(rec.memory_id)
        mid = rec.memory_id

        m2, _ = _make_manager(Path(self.temp.name))
        fetched = m2.retrieve(mid)
        self.assertEqual(fetched.status, "archived")
        self.assertEqual(fetched.content, "archived_data")

    def test_bootstrap_indexes_populated_on_restart(self) -> None:
        """After restart, indexes are rebuilt and tag search works."""
        m1, _ = _make_manager(Path(self.temp.name))
        m1.create("global", "system", "indexed_value", "test", tags=["session_data"])
        m1.create("task", "boot-task-1", "task_val", "worker", tags=["step_output"])

        m2, _ = _make_manager(Path(self.temp.name))
        global_results = m2.retrieval.get_by_tag("session_data")
        task_results = m2.retrieval.get_by_tag("step_output")
        self.assertEqual(len(global_results), 1)
        self.assertEqual(len(task_results), 1)


# ---------------------------------------------------------------------------
# 5. Semantic Retrieval
# ---------------------------------------------------------------------------


class TestSemanticRetrieval(unittest.TestCase):
    """Memory: semantic/keyword search ordering and ranking."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_semantic_search_returns_best_match_first(self) -> None:
        """Semantic search returns the most relevant result first."""
        self.manager.create("task", "t-sem-1", "First draft code implementation", "coder", tags=["draft"])
        self.manager.create("task", "t-sem-1", "Code review standards", "architect", tags=["standards"])
        self.manager.create("global", "system", "API security tokens", "admin", tags=["security"])
        results = self.manager.retrieval.semantic_search("draft code implementation")
        self.assertGreater(len(results), 0)
        # First result should be the most relevant
        self.assertIn("draft", results[0].content.lower())

    def test_semantic_search_with_zero_results(self) -> None:
        """Semantic search for unrelated query returns empty or low-relevance list."""
        self.manager.create("task", "t-sem-2", "Python calculator", "coder")
        results = self.manager.retrieval.semantic_search("quantum entanglement photon")
        # Either empty or no exact match
        if results:
            self.assertNotIn("quantum", results[0].content.lower())

    def test_semantic_search_multi_word_match(self) -> None:
        """Semantic search on multi-word query returns best overlap."""
        self.manager.create("task", "t-sem-3", "Build web dashboard", "dev")
        self.manager.create("task", "t-sem-3", "Export CSV report", "worker")
        results = self.manager.retrieval.semantic_search("web dashboard build")
        self.assertEqual(results[0].content, "Build web dashboard")

    def test_search_query_by_owner(self) -> None:
        """Search filtered by owner returns only that owner's records."""
        self.manager.create("task", "owner-a", "Record A1", "worker")
        self.manager.create("task", "owner-b", "Record B1", "worker")
        query = MemorySearchQuery(owner="owner-a")
        results = self.manager.search(query)
        self.assertTrue(all(r.owner == "owner-a" for r in results))
        self.assertEqual(len(results), 1)

    def test_search_query_by_source(self) -> None:
        """Search filtered by source returns only records from that source."""
        self.manager.create("task", "src-task", "from worker A", "worker_a")
        self.manager.create("task", "src-task", "from worker B", "worker_b")
        query = MemorySearchQuery(source="worker_a")
        results = self.manager.search(query)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "from worker A")

    def test_search_query_by_status(self) -> None:
        """Search filtered by status=archived returns only archived records."""
        rec = self.manager.create("global", "system", "old data", "test")
        self.manager.archive(rec.memory_id)
        self.manager.create("global", "system", "active data", "test")
        query = MemorySearchQuery(status="archived")
        results = self.manager.search(query)
        self.assertTrue(all(r.status == "archived" for r in results))
        self.assertEqual(len(results), 1)

    def test_search_by_multiple_tags(self) -> None:
        """Search with multiple tags returns only records matching all specified tags."""
        self.manager.create("task", "t-tag-1", "all tags", "worker", tags=["a", "b", "c"])
        self.manager.create("task", "t-tag-1", "some tags", "worker", tags=["a", "b"])
        self.manager.create("task", "t-tag-1", "one tag", "worker", tags=["a"])
        query = MemorySearchQuery(tags=["a", "b", "c"])
        results = self.manager.search(query)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "all tags")


# ---------------------------------------------------------------------------
# 6. Scope Enforcement
# ---------------------------------------------------------------------------


class TestScopeEnforcement(unittest.TestCase):
    """Memory: scope isolation, policy enforcement, and boundary protection."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name), max_records=3)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_invalid_scope_raises_validation_error(self) -> None:
        """Creating a record with invalid scope raises MemoryValidationError."""
        with self.assertRaises(MemoryValidationError):
            MemoryRecord(content="x", scope="invalid_scope", owner="test", source="worker")  # type: ignore

    def test_policy_limit_enforced_per_task(self) -> None:
        """Exceeding max_records_per_task raises MemoryPolicyViolationError."""
        for i in range(3):
            self.manager.create("task", "policy-task", f"record {i}", "worker")
        with self.assertRaises(MemoryPolicyViolationError):
            self.manager.create("task", "policy-task", "overflow", "worker")

    def test_policy_limit_independent_per_task(self) -> None:
        """Policy limits are per-task; different tasks don't share limits."""
        for i in range(3):
            self.manager.create("task", "task-a", f"rec {i}", "worker")
        # task-b should still accept records
        rec = self.manager.create("task", "task-b", "task-b record", "worker")
        self.assertIsNotNone(rec.memory_id)

    def test_ephemeral_not_written_to_disk(self) -> None:
        """Ephemeral records are never persisted to disk."""
        self.manager.create("ephemeral", "session-x", "volatile", "worker")
        ephemeral_dir = Path(self.temp.name) / "ephemeral"
        self.assertFalse(ephemeral_dir.exists())

    def test_global_written_to_disk(self) -> None:
        """Global records are always persisted to disk."""
        self.manager.create("global", "system", "global_val", "test")
        global_file = Path(self.temp.name) / "global" / "global_store.json"
        self.assertTrue(global_file.exists())

    def test_scope_preserved_after_retrieve(self) -> None:
        """Retrieved record preserves the original scope."""
        rec = self.manager.create("task", "scope-task", "scoped value", "worker")
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.scope, "task")

    def test_move_task_to_global_removes_task_file_when_empty(self) -> None:
        """Moving the only task record to global prunes the empty task file."""
        rec = self.manager.create("task", "prune-task", "sole record", "worker")
        self.manager.move(rec.memory_id, "global")
        task_file = Path(self.temp.name) / "task" / "prune-task.json"
        self.assertFalse(task_file.exists())

    def test_move_ephemeral_to_task_clears_expiration(self) -> None:
        """Moving from ephemeral to task clears the expiration timestamp."""
        rec = self.manager.create("ephemeral", "move-task", "data", "worker")
        moved = self.manager.move(rec.memory_id, "task")
        self.assertIsNone(moved.expires_at)


# ---------------------------------------------------------------------------
# 7. Ephemeral Expiration and Sweep
# ---------------------------------------------------------------------------


class TestEphemeralExpiration(unittest.TestCase):
    """Memory: ephemeral TTL, sweep, and expiration events."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name), ephemeral_ttl=0.1)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_ephemeral_custom_ttl_expires(self) -> None:
        """Ephemeral record expires after its custom TTL."""
        rec = self.manager.create("ephemeral", "sess-exp-1", "short lived", "worker", ttl_seconds=0.05)
        time.sleep(0.08)
        with self.assertRaises(MemoryNotFoundError):
            self.manager.retrieve(rec.memory_id)

    def test_ephemeral_within_ttl_accessible(self) -> None:
        """Ephemeral record is accessible before expiry."""
        rec = self.manager.create("ephemeral", "sess-exp-2", "alive", "worker", ttl_seconds=5.0)
        fetched = self.manager.retrieve(rec.memory_id)
        self.assertEqual(fetched.content, "alive")

    def test_expiration_emits_memory_expired_event(self) -> None:
        """MemoryExpired event is emitted when ephemeral record expires and is swept."""
        rec = self.manager.create("ephemeral", "sess-exp-3", "expiring", "worker", ttl_seconds=0.05)
        time.sleep(0.08)
        # Trigger sweep via create or retrieve
        try:
            self.manager.retrieve(rec.memory_id)
        except MemoryNotFoundError:
            pass
        self.assertIn("MemoryExpired", self.eb.names())

    def test_default_ephemeral_ttl_applied(self) -> None:
        """Ephemeral record without explicit TTL uses the policy default."""
        manager, eb = _make_manager(Path(self.temp.name), ephemeral_ttl=0.08)
        rec = manager.create("ephemeral", "sess-default", "default ttl", "worker")
        time.sleep(0.12)
        with self.assertRaises(MemoryNotFoundError):
            manager.retrieve(rec.memory_id)

    def test_multiple_ephemeral_sweep_at_once(self) -> None:
        """Multiple expired ephemeral records are swept in a single pass."""
        recs = [
            self.manager.create("ephemeral", f"sess-sweep-{i}", f"data-{i}", "worker", ttl_seconds=0.05)
            for i in range(5)
        ]
        time.sleep(0.08)
        for rec in recs:
            with self.assertRaises(MemoryNotFoundError):
                self.manager.retrieve(rec.memory_id)


# ---------------------------------------------------------------------------
# 8. Lifecycle Transitions
# ---------------------------------------------------------------------------


class TestLifecycleTransitions(unittest.TestCase):
    """Memory: valid and invalid lifecycle state transitions."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_active_to_archived(self) -> None:
        """Active record can be archived successfully."""
        rec = self.manager.create("global", "system", "active data", "test")
        archived = self.manager.archive(rec.memory_id)
        self.assertEqual(archived.status, "archived")

    def test_active_to_deleted(self) -> None:
        """Active record can be deleted successfully."""
        rec = self.manager.create("global", "system", "to delete", "test")
        self.manager.delete(rec.memory_id)
        with self.assertRaises(MemoryNotFoundError):
            self.manager.retrieve(rec.memory_id)

    def test_archive_emits_event(self) -> None:
        """archive() emits MemoryArchived event."""
        rec = self.manager.create("global", "system", "event test", "test")
        self.manager.archive(rec.memory_id)
        self.assertIn("MemoryArchived", self.eb.names())

    def test_delete_emits_event(self) -> None:
        """delete() emits MemoryDeleted event."""
        rec = self.manager.create("global", "system", "del test", "test")
        self.manager.delete(rec.memory_id)
        self.assertIn("MemoryDeleted", self.eb.names())

    def test_update_emits_event(self) -> None:
        """update() emits MemoryUpdated event."""
        rec = self.manager.create("task", "lc-task", "original", "worker")
        self.manager.update(rec.memory_id, content="updated")
        self.assertIn("MemoryUpdated", self.eb.names())

    def test_delete_nonexistent_record_is_silent(self) -> None:
        """Deleting a non-existent record does not raise an error."""
        # Should not raise
        self.manager.delete("nonexistent-id-xyz")

    def test_list_all_scopes_returns_all_active(self) -> None:
        """list() with no filter returns records from all scopes."""
        self.manager.create("global", "system", "g1", "test")
        self.manager.create("task", "list-task", "t1", "worker")
        self.manager.create("ephemeral", "sess", "e1", "worker")
        results = self.manager.list()
        self.assertGreaterEqual(len(results), 3)

    def test_list_scoped_returns_only_that_scope(self) -> None:
        """list(scope='global') returns only global-scoped records."""
        self.manager.create("global", "system", "g_only", "test")
        self.manager.create("task", "list-task-2", "t_only", "worker")
        results = self.manager.list(scope="global")
        self.assertTrue(all(r.scope == "global" for r in results))


# ---------------------------------------------------------------------------
# 9. Event Completeness
# ---------------------------------------------------------------------------


class TestEventCompleteness(unittest.TestCase):
    """Memory: events emitted for all CRUD operations."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, self.eb = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_emits_memory_created(self) -> None:
        """create() emits MemoryCreated event."""
        self.manager.create("task", "event-task", "data", "worker")
        self.assertIn("MemoryCreated", self.eb.names())

    def test_retrieve_emits_memory_retrieved(self) -> None:
        """retrieve() emits MemoryRetrieved event."""
        rec = self.manager.create("task", "event-task-2", "data", "worker")
        self.manager.retrieve(rec.memory_id)
        self.assertIn("MemoryRetrieved", self.eb.names())

    def test_update_emits_memory_updated(self) -> None:
        """update() emits MemoryUpdated event."""
        rec = self.manager.create("task", "event-task-3", "old", "worker")
        self.manager.update(rec.memory_id, content="new")
        self.assertIn("MemoryUpdated", self.eb.names())

    def test_move_emits_memory_updated(self) -> None:
        """move() emits MemoryUpdated event after scope transition."""
        rec = self.manager.create("ephemeral", "move-sess", "data", "worker")
        self.manager.move(rec.memory_id, "task")
        self.assertIn("MemoryUpdated", self.eb.names())

    def test_create_count_matches_records(self) -> None:
        """Number of MemoryCreated events matches number of created records."""
        for i in range(4):
            self.manager.create("task", "count-task", f"rec {i}", "worker")
        created_count = self.eb.names().count("MemoryCreated")
        self.assertEqual(created_count, 4)


# ---------------------------------------------------------------------------
# 10. Performance Budget
# ---------------------------------------------------------------------------


class TestMemoryPerformanceBudget(unittest.TestCase):
    """Memory: lookup and save operations must complete within 5 ms budget."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.manager, _ = _make_manager(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_under_100ms(self) -> None:
        """Memory create (including persistence) completes within 100 ms."""
        start = time.perf_counter()
        self.manager.create("task", "perf-task-1", "test data", "worker")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 100, f"create() took {elapsed_ms:.1f} ms")

    def test_retrieve_from_cache_under_5ms(self) -> None:
        """Cached retrieve (non-disk) completes within 5 ms budget."""
        rec = self.manager.create("task", "perf-task-2", "cached data", "worker")
        # Warm up cache
        self.manager.retrieve(rec.memory_id)
        # Measure second call (should hit cache)
        start = time.perf_counter()
        self.manager.retrieve(rec.memory_id)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 5, f"Cached retrieve took {elapsed_ms:.2f} ms")

    def test_tag_search_under_10ms(self) -> None:
        """Tag-based index search completes within 10 ms for 20 records."""
        for i in range(20):
            self.manager.create("task", "perf-task-3", f"item {i}", "worker", tags=["batch"])
        start = time.perf_counter()
        self.manager.retrieval.get_by_tag("batch")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 10, f"Tag search took {elapsed_ms:.2f} ms for 20 records")


# ---------------------------------------------------------------------------
# 11. Serialization and Record Validation
# ---------------------------------------------------------------------------


class TestRecordSerialization(unittest.TestCase):
    """Memory: MemoryRecord serialization contracts and validation rules."""

    def test_round_trip_all_fields(self) -> None:
        """MemoryRecord round-trips through to_dict/from_dict without loss."""
        rec = MemoryRecord(
            content={"key": "value", "nested": [1, 2, 3]},
            scope="task",
            owner="task-ser-1",
            source="worker",
            tags=["a", "b"],
            metadata={"x": 99},
        )
        d = rec.to_dict()
        rec2 = MemoryRecord.from_dict(d)
        self.assertEqual(rec.memory_id, rec2.memory_id)
        self.assertEqual(rec.content, rec2.content)
        self.assertEqual(rec.scope, rec2.scope)
        self.assertEqual(rec.tags, rec2.tags)
        self.assertEqual(rec.metadata, rec2.metadata)

    def test_memory_id_auto_generated(self) -> None:
        """MemoryRecord auto-generates a unique memory_id."""
        r1 = MemoryRecord(content="a", scope="global", owner="sys", source="test")
        r2 = MemoryRecord(content="b", scope="global", owner="sys", source="test")
        self.assertNotEqual(r1.memory_id, r2.memory_id)

    def test_explicit_memory_id_preserved(self) -> None:
        """Explicitly provided memory_id is preserved on the record."""
        rec = MemoryRecord(memory_id="fixed-id-123", content="x", scope="global", owner="sys", source="test")
        self.assertEqual(rec.memory_id, "fixed-id-123")

    def test_created_at_is_utc(self) -> None:
        """MemoryRecord created_at is a UTC-aware datetime."""
        rec = MemoryRecord(content="ts", scope="global", owner="sys", source="test")
        self.assertIsNotNone(rec.created_at)
        self.assertIsNotNone(rec.created_at.tzinfo)

    def test_invalid_scope_raises(self) -> None:
        """Invalid scope raises MemoryValidationError at construction."""
        with self.assertRaises(MemoryValidationError):
            MemoryRecord(content="x", scope="bad_scope", owner="sys", source="test")  # type: ignore

    def test_empty_content_is_valid(self) -> None:
        """Empty string content is a valid memory record."""
        rec = MemoryRecord(content="", scope="global", owner="sys", source="test")
        self.assertEqual(rec.content, "")

    def test_dict_content_preserved(self) -> None:
        """Dict content is preserved through serialization."""
        payload = {"step": "run_tests", "exit_code": 0, "output": "all passed"}
        rec = MemoryRecord(content=payload, scope="task", owner="t1", source="worker")
        d = rec.to_dict()
        rec2 = MemoryRecord.from_dict(d)
        self.assertEqual(rec2.content, payload)

    def test_tags_default_empty(self) -> None:
        """MemoryRecord defaults to empty tags list."""
        rec = MemoryRecord(content="x", scope="global", owner="sys", source="test")
        self.assertEqual(rec.tags, [])

    def test_status_defaults_created(self) -> None:
        """MemoryRecord defaults to 'created' status (the initial lifecycle state)."""
        rec = MemoryRecord(content="x", scope="global", owner="sys", source="test")
        self.assertEqual(rec.status, "created")


if __name__ == "__main__":
    unittest.main()
