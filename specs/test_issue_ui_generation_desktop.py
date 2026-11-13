"""
Regression test for Issue: "create a complex UI interface Called Iris in my desktop in html"
fails write_file with "No file path provided."

Root causes:
1. "in my desktop" / "called Iris" wasn't routing to compound code-and-save in native workflow
   due to restrictive keyword checks (missing "ui", "interface", "html", etc.).
2. DAG builder _build_dag_from_analysis failed to inject file_path into write_file steps
   when LLM step_inputs omitted file_path.
3. Named entities ("called Iris") were not mapped to target filenames ("iris.html").
4. ExecutionRepairEngine had no strategy for missing file paths.
5. VALID_STEP_TRANSITIONS blocked RUNNING -> WAITING during retries.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestUIGenerationRouting:
    """Tests for routing UI and code generation requests with destination directories."""

    def setup_method(self):
        from workflow.planner import RuleBasedWorkflowPlanner
        self.planner = RuleBasedWorkflowPlanner()

    def test_create_ui_called_iris_in_desktop_in_html(self):
        """The user's prompt should route to generate_code + write_file targeting Desktop/iris.html."""
        goal = "create a complex UI interface Called Iris in my desktop in html. it is an AI interface like a chatbot interface"
        steps = self.planner.plan("wf_test", goal)
        assert len(steps) == 2
        assert steps[0].capability == "generate_code"
        assert steps[1].capability == "write_file"
        
        # Verify target file path is on Desktop and named iris.html
        write_path = steps[1].input_data.get("file_path") or steps[1].input_data.get("path")
        assert write_path is not None
        assert write_path.endswith("Desktop/iris.html")
        assert steps[1].input_data.get("content") == "Process code_gen output"
        assert steps[0].input_data.get("file_path") == write_path

    def test_eate_typo_ui_called_iris(self):
        """Even with a typo like 'eate', the combination of UI target + desktop destination routes correctly."""
        goal = "eate a complex UI interface Called Iris in my desktop in html. it is an AI interface like a chatbot interface"
        steps = self.planner.plan("wf_test_typo", goal)
        assert len(steps) == 2
        assert steps[0].capability == "generate_code"
        assert steps[1].capability == "write_file"
        write_path = steps[1].input_data.get("file_path") or steps[1].input_data.get("path")
        assert write_path is not None
        assert "Desktop" in write_path
        assert write_path.endswith(".html")

    def test_named_entity_extraction_python(self):
        """'called Calculator in python' resolves to calculator.py."""
        goal = "write a script called Calculator in my desktop in python"
        steps = self.planner.plan("wf_calc", goal)
        assert len(steps) == 2
        write_path = steps[1].input_data.get("file_path")
        assert write_path.endswith("Desktop/calculator.py")

    def test_dag_builder_injects_write_file_path(self):
        """_build_dag_from_analysis must always populate file_path and content for write_file."""
        analysis = {
            "intent": "code_gen",
            "required_capabilities": ["generate_code", "write_file"],
            "step_inputs": {
                "generate_code_0": {"prompt": "write html"},
                # write_file_1 omitted from step_inputs completely
            },
            "constraints": {"parallel": False},
        }
        goal = "build an AI dashboard in my desktop in html"
        steps = self.planner._build_dag_from_analysis("wf_dag", goal, analysis, is_simulated=False)
        assert len(steps) == 2
        write_step = steps[1]
        assert write_step.capability == "write_file"
        assert write_step.input_data.get("file_path") is not None
        assert "Desktop" in write_step.input_data["file_path"]
        assert write_step.input_data.get("content") == "Process generate_code_0 output"


class TestRepairMissingFilePath:
    """Tests for ExecutionRepairEngine's resolve_missing_file_path strategy."""

    def test_repair_missing_file_path_html(self):
        from execution.repair import ExecutionRepairEngine
        repair = ExecutionRepairEngine()
        res = repair.attempt_repair(
            strategy="resolve_missing_file_path",
            capability="write_file",
            input_data={"content": "<!DOCTYPE html><html><body><h1>Hello</h1></body></html>"},
            error_msg="No file path provided.",
        )
        assert res.success is True
        assert res.repaired_input.get("file_path") is not None
        assert res.repaired_input["file_path"].endswith(".html")

    def test_repair_missing_file_path_text(self):
        from execution.repair import ExecutionRepairEngine
        repair = ExecutionRepairEngine()
        res = repair.attempt_repair(
            strategy="resolve_missing_file_path",
            capability="write_file",
            input_data={"content": "Plain text content"},
            error_msg="No file path provided.",
        )
        assert res.success is True
        assert res.repaired_input.get("file_path") is not None
        assert res.repaired_input["file_path"].endswith(".txt")


class TestStepStateTransitions:
    """Tests for StepState transition validation during retries."""

    def test_running_to_waiting_valid(self):
        from workflow.step import StepState, validate_step_transition
        # Should not raise
        validate_step_transition(StepState.RUNNING, StepState.WAITING)

    def test_running_to_pending_valid(self):
        from workflow.step import StepState, validate_step_transition
        # Should not raise
        validate_step_transition(StepState.RUNNING, StepState.PENDING)

    def test_failed_to_pending_valid(self):
        from workflow.step import StepState, validate_step_transition
        # Should not raise
        validate_step_transition(StepState.FAILED, StepState.PENDING)
