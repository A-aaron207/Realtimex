"""
Unit tests for the Realtimex Cognitive Engine.
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
from cognitive.reasoning import (
    CognitiveRequest,
    CognitiveResponse,
    MockReasoningProvider,
    ReasoningProvider,
)
from cognitive.validator import CognitiveValidator
from events.event import Event
from events.event_types import CognitiveEventType


class DummyEventBus:
    """Mock event bus to collect emitted events for assertions."""

    def __init__(self) -> None:
        self.emitted: list[Event] = []

    def emit(self, event: Event) -> None:
        self.emitted.append(event)


class DummyTask:
    """Mock Task object matching tasks/task.py interface."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        state: Any,
        memory: dict[str, Any] | None = None,
        workflow: dict[str, Any] | None = None,
        history: list[Any] | None = None,
    ) -> None:
        self.task_id = task_id
        self.goal = goal
        self.state = state
        self.memory = memory or {}
        self.workflow = workflow or {}
        self.history = history or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": str(self.state),
            "memory": self.memory,
            "workflow": self.workflow,
            "history": self.history,
        }


class DummyTaskManager:
    """Mock TaskManager to return mock tasks."""

    def __init__(self) -> None:
        self.tasks: dict[str, DummyTask] = {}

    def get_task(self, task_id: str) -> DummyTask:
        if task_id not in self.tasks:
            raise KeyError(f"Task {task_id} not found")
        return self.tasks[task_id]


class DummyWorkflow:
    """Mock Workflow object matching workflow/workflow.py interface."""

    def __init__(self, workflow_id: str, parent_task_id: str, status: str, steps: dict[str, Any] | None = None) -> None:
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
    """Mock WorkflowManager to load mock workflows."""

    def __init__(self) -> None:
        self.workflows: dict[str, DummyWorkflow] = {}

    def load_workflow(self, workflow_id: str) -> DummyWorkflow:
        if workflow_id not in self.workflows:
            raise KeyError(f"Workflow {workflow_id} not found")
        return self.workflows[workflow_id]


class DummyEventManager:
    """Mock EventManager that records events and supports filtering."""

    def __init__(self, event_bus: DummyEventBus) -> None:
        self.event_bus = event_bus

    def filter_events(self, task_id: str | None = None) -> list[Event]:
        return [e for e in self.event_bus.emitted if task_id is None or e.task_id == task_id]


class CountingReasoningProvider(ReasoningProvider):
    """ReasoningProvider that counts calls to reason()."""

    def __init__(self, inner: ReasoningProvider) -> None:
        self.inner = inner
        self.call_count = 0

    def reason(self, request: CognitiveRequest, context: dict[str, Any], decision_type: str) -> dict[str, Any]:
        self.call_count += 1
        return self.inner.reason(request, context, decision_type)


class TestCognitiveEngine(unittest.TestCase):
    """Rigorous test cases verifying Cognitive Engine subsystems."""

    def setUp(self) -> None:
        self.event_bus = DummyEventBus()
        self.task_manager = DummyTaskManager()
        self.workflow_manager = DummyWorkflowManager()
        self.event_manager = DummyEventManager(self.event_bus)
        
        self.engine = CognitiveEngine(
            reasoning_provider=MockReasoningProvider(),
            task_manager=self.task_manager,
            workflow_manager=self.workflow_manager,
            event_manager=self.event_manager,
            config={"system_limit": 100},
            cache_ttl=60.0,
        )

    def test_request_response_serialization(self) -> None:
        """Verify serialization of requests and responses."""
        req = CognitiveRequest(
            task_id="t1",
            objective="Run test",
            constraints=["timeout_30s"],
            available_capabilities=["summarize_text"],
        )
        data = req.to_dict()
        self.assertEqual(data["task_id"], "t1")
        self.assertEqual(data["constraints"], ["timeout_30s"])

        req2 = CognitiveRequest.from_dict(data)
        self.assertEqual(req2.task_id, "t1")
        self.assertEqual(req2.constraints, ["timeout_30s"])

        resp = CognitiveResponse(
            recommendation="Proceed",
            confidence=0.95,
            reasoning_summary="Ready to go",
            risks=["risk1"],
            suggested_actions=["act1"],
            metadata={"source": "test"},
        )
        r_data = resp.to_dict()
        self.assertEqual(r_data["confidence"], 0.95)
        self.assertEqual(r_data["risks"], ["risk1"])

        resp2 = CognitiveResponse.from_dict(r_data)
        self.assertEqual(resp2.confidence, 0.95)
        self.assertEqual(resp2.risks, ["risk1"])

        with self.assertRaises(ValueError):
            CognitiveResponse(recommendation="Proceed", confidence=1.5, reasoning_summary="Too high")

    def test_cache_ttl_expiration(self) -> None:
        """Verify cache expiration, TTL, and cache hits/misses."""
        cache = CognitiveCache(default_ttl=0.1)
        req = CognitiveRequest(task_id="t1", objective="test")
        resp = CognitiveResponse(recommendation="OK", confidence=0.9, reasoning_summary="test")
        
        cache.set(req, "test_decision", resp)
        self.assertEqual(cache.size, 1)

        # Get within TTL
        cached = cache.get(req, "test_decision")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.recommendation, "OK")

        # Sleep past TTL
        time.sleep(0.15)
        cached_expired = cache.get(req, "test_decision")
        self.assertIsNone(cached_expired)
        self.assertEqual(cache.size, 0)

    def test_cache_integration(self) -> None:
        """Verify cache hit bypasses reasoning pipeline execution."""
        provider = CountingReasoningProvider(MockReasoningProvider())
        engine = CognitiveEngine(
            reasoning_provider=provider,
            task_manager=self.task_manager,
            workflow_manager=self.workflow_manager,
            event_manager=self.event_manager,
        )

        self.task_manager.tasks["t1"] = DummyTask(task_id="t1", goal="Test Cache Integration", state="CREATED")
        req = CognitiveRequest(task_id="t1", objective="Test Cache Integration")
        
        # First call (cache miss)
        res1 = engine.reason(req, "Risk Analysis")
        self.assertEqual(provider.call_count, 1)

        # Second call (cache hit)
        res2 = engine.reason(req, "Risk Analysis")
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(res1.recommendation, res2.recommendation)

    def test_context_builder(self) -> None:
        """Verify ContextBuilder correctly gathers resources and history."""
        task_id = "task-123"
        wf_id = "wf-456"

        self.task_manager.tasks[task_id] = DummyTask(
            task_id=task_id,
            goal="Build website",
            state="RUNNING",
            memory={"session_id": "s1"},
        )
        self.workflow_manager.workflows[wf_id] = DummyWorkflow(
            workflow_id=wf_id,
            parent_task_id=task_id,
            status="RUNNING",
        )

        # Add a past event
        self.event_bus.emit(
            Event(
                name=CognitiveEventType.DECISION_GENERATED,
                source="test",
                task_id=task_id,
                payload={"recommendation": "Mock decision"},
            )
        )

        ctx = self.engine.build_context(task_id=task_id, workflow_id=wf_id)
        self.assertEqual(ctx["task_id"], task_id)
        self.assertEqual(ctx["task"]["goal"], "Build website")
        self.assertEqual(ctx["workflow"]["workflow_id"], wf_id)
        self.assertEqual(ctx["memory"]["session_id"], "s1")
        self.assertEqual(ctx["configuration"]["system_limit"], 100)
        self.assertEqual(len(ctx["previous_decisions"]), 1)
        self.assertEqual(ctx["previous_decisions"][0]["event_type"], "DecisionGenerated")

    def test_context_builder_missing_task_raises(self) -> None:
        """Verify context builder raises ContextBuilderError for missing tasks."""
        with self.assertRaises(ContextBuilderError):
            self.engine.build_context(task_id="non-existent")

    def test_validator_workflow_planning(self) -> None:
        """Verify validation of steps, dependencies, cost, time, and safety."""
        validator = CognitiveValidator()
        context = {
            "available_capabilities": ["read_file", "write_file", "summarize_text"],
        }

        # 1. Valid Workflow
        valid_rec = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": []},
                {"step_id": "s2", "capability": "summarize_text", "dependencies": ["s1"]},
            ]
        }
        self.assertTrue(validator.validate(valid_rec, "Workflow Planning", context))

        # 2. Circular Dependency
        circular_rec = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": ["s2"]},
                {"step_id": "s2", "capability": "summarize_text", "dependencies": ["s1"]},
            ]
        }
        with self.assertRaises(ValidationError) as ex:
            validator.validate(circular_rec, "Workflow Planning", context)
        self.assertIn("Circular dependency", str(ex.exception))

        # 3. Missing Capability
        missing_cap_rec = {
            "steps": [
                {"step_id": "s1", "capability": "unsafe_execution", "dependencies": []},
            ]
        }
        with self.assertRaises(ValidationError) as ex:
            validator.validate(missing_cap_rec, "Workflow Planning", context)
        self.assertIn("missing", str(ex.exception))

        # 4. Impossible settings (negative cost)
        negative_cost_rec = {
            "steps": [
                {"step_id": "s1", "capability": "read_file", "dependencies": [], "estimated_cost": -10.0},
            ]
        }
        with self.assertRaises(ValidationError) as ex:
            validator.validate(negative_cost_rec, "Workflow Planning", context)
        self.assertIn("negative", str(ex.exception))

        # 5. Unsafe suggestions (directory traversal)
        unsafe_rec = {
            "steps": [
                {
                    "step_id": "s1",
                    "capability": "read_file",
                    "input_data": {"file_path": "../../../../etc/passwd"},
                    "dependencies": [],
                },
            ]
        }
        with self.assertRaises(ValidationError) as ex:
            validator.validate(unsafe_rec, "Workflow Planning", context)
        self.assertIn("unsafe file path", str(ex.exception).lower())

    def test_pipeline_events_and_flow(self) -> None:
        """Verify pipeline emits correct events at start, validation failure, and completion."""
        task_id = "task-999"
        self.task_manager.tasks[task_id] = DummyTask(task_id=task_id, goal="Demo workflow", state="CREATED")

        # Mock provider that will trigger validation failure on steps
        class FailingProvider(ReasoningProvider):
            def reason(self, request: CognitiveRequest, context: dict[str, Any], decision_type: str) -> dict[str, Any]:
                return {
                    "recommendation": {
                        "steps": [
                            {"step_id": "s1", "capability": "non_existent_capability"}
                        ]
                    },
                    "confidence": 0.8,
                    "reasoning_summary": "invalid steps",
                }

        engine_failing = CognitiveEngine(
            reasoning_provider=FailingProvider(),
            task_manager=self.task_manager,
            workflow_manager=self.workflow_manager,
            event_manager=self.event_manager,
            capability_registry=None,
        )
        
        # Enable capabilities registry context so it complains about non_existent_capability
        # We pass it in constraints / context
        req = CognitiveRequest(
            task_id=task_id,
            objective="test failure events",
            available_capabilities=["read_file"],  # s1 capability not listed here
        )

        with self.assertRaises(ValidationError):
            engine_failing.reason(req, "Workflow Planning")

        # Assert events emitted
        event_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("ReasoningStarted", event_names)
        self.assertIn("ValidationFailed", event_names)
        self.assertNotIn("DecisionGenerated", event_names)

    def test_engine_public_api_helpers(self) -> None:
        """Test general reason, plan, analyze, validate, recommend, and context helpers."""
        task_id = "task-ok"
        self.task_manager.tasks[task_id] = DummyTask(task_id=task_id, goal="Generate plan", state="CREATED")

        # 1. Plan workflow
        resp = self.engine.plan(task_id, "Build portfolio website")
        self.assertIsInstance(resp, CognitiveResponse)
        self.assertIn("steps", resp.recommendation)
        self.assertEqual(resp.confidence, 0.90)

        # 2. Risk analysis
        resp_risk = self.engine.analyze(task_id, "Deploy server", "Risk Analysis")
        self.assertEqual(resp_risk.recommendation.get("risk_level"), "medium")

        # 3. Conflict resolution
        resp_conflict = self.engine.analyze(task_id, "Write files", "Conflict Resolution")
        self.assertEqual(resp_conflict.recommendation.get("resolution"), "No conflicts detected. Proceed in parallel.")

        # 4. Recommendation accept / reject
        self.engine.accept_recommendation(task_id, resp.recommendation, "Workflow Planning")
        self.engine.reject_recommendation(task_id, resp.recommendation, "Workflow Planning", "User manually changed mind")

        emitted_names = [e.name for e in self.event_bus.emitted]
        self.assertIn("RecommendationAccepted", emitted_names)
        self.assertIn("RecommendationRejected", emitted_names)


if __name__ == "__main__":
    unittest.main()
