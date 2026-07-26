"""
Project A — Planner 2.0 Architecture Unit Tests
=================================================
Covers: GoalGraph decomposition, DAG dependency validation, topological ordering,
        ActionValidator pre-action checks, unresolved {{variable}} tag detection,
        confidence score threshold enforcement, path traversal & safety checks,
        auto-replanning workflows, and CognitivePlanner integration.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from cognitive.action_validator import ActionValidator, ActionValidationError, ValidationResult
from cognitive.engine import CognitiveEngine
from cognitive.goal_graph import GoalGraph, GoalNode
from cognitive.planner import CognitivePlanner
from cognitive.reasoning import MockReasoningProvider


class DummyTask:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.goal = "test"
        self.state = "RUNNING"
        self.metadata: dict = {}

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "goal": self.goal, "state": self.state, "metadata": self.metadata}


class DummyTaskManager:
    def get_task(self, task_id: str) -> Any:
        return DummyTask(task_id)


class DummyWM:
    def load_workflow(self, wf_id: str) -> None:
        raise KeyError(wf_id)


class DummyEventManager:
    def filter_events(self, task_id: str) -> list:
        return []


def _engine() -> CognitiveEngine:
    return CognitiveEngine(
        reasoning_provider=MockReasoningProvider(),
        task_manager=DummyTaskManager(),
        workflow_manager=DummyWM(),
        event_manager=DummyEventManager(),
    )


# ---------------------------------------------------------------------------
# 1. GoalGraph Tests
# ---------------------------------------------------------------------------

class TestGoalGraph(unittest.TestCase):
    """Test GoalNode and GoalGraph decomposition and ordering."""

    def test_goal_node_creation_and_dict(self) -> None:
        node = GoalNode(
            goal_id="g1",
            description="Test goal",
            dependencies=[],
            required_inputs=["in1"],
            produced_outputs=["out1"],
            capability="write_file",
        )
        self.assertEqual(node.goal_id, "g1")
        self.assertEqual(node.status, "PENDING")
        d = node.to_dict()
        node2 = GoalNode.from_dict(d)
        self.assertEqual(node2.goal_id, "g1")
        self.assertEqual(node2.capability, "write_file")

    def test_goal_graph_dag_validation_valid(self) -> None:
        graph = GoalGraph("Test Objective")
        graph.add_node(GoalNode(goal_id="g1", description="Step 1"))
        graph.add_node(GoalNode(goal_id="g2", description="Step 2", dependencies=["g1"]))
        self.assertTrue(graph.validate_dag())

    def test_goal_graph_dag_validation_circular_raises(self) -> None:
        graph = GoalGraph("Circular Objective")
        graph.add_node(GoalNode(goal_id="g1", description="Step 1", dependencies=["g2"]))
        graph.add_node(GoalNode(goal_id="g2", description="Step 2", dependencies=["g1"]))
        with self.assertRaises(Exception):
            graph.validate_dag()

    def test_goal_graph_executable_nodes(self) -> None:
        graph = GoalGraph("Exec Test")
        n1 = GoalNode(goal_id="g1", description="Step 1", status="RESOLVED")
        n2 = GoalNode(goal_id="g2", description="Step 2", dependencies=["g1"], status="PENDING")
        n3 = GoalNode(goal_id="g3", description="Step 3", dependencies=["g2"], status="PENDING")
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        executable = graph.get_executable_nodes()
        self.assertEqual(len(executable), 1)
        self.assertEqual(executable[0].goal_id, "g2")

    def test_goal_graph_topological_sort(self) -> None:
        graph = GoalGraph("Sort Test")
        graph.add_node(GoalNode(goal_id="g1", description="Step 1"))
        graph.add_node(GoalNode(goal_id="g2", description="Step 2", dependencies=["g1"]))
        graph.add_node(GoalNode(goal_id="g3", description="Step 3", dependencies=["g2"]))

        order = graph.topological_sort()
        ids = [n.goal_id for n in order]
        self.assertEqual(ids, ["g1", "g2", "g3"])

    def test_decompose_objective_file_write(self) -> None:
        graph = GoalGraph.decompose_objective("Write python calculator code to desktop/calc.py")
        self.assertIn("g1_resolve_path", graph.nodes)
        self.assertIn("g2_prepare_content", graph.nodes)
        self.assertIn("g3_execute_write", graph.nodes)

    def test_decompose_objective_search(self) -> None:
        graph = GoalGraph.decompose_objective("Search for quantum computing algorithms")
        self.assertIn("g1_query_formulation", graph.nodes)
        self.assertIn("g2_execute_search", graph.nodes)
        self.assertIn("g3_synthesize_results", graph.nodes)


# ---------------------------------------------------------------------------
# 2. ActionValidator Tests
# ---------------------------------------------------------------------------

class TestActionValidator(unittest.TestCase):
    """Test pre-execution action validation checks."""

    def setUp(self) -> None:
        self.validator = ActionValidator(min_confidence_threshold=0.70)

    def test_valid_action_passes(self) -> None:
        step = {"step_id": "s1", "capability": "write_file", "input_data": {"file_path": "logs/calc.py"}}
        res = self.validator.validate_action(step, confidence_score=0.95)
        self.assertTrue(res.is_valid)

    def test_low_confidence_triggers_replan(self) -> None:
        step = {"step_id": "s1", "capability": "run_command"}
        res = self.validator.validate_action(step, confidence_score=0.50)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.should_replan)
        self.assertIn("confidence score", res.reason)

    def test_unresolved_variable_fails(self) -> None:
        step = {
            "step_id": "s1",
            "capability": "write_file",
            "input_data": {"file_path": "{{workspace_path}}/calc.py", "content": "print(1)"}
        }
        res = self.validator.validate_action(step)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.should_replan)
        self.assertIn("workspace_path", res.details["unresolved_variables"])

    def test_unavailable_capability_fails(self) -> None:
        step = {"step_id": "s1", "capability": "unsupported_tool"}
        res = self.validator.validate_action(step, available_capabilities=["read_file", "write_file"])
        self.assertFalse(res.is_valid)
        self.assertTrue(res.should_replan)

    def test_path_traversal_fails(self) -> None:
        step = {"step_id": "s1", "capability": "write_file", "input_data": {"file_path": "../../../etc/passwd"}}
        res = self.validator.validate_action(step)
        self.assertFalse(res.is_valid)
        self.assertFalse(res.should_replan)
        self.assertIn("path traversal", res.reason)

    def test_disallowed_system_path_fails(self) -> None:
        step = {"step_id": "s1", "capability": "write_file", "input_data": {"file_path": "/etc/shadow"}}
        res = self.validator.validate_action(step)
        self.assertFalse(res.is_valid)
        self.assertIn("system directory", res.reason)

    def test_non_existent_read_file_fails(self) -> None:
        step = {"step_id": "s1", "capability": "read_file", "input_data": {"file_path": "/tmp/non_existent_file_xyz.txt"}}
        res = self.validator.validate_action(step)
        self.assertFalse(res.is_valid)
        self.assertTrue(res.should_replan)


# ---------------------------------------------------------------------------
# 3. CognitivePlanner 2.0 Integration Tests
# ---------------------------------------------------------------------------

class TestCognitivePlannerV2(unittest.TestCase):
    """Test CognitivePlanner 2.0 goal graph and replanning integration."""

    def setUp(self) -> None:
        self.engine = _engine()
        self.planner = CognitivePlanner(self.engine)

    def test_plan_with_goal_graph_returns_graph(self) -> None:
        resp, graph = self.planner.plan_with_goal_graph("t1", "Write a python calculator script")
        self.assertIsNotNone(resp)
        self.assertIsInstance(graph, GoalGraph)
        self.assertIn("g1_resolve_path", graph.nodes)

    def test_planner_validate_action(self) -> None:
        step = {"step_id": "s1", "capability": "run_command", "input_data": {"command": "echo 123"}}
        res = self.planner.validate_action(step, confidence_score=0.90)
        self.assertTrue(res.is_valid)

    def test_replan_on_failure(self) -> None:
        failed_step = {"step_id": "s2", "capability": "write_file", "input_data": {"file_path": "/etc/config"}}
        resp = self.planner.replan_on_failure(
            task_id="t1",
            objective="Configure app",
            failed_step=failed_step,
            failure_reason="Restricted system path",
        )
        self.assertIsNotNone(resp)


if __name__ == "__main__":
    unittest.main()
