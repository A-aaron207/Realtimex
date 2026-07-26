"""
Project C — Memory 2.0 Unit Tests
=================================
Covers: Workspace Memory (context tracking, recent files, continuation summary),
        Task Trajectory Memory (action logging, file diff snapshots, undo_task capability),
        Artifact Memory (type classification, SHA-256 checksums, metadata, artifact search),
        and MemoryManager integration.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory.artifact_memory import ArtifactMemoryStore, ArtifactRecord
from memory.manager import MemoryManager
from memory.persistence import FileMemoryPersistence
from memory.task_trajectory import TaskTrajectoryRecord, TaskTrajectoryStore
from memory.workspace import WorkspaceContext, WorkspaceMemoryStore


class TestWorkspaceMemory(unittest.TestCase):
    """Test WorkspaceContext and WorkspaceMemoryStore."""

    def test_workspace_context_initialization(self) -> None:
        ctx = WorkspaceContext(
            project_root="/home/user/projects/Realtimex",
            project_name="Realtimex",
            current_dir="/home/user/projects/Realtimex",
            git_branch="feature/memory-2.0",
        )
        self.assertEqual(ctx.project_name, "Realtimex")
        self.assertEqual(ctx.git_branch, "feature/memory-2.0")

    def test_touch_file_tracks_recent_files(self) -> None:
        ctx = WorkspaceContext(project_root="/tmp", project_name="tmp", current_dir="/tmp")
        ctx.touch_file("/tmp/calc.py", action="created")
        ctx.touch_file("/tmp/README.md", action="modified")

        self.assertEqual(len(ctx.recent_files), 2)
        self.assertIn("README.md", ctx.recent_files[0]["filename"])
        self.assertEqual(ctx.recent_files[0]["action"], "modified")

    def test_continuation_summary_narrative(self) -> None:
        ctx = WorkspaceContext(
            project_root="/home/user/Realtimex",
            project_name="Realtimex",
            current_dir="/home/user/Realtimex",
            git_branch="main",
            python_venv=".venv",
        )
        ctx.touch_file("/home/user/Realtimex/main.py", action="modified")
        summary = ctx.get_continuation_summary()
        self.assertIn("Realtimex", summary)
        self.assertIn("main", summary)
        self.assertIn("main.py", summary)

    def test_workspace_context_dict_roundtrip(self) -> None:
        ctx = WorkspaceContext(
            project_root="/tmp",
            project_name="tmp",
            current_dir="/tmp",
            git_branch="dev",
        )
        d = ctx.to_dict()
        ctx2 = WorkspaceContext.from_dict(d)
        self.assertEqual(ctx2.project_root, "/tmp")
        self.assertEqual(ctx2.git_branch, "dev")


class TestTaskTrajectoryMemory(unittest.TestCase):
    """Test TaskTrajectoryRecord and TaskTrajectoryStore including undo functionality."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_record_actions_and_files(self) -> None:
        rec = TaskTrajectoryRecord(task_id="t100", objective="Create calculator")
        rec.record_action("s1", "write_file", {"file_path": "calc.py"}, {"status": "SUCCESS"})
        rec.record_file_creation("/tmp/calc.py")
        rec.record_file_modification("/tmp/README.md", previous_content="# Old Title")

        self.assertEqual(len(rec.actions_executed), 1)
        self.assertEqual(len(rec.created_files), 1)
        self.assertEqual(len(rec.modified_files), 1)

    def test_undo_task_deletes_created_and_restores_modified(self) -> None:
        store = TaskTrajectoryStore()
        rec = store.start_task("t101", "Create & modify files")

        # Create physical test files
        created_file = Path(self.temp_dir.name) / "new_file.txt"
        modified_file = Path(self.temp_dir.name) / "existing_file.txt"

        created_file.write_text("i am new")
        modified_file.write_text("original content")

        rec.record_file_creation(str(created_file))
        rec.record_file_modification(str(modified_file), previous_content="original content")

        # Modify the existing file to simulate task modification
        modified_file.write_text("modified by task")

        # Execute Undo
        undo_res = store.undo_task("t101")
        self.assertEqual(undo_res["status"], "SUCCESS")

        # Created file must be deleted
        self.assertFalse(created_file.exists())

        # Modified file must be restored to original content
        self.assertEqual(modified_file.read_text(), "original content")


class TestArtifactMemory(unittest.TestCase):
    """Test ArtifactRecord and ArtifactMemoryStore."""

    def test_register_and_checksum_artifact(self) -> None:
        store = ArtifactMemoryStore()
        code_content = "def add(a, b):\n    return a + b"
        art = store.register_artifact(
            artifact_id="art-1",
            artifact_type="code",
            file_path="/tmp/calculator.py",
            name="calculator.py",
            task_id="t200",
            content=code_content,
        )
        self.assertEqual(art.artifact_type, "code")
        self.assertGreater(len(art.checksum), 0)

    def test_query_artifacts_by_type(self) -> None:
        store = ArtifactMemoryStore()
        store.register_artifact("a1", "code", "/tmp/a.py", task_id="t1")
        store.register_artifact("a2", "html", "/tmp/b.html", task_id="t1")
        store.register_artifact("a3", "code", "/tmp/c.py", task_id="t2")

        code_arts = store.list_artifacts(artifact_type="code")
        self.assertEqual(len(code_arts), 2)

        t1_arts = store.list_artifacts(task_id="t1")
        self.assertEqual(len(t1_arts), 2)


class TestMemoryManagerIntegrationV2(unittest.TestCase):
    """Test MemoryManager integrating Memory 2.0 stores."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.persistence = FileMemoryPersistence(directory=Path(self.temp_dir.name))
        self.manager = MemoryManager(persistence=self.persistence)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_memory_manager_has_v2_stores(self) -> None:
        self.assertIsInstance(self.manager.workspace_store, WorkspaceMemoryStore)
        self.assertIsInstance(self.manager.trajectory_store, TaskTrajectoryStore)
        self.assertIsInstance(self.manager.artifact_store, ArtifactMemoryStore)


if __name__ == "__main__":
    unittest.main()
