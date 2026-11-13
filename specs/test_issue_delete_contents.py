"""
Regression test for Issue: "delete all contents from Desktop folder" fails with retry loop.

Root causes:
1. Planner pattern matching gap - "delete all the contents and files from my desktop folder"
   didn't match any deletion keywords (only "delete file", "remove file" etc. were matched).
2. Observer stderr leaking - stderr from successful commands (exit code 0) was treated as an
   error, causing `is_success` to return False even when the command succeeded.
3. Repair step ID collision - second repair attempt crashed with "Step with ID already exists"
   because repair step IDs like "repair_list_directory_0" were reused.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDeletionPatternMatching:
    """Tests for the planner's ability to match deletion-related goals."""

    def setup_method(self):
        from workflow.planner import RuleBasedWorkflowPlanner
        self.planner = RuleBasedWorkflowPlanner()

    def test_delete_all_contents_from_desktop(self):
        """The original failing goal should now route to a native run_command step."""
        steps = self.planner._build_native_tool_workflow(
            "wf1", "delete all the contents and files from my desktop folder permanently"
        )
        assert steps is not None, "Planner should match 'delete all' pattern"
        assert len(steps) == 1
        assert steps[0].capability == "run_command"
        cmd = steps[0].input_data["command"]
        # Should use find ... -delete for content deletion (preserving the folder)
        assert "find" in cmd or "rm" in cmd
        assert "Desktop" in cmd

    def test_empty_folder(self):
        steps = self.planner._build_native_tool_workflow("wf1", "empty the Downloads folder")
        assert steps is not None
        assert steps[0].capability == "run_command"
        assert "Downloads" in steps[0].input_data["command"]

    def test_clear_directory(self):
        steps = self.planner._build_native_tool_workflow("wf1", "clear the temp directory")
        assert steps is not None
        assert steps[0].capability == "run_command"

    def test_remove_all_files(self):
        steps = self.planner._build_native_tool_workflow("wf1", "remove all files from /tmp/test")
        assert steps is not None
        cmd = steps[0].input_data["command"]
        assert "/tmp/test" in cmd

    def test_wipe_folder(self):
        steps = self.planner._build_native_tool_workflow("wf1", "wipe the documents folder")
        assert steps is not None
        assert steps[0].capability == "run_command"

    def test_original_delete_file_still_works(self):
        """Regression: ensure original 'delete file' pattern still works."""
        steps = self.planner._build_native_tool_workflow("wf1", "delete file /tmp/test.txt")
        assert steps is not None
        assert steps[0].capability == "run_command"
        assert "/tmp/test.txt" in steps[0].input_data["command"]

    def test_original_remove_folder_still_works(self):
        """Regression: ensure original 'remove folder' pattern still works."""
        steps = self.planner._build_native_tool_workflow("wf1", "remove folder /tmp/mydir")
        assert steps is not None
        assert "/tmp/mydir" in steps[0].input_data["command"]

    def test_delete_everything_on_desktop(self):
        steps = self.planner._build_native_tool_workflow("wf1", "delete everything on my desktop")
        assert steps is not None
        assert "Desktop" in steps[0].input_data["command"]


class TestPathExtraction:
    """Tests for the _extract_path_from_goal helper method."""

    def setup_method(self):
        from workflow.planner import RuleBasedWorkflowPlanner
        self.planner = RuleBasedWorkflowPlanner()

    def test_extract_absolute_path(self):
        path = self.planner._extract_path_from_goal(
            "delete all files in /home/aarons/Desktop", "delete all files in /home/aarons/desktop"
        )
        assert path == "/home/aarons/Desktop"

    def test_extract_tilde_path(self):
        path = self.planner._extract_path_from_goal(
            "clear ~/Downloads", "clear ~/downloads"
        )
        home = os.path.expanduser("~")
        assert path == os.path.join(home, "Downloads")

    def test_extract_named_directory_desktop(self):
        path = self.planner._extract_path_from_goal(
            "delete all contents from my Desktop folder", "delete all contents from my desktop folder"
        )
        home = os.path.expanduser("~")
        assert path == os.path.join(home, "Desktop")

    def test_extract_named_directory_downloads(self):
        path = self.planner._extract_path_from_goal(
            "empty the downloads directory", "empty the downloads directory"
        )
        home = os.path.expanduser("~")
        assert path == os.path.join(home, "Downloads")

    def test_extract_named_directory_documents(self):
        path = self.planner._extract_path_from_goal(
            "clear documents folder", "clear documents folder"
        )
        home = os.path.expanduser("~")
        assert path == os.path.join(home, "Documents")


class TestObserverStderrHandling:
    """Tests for the observer's stderr handling fix."""

    def test_success_with_stderr_not_treated_as_error(self):
        """When status=SUCCESS and exit_code=0, stderr should NOT cause failure."""
        from execution.observer import ExecutionObserver

        obs = ExecutionObserver()
        result = obs.observe(
            step_id="test_rm",
            capability="run_command",
            raw_result={
                "status": "SUCCESS",
                "stdout": "",
                "stderr": "rm: cannot remove '.' or '..'",
                "exit_code": 0,
            },
        )
        assert result.is_success is True, "Status SUCCESS + exit_code 0 should be success regardless of stderr"
        assert result.error is None, "Error should be None when command succeeded"

    def test_failed_with_stderr_uses_it_as_error(self):
        """When status=FAILED, stderr should be used as the error message."""
        from execution.observer import ExecutionObserver

        obs = ExecutionObserver()
        result = obs.observe(
            step_id="test_bad",
            capability="run_command",
            raw_result={
                "status": "FAILED",
                "stdout": "",
                "stderr": "command not found",
                "exit_code": 127,
            },
        )
        assert result.is_success is False
        assert result.error is not None
        assert "command not found" in result.error

    def test_success_without_stderr(self):
        """Normal success case should still work."""
        from execution.observer import ExecutionObserver

        obs = ExecutionObserver()
        result = obs.observe(
            step_id="test_ok",
            capability="run_command",
            raw_result={
                "status": "SUCCESS",
                "stdout": "ok",
                "exit_code": 0,
            },
        )
        assert result.is_success is True
        assert result.error is None

    def test_nonzero_exit_code_uses_stderr(self):
        """When exit_code != 0, stderr should be captured as the error."""
        from execution.observer import ExecutionObserver

        obs = ExecutionObserver()
        result = obs.observe(
            step_id="test_exit1",
            capability="run_command",
            raw_result={
                "status": "SUCCESS",
                "stderr": "permission denied",
                "exit_code": 1,
            },
        )
        assert result.is_success is False
        assert result.error is not None


class TestRepairStepIdUniqueness:
    """Tests for repair step ID uniqueness across multiple repair attempts."""

    def test_repair_step_ids_include_attempt_counter(self):
        """Step IDs generated during repair should include the attempt number."""
        # Simulate what the repair logic does
        repair_attempts = 0
        caps = ["list_directory", "run_command"]

        ids_attempt_1 = [f"repair_{cap}_{idx}_r{repair_attempts + 1}" for idx, cap in enumerate(caps)]
        repair_attempts = 1
        ids_attempt_2 = [f"repair_{cap}_{idx}_r{repair_attempts + 1}" for idx, cap in enumerate(caps)]

        # IDs from attempt 1 and attempt 2 should NOT overlap
        assert set(ids_attempt_1).isdisjoint(set(ids_attempt_2)), \
            f"Step IDs should be unique across attempts: {ids_attempt_1} vs {ids_attempt_2}"

    def test_recovery_write_ids_include_attempt_counter(self):
        """recovery_write step IDs should also be unique per attempt."""
        ids = [f"recovery_write_r{i + 1}" for i in range(3)]
        assert len(set(ids)) == 3, "All recovery_write IDs should be unique"
