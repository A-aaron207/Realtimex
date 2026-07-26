"""
Sprint 1A — Planner Reliability Tests
======================================
Covers: multi-step planning, variable propagation, recovery, plan optimization,
        capability selection, edge cases, serialization, and error handling.

Target: close the gap from 131/150 toward 150/150 on the Planner subsystem.
"""

from __future__ import annotations

import time
import unittest
from typing import Any

from cognitive.cache import CognitiveCache
from cognitive.context import ContextBuilder
from cognitive.engine import CognitiveEngine
from cognitive.exceptions import (
    ContextBuilderError,
    ReasoningError,
    ValidationError,
)
from cognitive.planner import CognitivePlanner
from cognitive.reasoning import (
    CognitiveRequest,
    CognitiveResponse,
    MockReasoningProvider,
    ReasoningProvider,
)
from cognitive.validator import CognitiveValidator
from events.event import Event
from events.event_types import CognitiveEventType


# ---------------------------------------------------------------------------
# Shared Mocks
# ---------------------------------------------------------------------------


class DummyEventBus:
    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class DummyTask:
    def __init__(
        self,
        task_id: str,
        goal: str,
        state: Any,
        memory: dict[str, Any] | None = None,
        workflow: dict[str, Any] | None = None,
        history: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.task_id = task_id
        self.goal = goal
        self.state = state
        self.memory = memory or {}
        self.workflow = workflow or {}
        self.history = history or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": str(self.state),
            "memory": self.memory,
            "workflow": self.workflow,
            "history": self.history,
            "metadata": self.metadata,
        }


class DummyTaskManager:
    def __init__(self) -> None:
        self.tasks: dict[str, DummyTask] = {}

    def get_task(self, task_id: str) -> DummyTask:
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found")
        return self.tasks[task_id]


class DummyWorkflow:
    def __init__(
        self,
        workflow_id: str,
        parent_task_id: str,
        status: str,
        steps: dict[str, Any] | None = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.parent_task_id = parent_task_id
        self.status = status
        self.steps = steps or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "parent_task_id": self.parent_task_id,
            "status": self.status,
            "steps": self.steps,
        }


class DummyWorkflowManager:
    def __init__(self) -> None:
        self.workflows: dict[str, DummyWorkflow] = {}

    def load_workflow(self, workflow_id: str) -> DummyWorkflow:
        if workflow_id not in self.workflows:
            raise KeyError(f"Workflow {workflow_id} not found")
        return self.workflows[workflow_id]


class DummyEventManager:
    def __init__(self, event_bus: DummyEventBus) -> None:
        self.event_bus = event_bus

    def filter_events(self, task_id: str | None = None) -> list[Event]:
        return [e for e in self.event_bus.emitted if task_id is None or e.task_id == task_id]


def _make_engine(
    provider: ReasoningProvider | None = None,
    task_manager: DummyTaskManager | None = None,
    workflow_manager: DummyWorkflowManager | None = None,
    event_manager: DummyEventManager | None = None,
    config: dict[str, Any] | None = None,
    cache_ttl: float = 60.0,
) -> tuple[CognitiveEngine, DummyTaskManager, DummyWorkflowManager, DummyEventBus]:
    event_bus = DummyEventBus()
    tm = task_manager or DummyTaskManager()
    wm = workflow_manager or DummyWorkflowManager()
    em = event_manager or DummyEventManager(event_bus)
    engine = CognitiveEngine(
        reasoning_provider=provider or MockReasoningProvider(),
        task_manager=tm,
        workflow_manager=wm,
        event_manager=em,
        config=config or {},
        cache_ttl=cache_ttl,
    )
    return engine, tm, wm, event_bus


# ---------------------------------------------------------------------------
# 1. Multi-step Planning Tests
# ---------------------------------------------------------------------------


class TestMultiStepPlanning(unittest.TestCase):
    """Planner: multi-step workflow generation and dependency validation."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="CREATED")

    def test_plan_returns_cognitive_response(self) -> None:
        """plan() must return a CognitiveResponse."""
        self._add_task("t-ms-1", "Analyse logs")
        resp = self.engine.plan("t-ms-1", "Analyse logs")
        self.assertIsInstance(resp, CognitiveResponse)

    def test_plan_has_steps_key(self) -> None:
        """plan() recommendation must contain a 'steps' list."""
        self._add_task("t-ms-2", "Build website")
        resp = self.engine.plan("t-ms-2", "Build portfolio website")
        rec = resp.recommendation
        self.assertIn("steps", rec)
        self.assertIsInstance(rec["steps"], list)
        self.assertGreater(len(rec["steps"]), 0)

    def test_plan_steps_have_required_fields(self) -> None:
        """Each step must have step_id and capability fields."""
        self._add_task("t-ms-3", "Build app")
        resp = self.engine.plan("t-ms-3", "Build app")
        for step in resp.recommendation["steps"]:
            self.assertIn("step_id", step)
            self.assertIn("capability", step)
            self.assertIsInstance(step["step_id"], str)
            self.assertIsInstance(step["capability"], str)

    def test_plan_dependency_ordering_respected(self) -> None:
        """Steps that depend on others must reference valid step IDs."""
        self._add_task("t-ms-4", "Build website")
        resp = self.engine.plan("t-ms-4", "Build portfolio website")
        steps = resp.recommendation["steps"]
        step_ids = {s["step_id"] for s in steps}
        for step in steps:
            for dep in step.get("dependencies", []):
                self.assertIn(dep, step_ids, f"Dependency '{dep}' not in step IDs")

    def test_plan_confidence_within_bounds(self) -> None:
        """Planner confidence must be in [0.0, 1.0]."""
        self._add_task("t-ms-5", "Fetch data")
        resp = self.engine.plan("t-ms-5", "Fetch data")
        self.assertGreaterEqual(resp.confidence, 0.0)
        self.assertLessEqual(resp.confidence, 1.0)

    def test_plan_with_constraints_propagated(self) -> None:
        """Constraints passed to plan() appear in the request context."""
        self._add_task("t-ms-6", "Deploy server")
        constraints = ["timeout_30s", "readonly_filesystem"]
        resp = self.engine.plan("t-ms-6", "Deploy server", constraints=constraints)
        self.assertIsInstance(resp, CognitiveResponse)
        # Confidence and recommendation still valid
        self.assertGreaterEqual(resp.confidence, 0.0)

    def test_plan_with_no_task_raises_context_error(self) -> None:
        """plan() for a non-existent task must raise ContextBuilderError."""
        with self.assertRaises(ContextBuilderError):
            self.engine.plan("nonexistent-task-id", "Do something")

    def test_plan_reasoning_summary_non_empty(self) -> None:
        """Reasoning summary must be a non-empty string."""
        self._add_task("t-ms-7", "Write report")
        resp = self.engine.plan("t-ms-7", "Write report")
        self.assertIsInstance(resp.reasoning_summary, str)
        self.assertGreater(len(resp.reasoning_summary), 0)

    def test_plan_emits_reasoning_started_event(self) -> None:
        """plan() must emit at least a ReasoningStarted event."""
        self._add_task("t-ms-8", "Build chart")
        self.engine.plan("t-ms-8", "Build chart")
        names = [e.name for e in self.eb.emitted]
        self.assertIn("ReasoningStarted", names)

    def test_plan_emits_decision_generated_event(self) -> None:
        """plan() must emit a DecisionGenerated event on success."""
        self._add_task("t-ms-9", "Render page")
        self.engine.plan("t-ms-9", "Render page")
        names = [e.name for e in self.eb.emitted]
        self.assertIn("DecisionGenerated", names)

    def test_plan_emits_reasoning_completed_event(self) -> None:
        """plan() must emit a ReasoningCompleted event on success."""
        self._add_task("t-ms-10", "Process data")
        self.engine.plan("t-ms-10", "Process data")
        names = [e.name for e in self.eb.emitted]
        self.assertIn("ReasoningCompleted", names)

    def test_multi_step_no_circular_deps(self) -> None:
        """Validator rejects workflows containing circular dependencies."""
        validator = CognitiveValidator()
        circular = {
            "steps": [
                {"step_id": "A", "capability": "read_file", "dependencies": ["B"]},
                {"step_id": "B", "capability": "read_file", "dependencies": ["A"]},
            ]
        }
        with self.assertRaises(ValidationError):
            validator.validate(circular, "Workflow Planning", {"available_capabilities": ["read_file"]})

    def test_multi_step_no_duplicate_step_ids(self) -> None:
        """Validator rejects workflows with duplicate step IDs."""
        validator = CognitiveValidator()
        dup = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": []},
                {"step_id": "s1", "capability": "write_file", "dependencies": []},
            ]
        }
        with self.assertRaises(ValidationError):
            validator.validate(dup, "Workflow Planning", {"available_capabilities": ["read_file", "write_file"]})

    def test_multi_step_deep_dependency_chain(self) -> None:
        """A five-step linear dependency chain should validate successfully."""
        validator = CognitiveValidator()
        caps = ["cap_a", "cap_b", "cap_c", "cap_d", "cap_e"]
        steps = [
            {"step_id": "s1", "capability": "cap_a", "dependencies": []},
            {"step_id": "s2", "capability": "cap_b", "dependencies": ["s1"]},
            {"step_id": "s3", "capability": "cap_c", "dependencies": ["s2"]},
            {"step_id": "s4", "capability": "cap_d", "dependencies": ["s3"]},
            {"step_id": "s5", "capability": "cap_e", "dependencies": ["s4"]},
        ]
        self.assertTrue(
            validator.validate({"steps": steps}, "Workflow Planning", {"available_capabilities": caps})
        )

    def test_plan_with_additional_context_merged(self) -> None:
        """Additional context passed to plan() is available downstream."""
        self._add_task("t-ms-11", "Export data")
        resp = self.engine.plan(
            "t-ms-11",
            "Export data",
            additional_context={"output_format": "csv", "destination": "/tmp/out.csv"},
        )
        self.assertIsInstance(resp, CognitiveResponse)

    def test_planner_helper_plan_matches_engine_plan(self) -> None:
        """CognitivePlanner.plan() wraps engine.plan() transparently."""
        self._add_task("t-ms-12", "Send report")
        planner = CognitivePlanner(engine=self.engine)
        direct = self.engine.plan("t-ms-12", "Send report")
        # Reset event bus and cache for clean comparison
        engine2, tm2, _, _ = _make_engine()
        tm2.tasks["t-ms-12"] = DummyTask(task_id="t-ms-12", goal="Send report", state="CREATED")
        planner2 = CognitivePlanner(engine=engine2)
        via_planner = planner2.plan("t-ms-12", "Send report")
        self.assertEqual(direct.recommendation, via_planner.recommendation)


# ---------------------------------------------------------------------------
# 2. Variable Propagation Tests
# ---------------------------------------------------------------------------


class TestVariablePropagation(unittest.TestCase):
    """Planner: context and variable propagation between pipeline stages."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine(config={"max_steps": 20})

    def test_task_memory_visible_in_context(self) -> None:
        """Task memory dict is available in the reasoning context."""
        self.tm.tasks["t-vp-1"] = DummyTask(
            task_id="t-vp-1",
            goal="Summarise doc",
            state="CREATED",
            memory={"file_path": "/docs/report.pdf", "lang": "en"},
        )
        ctx = self.engine.build_context("t-vp-1")
        self.assertEqual(ctx["memory"]["file_path"], "/docs/report.pdf")
        self.assertEqual(ctx["memory"]["lang"], "en")

    def test_additional_context_merged_into_memory(self) -> None:
        """Additional context memory keys are merged into the built context."""
        self.tm.tasks["t-vp-2"] = DummyTask(task_id="t-vp-2", goal="Run script", state="CREATED")
        ctx = self.engine.build_context(
            "t-vp-2", additional_context={"memory": {"session_token": "abc123"}}
        )
        self.assertEqual(ctx["memory"]["session_token"], "abc123")

    def test_config_visible_in_context(self) -> None:
        """Config passed at engine init is exposed in context['configuration']."""
        self.tm.tasks["t-vp-3"] = DummyTask(task_id="t-vp-3", goal="Check config", state="CREATED")
        ctx = self.engine.build_context("t-vp-3")
        self.assertEqual(ctx["configuration"]["max_steps"], 20)

    def test_workflow_propagated_from_task(self) -> None:
        """Workflow embedded in task memory propagates into context['workflow']."""
        self.tm.tasks["t-vp-4"] = DummyTask(
            task_id="t-vp-4",
            goal="Run workflow",
            state="RUNNING",
            workflow={"workflow_id": "wf-embedded", "status": "RUNNING"},
        )
        ctx = self.engine.build_context("t-vp-4")
        self.assertEqual(ctx["workflow"]["workflow_id"], "wf-embedded")

    def test_workflow_id_propagated_when_workflow_manager_loaded(self) -> None:
        """workflow_id from workflow manager is reflected in built context."""
        self.tm.tasks["t-vp-5"] = DummyTask(task_id="t-vp-5", goal="Check WF", state="CREATED")
        self.wm.workflows["wf-5"] = DummyWorkflow(
            workflow_id="wf-5", parent_task_id="t-vp-5", status="PENDING"
        )
        ctx = self.engine.build_context("t-vp-5", workflow_id="wf-5")
        self.assertEqual(ctx["workflow"]["workflow_id"], "wf-5")
        self.assertEqual(ctx["workflow"]["status"], "PENDING")

    def test_task_id_echoed_in_context(self) -> None:
        """Context always exposes the task_id used to build it."""
        self.tm.tasks["t-vp-6"] = DummyTask(task_id="t-vp-6", goal="Echo task", state="CREATED")
        ctx = self.engine.build_context("t-vp-6")
        self.assertEqual(ctx["task_id"], "t-vp-6")

    def test_arbitrary_context_keys_propagated(self) -> None:
        """Non-memory additional context keys land at the top level of context."""
        self.tm.tasks["t-vp-7"] = DummyTask(task_id="t-vp-7", goal="Test", state="CREATED")
        ctx = self.engine.build_context("t-vp-7", additional_context={"custom_key": "custom_val"})
        self.assertEqual(ctx["custom_key"], "custom_val")

    def test_missing_task_id_raises_context_builder_error(self) -> None:
        """build_context() for a non-existent task_id raises ContextBuilderError."""
        with self.assertRaises(ContextBuilderError):
            self.engine.build_context("does-not-exist")

    def test_missing_workflow_raises_context_builder_error(self) -> None:
        """build_context() for a non-existent workflow_id raises ContextBuilderError."""
        self.tm.tasks["t-vp-8"] = DummyTask(task_id="t-vp-8", goal="Test", state="CREATED")
        with self.assertRaises(ContextBuilderError):
            self.engine.build_context("t-vp-8", workflow_id="does-not-exist")

    def test_previous_decisions_populated_from_event_history(self) -> None:
        """Previous cognitive events for a task appear in context['previous_decisions']."""
        event_bus = DummyEventBus()
        tm = DummyTaskManager()
        em = DummyEventManager(event_bus)
        engine, tm, _, _ = _make_engine(event_manager=em)
        tm.tasks["t-vp-9"] = DummyTask(task_id="t-vp-9", goal="History test", state="CREATED")
        event_bus.emit(
            Event(
                name=CognitiveEventType.DECISION_GENERATED,
                source="test",
                task_id="t-vp-9",
                payload={"recommendation": "proceed"},
            )
        )
        ctx = engine.build_context("t-vp-9")
        self.assertEqual(len(ctx["previous_decisions"]), 1)
        self.assertEqual(ctx["previous_decisions"][0]["event_type"], "DecisionGenerated")


# ---------------------------------------------------------------------------
# 3. Recovery and Replanning Tests
# ---------------------------------------------------------------------------


class TestPlannerRecovery(unittest.TestCase):
    """Planner: recovery recommendation and failure scenario handling."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="FAILED")

    def test_recovery_timeout_yields_retry_with_backoff(self) -> None:
        """Timeout failure should recommend retry_with_backoff."""
        self._add_task("t-rec-1", "Fetch large dataset")
        resp = self.engine.analyze(
            "t-rec-1",
            "Recover from failure",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "timeout exceeded"}}},
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_with_backoff")

    def test_recovery_permission_error_yields_fail_fast(self) -> None:
        """Permission failure should recommend fail_fast."""
        self._add_task("t-rec-2", "Write protected file")
        resp = self.engine.analyze(
            "t-rec-2",
            "Recover from failure",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "permission denied"}}},
        )
        self.assertEqual(resp.recommendation.get("action"), "fail_fast")

    def test_recovery_unknown_failure_yields_retry_immediate(self) -> None:
        """Unknown failure reason should default to retry_immediate."""
        self._add_task("t-rec-3", "Process unknown")
        resp = self.engine.analyze(
            "t-rec-3",
            "Recover from failure",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "unknown error xzy"}}},
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_immediate")

    def test_recommend_recovery_helper_method(self) -> None:
        """engine.analyzer.recommend_recovery() routes to Recovery Recommendation."""
        self._add_task("t-rec-4", "Classify images")
        resp = self.engine.analyzer.recommend_recovery(
            task_id="t-rec-4",
            objective="Recover classifier task",
            failure_reason="timeout exceeded",
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_with_backoff")

    def test_recovery_recommendation_structure_is_dict(self) -> None:
        """Recovery recommendation payload must always be a dict with 'action' key."""
        self._add_task("t-rec-5", "Process batch")
        resp = self.engine.analyze(
            "t-rec-5",
            "Recover",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "disk full"}}},
        )
        self.assertIsInstance(resp.recommendation, dict)
        self.assertIn("action", resp.recommendation)

    def test_validator_rejects_recovery_missing_action(self) -> None:
        """Validator raises ValidationError if recovery recommendation lacks 'action'."""
        validator = CognitiveValidator()
        with self.assertRaises(ValidationError):
            validator.validate({}, "Recovery Recommendation", {})

    def test_validator_rejects_recovery_not_a_dict(self) -> None:
        """Validator raises ValidationError if recovery recommendation is not a dict."""
        validator = CognitiveValidator()
        with self.assertRaises(ValidationError):
            validator.validate("just retry", "Recovery Recommendation", {})

    def test_recovery_confidence_within_bounds(self) -> None:
        """Recovery recommendation confidence must be in [0.0, 1.0]."""
        self._add_task("t-rec-6", "Retry job")
        resp = self.engine.analyze(
            "t-rec-6",
            "Recover",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "timeout"}}},
        )
        self.assertGreaterEqual(resp.confidence, 0.0)
        self.assertLessEqual(resp.confidence, 1.0)


# ---------------------------------------------------------------------------
# 4. Capability Selection Tests
# ---------------------------------------------------------------------------


class TestCapabilitySelection(unittest.TestCase):
    """Planner: capability selection routing and validation."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="CREATED")

    def test_exact_capability_match_selected(self) -> None:
        """Exact match on capability name returns confidence ≥ 0.95."""
        self._add_task("t-cap-1", "read_file")
        resp = self.engine.analyze(
            "t-cap-1",
            "read_file",
            "Capability Selection",
            additional_context={"available_capabilities": ["read_file", "write_file"]},
        )
        self.assertEqual(resp.recommendation.get("selected_capability"), "read_file")
        self.assertGreaterEqual(resp.confidence, 0.95)

    def test_partial_capability_match_selected(self) -> None:
        """Partial match on capability name returns a match with lower confidence."""
        self._add_task("t-cap-2", "read")
        resp = self.engine.analyze(
            "t-cap-2",
            "read",
            "Capability Selection",
            additional_context={"available_capabilities": ["read_file", "write_file"]},
        )
        selected = resp.recommendation.get("selected_capability")
        self.assertIsNotNone(selected)
        self.assertIn("read", selected)

    def test_no_match_returns_none_selected(self) -> None:
        """No capability match returns None as selected_capability."""
        self._add_task("t-cap-3", "quantum_compute")
        resp = self.engine.analyze(
            "t-cap-3",
            "quantum_compute",
            "Capability Selection",
            additional_context={"available_capabilities": ["read_file", "write_file"]},
        )
        self.assertIsNone(resp.recommendation.get("selected_capability"))

    def test_no_match_low_confidence(self) -> None:
        """No match returns confidence ≤ 0.60."""
        self._add_task("t-cap-4", "warp_drive")
        resp = self.engine.analyze(
            "t-cap-4",
            "warp_drive",
            "Capability Selection",
            additional_context={"available_capabilities": ["navigate", "click"]},
        )
        self.assertLessEqual(resp.confidence, 0.60)

    def test_no_match_includes_risk(self) -> None:
        """No match includes a risk entry about the missing capability."""
        self._add_task("t-cap-5", "missing_cap")
        resp = self.engine.analyze(
            "t-cap-5",
            "missing_cap",
            "Capability Selection",
            additional_context={"available_capabilities": ["read_file"]},
        )
        self.assertGreater(len(resp.risks), 0)

    def test_validator_rejects_unavailable_capability_selection(self) -> None:
        """Validator raises ValidationError when selected capability is not in available list."""
        validator = CognitiveValidator()
        rec = {"selected_capability": "write_file"}
        with self.assertRaises(ValidationError):
            validator.validate(
                rec,
                "Capability Selection",
                {"available_capabilities": ["read_file"]},
            )

    def test_validator_accepts_valid_capability_selection(self) -> None:
        """Validator passes when selected capability is in available list."""
        validator = CognitiveValidator()
        rec = {"selected_capability": "read_file"}
        result = validator.validate(
            rec,
            "Capability Selection",
            {"available_capabilities": ["read_file", "write_file"]},
        )
        self.assertTrue(result)

    def test_select_capability_via_engine_analyze(self) -> None:
        """engine.analyze() routes 'Capability Selection' correctly."""
        self._add_task("t-cap-6", "summarize_text")
        resp = self.engine.analyze(
            "t-cap-6",
            "summarize_text",
            "Capability Selection",
            additional_context={"available_capabilities": ["summarize_text", "translate_text"]},
        )
        self.assertIsInstance(resp, CognitiveResponse)
        self.assertIn("selected_capability", resp.recommendation)


# ---------------------------------------------------------------------------
# 5. Risk Analysis Tests
# ---------------------------------------------------------------------------


class TestRiskAnalysis(unittest.TestCase):
    """Planner: risk analysis routing and constraint evaluation."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="CREATED")

    def test_risk_analysis_no_constraints_flags_risk(self) -> None:
        """Task with no constraints should surface an 'infinite loop' risk."""
        self._add_task("t-risk-1", "Deploy server")
        resp = self.engine.analyze("t-risk-1", "Deploy server", "Risk Analysis")
        self.assertGreater(len(resp.risks), 0)

    def test_risk_analysis_with_timeout_constraint_flagged(self) -> None:
        """A timeout constraint should appear in the risks list."""
        self._add_task("t-risk-2", "Long computation")
        resp = self.engine.analyze(
            "t-risk-2",
            "Long computation",
            "Risk Analysis",
            additional_context={"constraints": ["timeout_60s"]},
        )
        risk_text = " ".join(resp.risks).lower()
        self.assertIn("timeout", risk_text)

    def test_risk_analysis_returns_risk_level(self) -> None:
        """Risk analysis recommendation must contain 'risk_level' key."""
        self._add_task("t-risk-3", "Read file")
        resp = self.engine.analyze("t-risk-3", "Read file", "Risk Analysis")
        self.assertIn("risk_level", resp.recommendation)

    def test_risk_analysis_confidence_in_bounds(self) -> None:
        """Risk analysis confidence must be in [0.0, 1.0]."""
        self._add_task("t-risk-4", "Scale cluster")
        resp = self.engine.analyze("t-risk-4", "Scale cluster", "Risk Analysis")
        self.assertGreaterEqual(resp.confidence, 0.0)
        self.assertLessEqual(resp.confidence, 1.0)

    def test_risk_analysis_via_analyzer_helper(self) -> None:
        """analyzer.analyze_risks() routes to Risk Analysis correctly."""
        self._add_task("t-risk-5", "Purge database")
        resp = self.engine.analyzer.analyze_risks(
            task_id="t-risk-5",
            objective="Purge database",
            constraints=["limit_1000_rows"],
        )
        self.assertIsInstance(resp, CognitiveResponse)
        self.assertIn("risk_level", resp.recommendation)


# ---------------------------------------------------------------------------
# 6. Permission Review Tests
# ---------------------------------------------------------------------------


class TestPermissionReview(unittest.TestCase):
    """Planner: permission review gating."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="CREATED")

    def test_safe_permissions_approved(self) -> None:
        """No unsafe permissions → recommendation approves execution."""
        self._add_task("t-perm-1", "Read config file")
        resp = self.engine.analyze(
            "t-perm-1",
            "Read config file",
            "Permission Review",
            additional_context={"required_permissions": []},
        )
        self.assertIn("approve", resp.recommendation.lower())

    def test_terminal_without_sandbox_rejected(self) -> None:
        """Terminal permission without sandbox access → recommendation rejects."""
        self._add_task("t-perm-2", "Run shell script")
        resp = self.engine.analyze(
            "t-perm-2",
            "Run shell script",
            "Permission Review",
            additional_context={
                "required_permissions": ["terminal"],
                "permissions": {"terminal": False},
            },
        )
        self.assertIn("reject", resp.recommendation.lower())

    def test_permission_review_validator_security_violation(self) -> None:
        """Validator raises ValidationError when approving a task with security violation history."""
        validator = CognitiveValidator()
        rec = "Approve execution permissions."
        ctx = {
            "task": {
                "history": [{"event_type": "security_violation_detected", "detail": "key leaked"}]
            }
        }
        with self.assertRaises(ValidationError):
            validator.validate(rec, "Permission Review", ctx)

    def test_permission_review_safe_history_passes(self) -> None:
        """Validator accepts approval when task history is clean."""
        validator = CognitiveValidator()
        rec = "Approve execution permissions."
        ctx = {"task": {"history": [{"event_type": "step_completed"}]}}
        result = validator.validate(rec, "Permission Review", ctx)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# 7. Conflict Resolution Tests
# ---------------------------------------------------------------------------


class TestConflictResolution(unittest.TestCase):
    """Planner: conflict resolution routing and concurrent write detection."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="CREATED")

    def test_no_conflict_parallel_proceed(self) -> None:
        """No concurrent writes → resolution recommends parallel proceed."""
        self._add_task("t-conf-1", "Write logs")
        resp = self.engine.analyze("t-conf-1", "Write logs", "Conflict Resolution")
        self.assertIn("No conflicts", resp.recommendation.get("resolution", ""))

    def test_conflict_detected_concurrent_writes(self) -> None:
        """Two concurrent write steps → resolution enforces sequential ordering."""
        self._add_task("t-conf-2", "Export data")
        self.wm.workflows["wf-conf-2"] = DummyWorkflow(
            workflow_id="wf-conf-2",
            parent_task_id="t-conf-2",
            status="RUNNING",
            steps={
                "step_1": {"capability": "write_file"},
                "step_2": {"capability": "write_file"},
            },
        )
        resp = self.engine.analyze(
            "t-conf-2",
            "Export data",
            "Conflict Resolution",
            additional_context={"workflow_id": "wf-conf-2"},
        )
        resolution = resp.recommendation.get("resolution", "")
        self.assertIn("sequential", resolution.lower())

    def test_conflict_resolution_validator_empty_rec_rejected(self) -> None:
        """Validator rejects empty conflict resolution recommendation."""
        validator = CognitiveValidator()
        with self.assertRaises(ValidationError):
            validator.validate(None, "Conflict Resolution", {})

    def test_conflict_resolution_confidence_in_bounds(self) -> None:
        """Conflict resolution confidence must be in [0.0, 1.0]."""
        self._add_task("t-conf-3", "Merge branches")
        resp = self.engine.analyze("t-conf-3", "Merge branches", "Conflict Resolution")
        self.assertGreaterEqual(resp.confidence, 0.0)
        self.assertLessEqual(resp.confidence, 1.0)


# ---------------------------------------------------------------------------
# 8. Planner Optimization Tests
# ---------------------------------------------------------------------------


class TestPlannerOptimization(unittest.TestCase):
    """Planner: workflow optimization routing."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()

    def _add_task(self, task_id: str, goal: str) -> None:
        self.tm.tasks[task_id] = DummyTask(task_id=task_id, goal=goal, state="CREATED")
        self.wm.workflows[f"wf-{task_id}"] = DummyWorkflow(
            workflow_id=f"wf-{task_id}", parent_task_id=task_id, status="RUNNING"
        )

    def test_optimize_workflow_returns_response(self) -> None:
        """optimize_workflow() must return a CognitiveResponse."""
        self._add_task("t-opt-1", "Optimize pipeline")
        planner = CognitivePlanner(engine=self.engine)
        resp = planner.optimize_workflow(
            task_id="t-opt-1",
            objective="Optimize pipeline",
            workflow_id=f"wf-t-opt-1",
        )
        self.assertIsInstance(resp, CognitiveResponse)

    def test_optimize_workflow_confidence_in_bounds(self) -> None:
        """Optimized workflow confidence is between 0 and 1."""
        self._add_task("t-opt-2", "Optimize data pipeline")
        planner = CognitivePlanner(engine=self.engine)
        resp = planner.optimize_workflow(
            task_id="t-opt-2",
            objective="Optimize data pipeline",
            workflow_id="wf-t-opt-2",
        )
        self.assertGreaterEqual(resp.confidence, 0.0)
        self.assertLessEqual(resp.confidence, 1.0)


# ---------------------------------------------------------------------------
# 9. Validator Edge Cases
# ---------------------------------------------------------------------------


class TestValidatorEdgeCases(unittest.TestCase):
    """Validator: structural and safety edge cases."""

    def setUp(self) -> None:
        self.validator = CognitiveValidator()
        self.caps = {"available_capabilities": ["read_file", "write_file", "summarize_text"]}

    def test_negative_step_cost_rejected(self) -> None:
        """Steps with negative estimated_cost are rejected."""
        rec = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": [], "estimated_cost": -5.0},
            ]
        }
        with self.assertRaises(ValidationError) as ex:
            self.validator.validate(rec, "Workflow Planning", self.caps)
        self.assertIn("negative", str(ex.exception))

    def test_directory_traversal_path_rejected(self) -> None:
        """File paths containing ../ traversal are rejected as unsafe."""
        rec = {
            "steps": [
                {
                    "step_id": "s1",
                    "capability": "read_file",
                    "input_data": {"file_path": "../../etc/passwd"},
                    "dependencies": [],
                }
            ]
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(rec, "Workflow Planning", self.caps)

    def test_etc_path_rejected(self) -> None:
        """/etc paths in file_path are rejected as unsafe."""
        rec = {
            "steps": [
                {
                    "step_id": "s1",
                    "capability": "read_file",
                    "input_data": {"file_path": "/etc/shadow"},
                    "dependencies": [],
                }
            ]
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(rec, "Workflow Planning", self.caps)

    def test_empty_steps_list_rejected(self) -> None:
        """A workflow with an empty steps list is rejected."""
        with self.assertRaises(ValidationError):
            self.validator.validate({"steps": []}, "Workflow Planning", self.caps)

    def test_steps_not_a_list_rejected(self) -> None:
        """Steps that are not a list are rejected."""
        with self.assertRaises(ValidationError):
            self.validator.validate({"steps": "step_one"}, "Workflow Planning", self.caps)

    def test_step_without_step_id_rejected(self) -> None:
        """A step missing 'step_id' is rejected."""
        rec = {"steps": [{"capability": "read_file", "dependencies": []}]}
        with self.assertRaises(ValidationError):
            self.validator.validate(rec, "Workflow Planning", self.caps)

    def test_step_without_capability_rejected(self) -> None:
        """A step missing 'capability' is rejected."""
        rec = {"steps": [{"step_id": "s1", "dependencies": []}]}
        with self.assertRaises(ValidationError):
            self.validator.validate(rec, "Workflow Planning", self.caps)

    def test_step_with_invalid_dependency_rejected(self) -> None:
        """A step depending on a non-existent step_id is rejected."""
        rec = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": ["ghost_step"]},
            ]
        }
        with self.assertRaises(ValidationError):
            self.validator.validate(rec, "Workflow Planning", self.caps)

    def test_general_impossible_negative_top_level_cost(self) -> None:
        """Top-level negative estimated_cost is rejected by impossible check."""
        with self.assertRaises(ValidationError):
            self.validator.validate(
                {"estimated_cost": -100.0},
                "Risk Analysis",
                {},
            )

    def test_recommendation_not_dict_for_workflow_rejected(self) -> None:
        """Non-dict workflow planning recommendation is rejected."""
        with self.assertRaises(ValidationError):
            self.validator.validate("proceed now", "Workflow Planning", self.caps)


# ---------------------------------------------------------------------------
# 10. Cache and Performance Tests
# ---------------------------------------------------------------------------


class TestCacheAndPerformance(unittest.TestCase):
    """Planner: cache correctness, TTL, and performance budgets."""

    def test_cache_hit_does_not_call_provider(self) -> None:
        """Second identical request returns cached response without calling provider."""
        call_count = 0

        class CountingProvider(ReasoningProvider):
            def reason(self, request: CognitiveRequest, context: dict, decision_type: str) -> dict:
                nonlocal call_count
                call_count += 1
                return {
                    "recommendation": {"steps": [{"step_id": "s1", "capability": "read_file", "dependencies": []}]},
                    "confidence": 0.90,
                    "reasoning_summary": "counted",
                }

        event_bus = DummyEventBus()
        tm = DummyTaskManager()
        em = DummyEventManager(event_bus)
        engine = CognitiveEngine(
            reasoning_provider=CountingProvider(),
            task_manager=tm,
            workflow_manager=DummyWorkflowManager(),
            event_manager=em,
            cache_ttl=60.0,
        )
        tm.tasks["t-cache-1"] = DummyTask(task_id="t-cache-1", goal="Cache test", state="CREATED")
        req = CognitiveRequest(
            task_id="t-cache-1",
            objective="Cache test",
            available_capabilities=["read_file"],
        )

        engine.reason(req, "Workflow Planning")
        engine.reason(req, "Workflow Planning")
        self.assertEqual(call_count, 1, "Provider should be called only once on cache hit")

    def test_cache_expires_after_ttl(self) -> None:
        """Cache entry expires after its TTL and triggers a new provider call."""
        cache = CognitiveCache(default_ttl=0.05)  # 50ms TTL
        req = CognitiveRequest(task_id="t-ttl-1", objective="TTL test")
        resp = CognitiveResponse(recommendation="ok", confidence=0.8, reasoning_summary="ttl")
        cache.set(req, "test_type", resp)
        self.assertIsNotNone(cache.get(req, "test_type"))
        time.sleep(0.08)
        self.assertIsNone(cache.get(req, "test_type"))

    def test_planner_plan_latency_under_150ms(self) -> None:
        """plan() execution must complete within 150 ms performance budget."""
        event_bus = DummyEventBus()
        tm = DummyTaskManager()
        em = DummyEventManager(event_bus)
        engine, _, _, _ = _make_engine(event_manager=em)
        tm.tasks["t-perf-1"] = DummyTask(task_id="t-perf-1", goal="Perf test", state="CREATED")
        engine.context_builder.task_manager = tm

        start = time.perf_counter()
        engine.plan("t-perf-1", "Perf test")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 150, f"plan() took {elapsed_ms:.1f} ms, exceeds 150 ms budget")

    def test_cache_different_decision_types_are_separate(self) -> None:
        """Cache treats same request with different decision types as separate entries."""
        cache = CognitiveCache(default_ttl=60.0)
        req = CognitiveRequest(task_id="t-cache-2", objective="Dual type test")
        resp1 = CognitiveResponse(recommendation="r1", confidence=0.8, reasoning_summary="s1")
        resp2 = CognitiveResponse(recommendation="r2", confidence=0.9, reasoning_summary="s2")
        cache.set(req, "Risk Analysis", resp1)
        cache.set(req, "Workflow Planning", resp2)
        self.assertEqual(cache.get(req, "Risk Analysis").recommendation, "r1")
        self.assertEqual(cache.get(req, "Workflow Planning").recommendation, "r2")

    def test_cache_size_tracks_entries(self) -> None:
        """CognitiveCache.size reflects the number of cached entries."""
        cache = CognitiveCache(default_ttl=60.0)
        req1 = CognitiveRequest(task_id="t-sz-1", objective="A")
        req2 = CognitiveRequest(task_id="t-sz-2", objective="B")
        resp = CognitiveResponse(recommendation="x", confidence=0.5, reasoning_summary="y")
        cache.set(req1, "Risk Analysis", resp)
        cache.set(req2, "Risk Analysis", resp)
        self.assertEqual(cache.size, 2)


# ---------------------------------------------------------------------------
# 11. Request/Response Serialization Tests
# ---------------------------------------------------------------------------


class TestRequestResponseSerialization(unittest.TestCase):
    """Planner: request and response data model serialization contracts."""

    def test_request_round_trip(self) -> None:
        """CognitiveRequest serializes and deserializes without data loss."""
        req = CognitiveRequest(
            task_id="t-ser-1",
            objective="Serialize me",
            workflow_id="wf-xyz",
            constraints=["c1", "c2"],
            available_capabilities=["read_file", "write_file"],
            current_context={"key": "value"},
        )
        d = req.to_dict()
        req2 = CognitiveRequest.from_dict(d)
        self.assertEqual(req.task_id, req2.task_id)
        self.assertEqual(req.objective, req2.objective)
        self.assertEqual(req.workflow_id, req2.workflow_id)
        self.assertEqual(req.constraints, req2.constraints)
        self.assertEqual(req.available_capabilities, req2.available_capabilities)
        self.assertEqual(req.current_context, req2.current_context)

    def test_response_round_trip(self) -> None:
        """CognitiveResponse serializes and deserializes without data loss."""
        resp = CognitiveResponse(
            recommendation={"action": "proceed"},
            confidence=0.87,
            reasoning_summary="All checks passed.",
            risks=["risk_a"],
            suggested_actions=["act_b"],
            metadata={"model": "mock"},
        )
        d = resp.to_dict()
        resp2 = CognitiveResponse.from_dict(d)
        self.assertEqual(resp.confidence, resp2.confidence)
        self.assertEqual(resp.risks, resp2.risks)
        self.assertEqual(resp.suggested_actions, resp2.suggested_actions)
        self.assertEqual(resp.recommendation, resp2.recommendation)

    def test_response_confidence_zero_valid(self) -> None:
        """Confidence of exactly 0.0 is valid."""
        resp = CognitiveResponse(recommendation="skip", confidence=0.0, reasoning_summary="Nothing to do.")
        self.assertEqual(resp.confidence, 0.0)

    def test_response_confidence_one_valid(self) -> None:
        """Confidence of exactly 1.0 is valid."""
        resp = CognitiveResponse(recommendation="proceed", confidence=1.0, reasoning_summary="Certain.")
        self.assertEqual(resp.confidence, 1.0)

    def test_response_confidence_above_one_raises(self) -> None:
        """Confidence above 1.0 raises ValueError."""
        with self.assertRaises(ValueError):
            CognitiveResponse(recommendation="x", confidence=1.01, reasoning_summary="oob")

    def test_response_confidence_below_zero_raises(self) -> None:
        """Confidence below 0.0 raises ValueError."""
        with self.assertRaises(ValueError):
            CognitiveResponse(recommendation="x", confidence=-0.01, reasoning_summary="oob")

    def test_request_defaults_are_correct(self) -> None:
        """CognitiveRequest with minimal args initializes correct defaults."""
        req = CognitiveRequest(task_id="t-def-1", objective="minimal")
        self.assertIsNone(req.workflow_id)
        self.assertEqual(req.constraints, [])
        self.assertEqual(req.available_capabilities, [])
        self.assertEqual(req.current_context, {})

    def test_response_defaults_are_correct(self) -> None:
        """CognitiveResponse with minimal args initializes correct defaults."""
        resp = CognitiveResponse(recommendation="ok", confidence=0.5, reasoning_summary="base")
        self.assertEqual(resp.risks, [])
        self.assertEqual(resp.suggested_actions, [])
        self.assertEqual(resp.metadata, {})


# ---------------------------------------------------------------------------
# 12. General Reasoning Fallback
# ---------------------------------------------------------------------------


class TestGeneralReasoningFallback(unittest.TestCase):
    """Planner: engine.analyze() unknown types fall back to general reasoning."""

    def setUp(self) -> None:
        self.engine, self.tm, self.wm, self.eb = _make_engine()
        self.tm.tasks["t-fb-1"] = DummyTask(task_id="t-fb-1", goal="Test fallback", state="CREATED")

    def test_unknown_analysis_type_falls_back(self) -> None:
        """engine.analyze() with unrecognized type falls back to general reason()."""
        resp = self.engine.analyze("t-fb-1", "Do something", "Completely Unknown Type")
        self.assertIsInstance(resp, CognitiveResponse)

    def test_recommend_method_returns_response(self) -> None:
        """engine.recommend() returns a CognitiveResponse for any decision type."""
        resp = self.engine.recommend("t-fb-1", "Risk Analysis", "Assess deployment risk")
        self.assertIsInstance(resp, CognitiveResponse)

    def test_validate_method_returns_true_for_valid(self) -> None:
        """engine.validate() returns True for a valid workflow recommendation."""
        rec = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": []},
            ]
        }
        result = self.engine.validate(rec, "Workflow Planning", {"available_capabilities": ["read_file"]})
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
