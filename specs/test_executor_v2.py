"""
Project B — Agent Execution Engine (Executor 2.0) Unit Tests
============================================================
Covers: ExecutionObserver, ExecutionResultValidator, ExecutionRepairEngine,
        AgentExecutionEngine reliability loop, automated non-LLM repairs (mkdir, fallback),
        retry logic, pre-check validation, and post-condition checks.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from execution import (
    AgentExecutionEngine,
    ExecutionEngineReport,
    ExecutionObservation,
    ExecutionObserver,
    ExecutionRepairEngine,
    ExecutionResultValidator,
)


class TestExecutionObserver(unittest.TestCase):
    """Test runtime output observation and parsing."""

    def setUp(self) -> None:
        self.observer = ExecutionObserver()

    def test_observe_success_result(self) -> None:
        raw = {"status": "SUCCESS", "stdout": "hello", "exit_code": 0}
        obs = self.observer.observe("s1", "run_command", raw, duration_ms=15.0)
        self.assertTrue(obs.is_success)
        self.assertEqual(obs.exit_code, 0)
        self.assertEqual(obs.execution_time_ms, 15.0)

    def test_observe_error_result(self) -> None:
        raw = {"status": "FAILED", "error": "Command failed", "exit_code": 1}
        obs = self.observer.observe("s1", "run_command", raw)
        self.assertFalse(obs.is_success)
        self.assertEqual(obs.error, "Command failed")

    def test_observe_exception(self) -> None:
        obs = self.observer.observe("s1", "write_file", None, exception=PermissionError("Permission denied"))
        self.assertFalse(obs.is_success)
        self.assertIn("Permission denied", obs.error)
        self.assertEqual(obs.metadata["exception_class"], "PermissionError")


class TestExecutionResultValidator(unittest.TestCase):
    """Test post-condition validation and repair strategy selection."""

    def setUp(self) -> None:
        self.validator = ExecutionResultValidator()
        self.observer = ExecutionObserver()

    def test_valid_observation_passes(self) -> None:
        obs = self.observer.observe("s1", "run_command", {"status": "SUCCESS", "exit_code": 0})
        res = self.validator.validate_observation(obs)
        self.assertTrue(res.is_valid)

    def test_missing_directory_recommends_mkdir_repair(self) -> None:
        obs = self.observer.observe("s1", "write_file", {"status": "FAILED", "error": "No such file or directory"})
        res = self.validator.validate_observation(obs)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.requires_repair)
        self.assertEqual(res.repair_strategy, "create_parent_directory")

    def test_permission_error_recommends_fallback_repair(self) -> None:
        obs = self.observer.observe("s1", "write_file", {"status": "FAILED", "error": "Permission denied"})
        res = self.validator.validate_observation(obs)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.repair_strategy, "use_fallback_directory")


class TestExecutionRepairEngine(unittest.TestCase):
    """Test deterministic local repair mechanisms."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repair = ExecutionRepairEngine()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_repair_create_parent_directory(self) -> None:
        target_path = Path(self.temp_dir.name) / "sub_dir" / "output.txt"
        self.assertFalse(target_path.parent.exists())

        inp = {"file_path": str(target_path)}
        res = self.repair.attempt_repair("create_parent_directory", "write_file", inp, "Directory missing")
        self.assertTrue(res.success)
        self.assertTrue(target_path.parent.exists())

    def test_repair_use_fallback_directory(self) -> None:
        fallback = Path(self.temp_dir.name) / "fallback"
        inp = {"file_path": "/restricted_root/calc.py"}
        res = self.repair.attempt_repair(
            "use_fallback_directory", "write_file", inp, "Permission denied", fallback_dir=fallback
        )
        self.assertTrue(res.success)
        self.assertIn(str(fallback), res.repaired_input["file_path"])


class TestAgentExecutionEngine(unittest.TestCase):
    """Test full Executor 2.0 Reliability Loop."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine = AgentExecutionEngine(max_retries=3, fallback_dir=self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_pre_check_failure_aborts_execution(self) -> None:
        step = {"step_id": "s1", "capability": "write_file", "input_data": {"file_path": "../../../etc/shadow"}}

        calls = 0
        def dummy_worker(inp: dict) -> dict:
            nonlocal calls
            calls += 1
            return {"status": "SUCCESS"}

        report = self.engine.execute_step(step, dummy_worker)
        self.assertEqual(report.status, "FAILED")
        self.assertEqual(calls, 0, "Worker must not be called if pre-check fails")
        self.assertIn("Pre-check failed", report.error)

    def test_single_pass_success(self) -> None:
        step = {"step_id": "s1", "capability": "run_command", "input_data": {"command": "echo hello"}}

        def dummy_worker(inp: dict) -> dict:
            return {"status": "SUCCESS", "stdout": "hello", "exit_code": 0}

        report = self.engine.execute_step(step, dummy_worker)
        self.assertEqual(report.status, "SUCCESS")
        self.assertEqual(report.attempts, 1)
        self.assertFalse(report.repaired)

    def test_automatic_repair_and_retry_loop(self) -> None:
        """
        REGRESSION / RELIABILITY LOOP TEST:
        Attempt 1 fails due to missing parent directory.
        Executor 2.0 repairs directory via mkdir.
        Attempt 2 succeeds.
        Report verifies status=SUCCESS, attempts=2, repaired=True.
        """
        target_file = Path(self.temp_dir.name) / "nested_dir" / "result.txt"
        step = {"step_id": "s1", "capability": "write_file", "input_data": {"file_path": str(target_file)}}

        attempts = 0
        def mock_worker(inp: dict) -> dict:
            nonlocal attempts
            attempts += 1
            p = Path(inp["file_path"])
            if not p.parent.exists():
                return {"status": "FAILED", "error": "No such file or directory"}
            p.write_text("success content")
            return {"status": "SUCCESS", "file_path": str(p)}

        report = self.engine.execute_step(step, mock_worker)
        self.assertEqual(report.status, "SUCCESS")
        self.assertEqual(report.attempts, 2)
        self.assertTrue(report.repaired)
        self.assertIn("Created missing parent directory", report.repair_summary)
        self.assertTrue(target_file.exists())

    def test_retry_exhaustion_returns_failure_report(self) -> None:
        step = {"step_id": "s1", "capability": "run_command", "input_data": {"command": "invalid"}}

        def failing_worker(inp: dict) -> dict:
            return {"status": "FAILED", "error": "Permanent failure", "exit_code": 1}

        report = self.engine.execute_step(step, failing_worker)
        self.assertEqual(report.status, "FAILED")
        self.assertEqual(report.attempts, 3)


if __name__ == "__main__":
    unittest.main()
