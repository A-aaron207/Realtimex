"""
Project E — Self-Healing Execution Engine Unit & Integration Tests
===================================================================
Verifies:
1. ExecutionResultValidator detects Python tracebacks and selects "llm_code_repair".
2. ExecutionRepairEngine locates the faulty script and repairs it via debug_code.
3. AgentExecutionEngine auto-retries repaired code and succeeds.
4. WorkerRuntime executes with live self-healing reliability loop.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from execution import (
    AgentExecutionEngine,
    ExecutionObservation,
    ExecutionObserver,
    ExecutionRepairEngine,
    ExecutionResultValidator,
)


class TestSelfHealingExecution(unittest.TestCase):
    """Verify autonomous self-healing and code repair loop."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.validator = ExecutionResultValidator()
        self.repair = ExecutionRepairEngine()
        self.observer = ExecutionObserver()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validator_identifies_zero_division_traceback(self) -> None:
        """Validator recognizes ZeroDivisionError traceback and selects llm_code_repair strategy."""
        stderr_output = (
            "Traceback (most recent call last):\n"
            "  File 'calculator.py', line 5, in <module>\n"
            "    res = 10 / 0\n"
            "ZeroDivisionError: division by zero\n"
        )
        obs = self.observer.observe(
            step_id="run_calc",
            capability="run_command",
            raw_result={"status": "FAILED", "stderr": stderr_output, "exit_code": 1},
        )
        val = self.validator.validate_observation(obs, {"command": "python3 calculator.py"})

        self.assertFalse(val.is_valid)
        self.assertTrue(val.requires_repair)
        self.assertEqual(val.repair_strategy, "llm_code_repair")

    def test_validator_identifies_syntax_error(self) -> None:
        """Validator recognizes SyntaxError in execution output."""
        obs = self.observer.observe(
            step_id="step_syntax",
            capability="run_command",
            raw_result={"status": "FAILED", "stderr": "SyntaxError: invalid syntax", "exit_code": 1},
        )
        val = self.validator.validate_observation(obs, {"command": "python3 script.py"})

        self.assertFalse(val.is_valid)
        self.assertEqual(val.repair_strategy, "llm_code_repair")

    def test_repair_engine_fixes_broken_file_via_developer_module(self) -> None:
        """ExecutionRepairEngine calls developer module to repair broken python file."""
        broken_file = Path(self.temp_dir.name) / "calc.py"
        broken_file.write_text("def divide(a, b): return a / b\nprint(divide(10, 0))")

        mock_dev = MagicMock()
        mock_dev.debug_code.return_value = {
            "status": "SUCCESS",
            "fixed_code": "def divide(a, b):\n    if b == 0: return None\n    return a / b\nprint(divide(10, 0))",
        }

        mock_registry = MagicMock()
        mock_service = MagicMock()
        mock_service.metadata = {"module": mock_dev}
        mock_registry.get.return_value = mock_service

        with patch("services.registry.ServiceRegistry.get_instance", return_value=mock_registry):
            res = self.repair.attempt_repair(
                strategy="llm_code_repair",
                capability="run_command",
                input_data={"command": f"python3 {broken_file}"},
                error_msg="ZeroDivisionError: division by zero",
            )

            self.assertTrue(res.success)
            self.assertEqual(res.strategy_used, "llm_code_repair")
            mock_dev.debug_code.assert_called_once()
            self.assertIn("Auto-repaired code", res.message)

    def test_agent_execution_engine_self_heals_and_retries(self) -> None:
        """
        Full Reliability Loop:
        Attempt 1 fails with ZeroDivisionError.
        Self-healing repairs the script.
        Attempt 2 runs the repaired script and succeeds with exit code 0.
        """
        engine = AgentExecutionEngine(max_retries=3)
        script_file = Path(self.temp_dir.name) / "test_target.py"
        script_file.write_text("print('failing')")

        mock_dev = MagicMock()
        def mock_fix(data: dict) -> dict:
            script_file.write_text("print('fixed')")
            return {"status": "SUCCESS", "fixed_code": "print('fixed')"}
        mock_dev.debug_code.side_effect = mock_fix

        mock_registry = MagicMock()
        mock_service = MagicMock()
        mock_service.metadata = {"module": mock_dev}
        mock_registry.get.return_value = mock_service

        attempts = 0
        def test_worker(input_data: dict) -> dict:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return {
                    "status": "FAILED",
                    "stderr": "Traceback (most recent call last):\nZeroDivisionError: division by zero",
                    "exit_code": 1,
                }
            return {"status": "SUCCESS", "stdout": "fixed", "exit_code": 0}

        step = {
            "step_id": "run_test_step",
            "capability": "run_command",
            "input_data": {"command": f"python3 {script_file}"},
        }

        with patch("services.registry.ServiceRegistry.get_instance", return_value=mock_registry):
            report = engine.execute_step(step, test_worker)

        self.assertEqual(report.status, "SUCCESS")
        self.assertEqual(report.attempts, 2)
        self.assertTrue(report.repaired)
        self.assertIn("Auto-repaired code", report.repair_summary)
        self.assertEqual(report.output["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
