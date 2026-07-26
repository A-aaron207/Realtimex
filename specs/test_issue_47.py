"""
Regression Test: Issue #47 — Recovery Action Routing Bug
=========================================================
Root Cause:
    engine.analyze() with decision_type containing "recovery" only checked
    additional_context["failure_reason"] at the flat top level. When callers
    used the nested path {"task": {"metadata": {"failure_reason": "..."}}} —
    which is the format used by analyzer.recommend_recovery() and the context
    builder — the engine silently defaulted to "unknown" and always returned
    action="retry_immediate" regardless of the actual failure type.

Fix (cognitive/engine.py, analyze() method):
    Added a second lookup branch that checks the nested path
    additional_context["task"]["metadata"]["failure_reason"] when the flat
    key is absent.

This file must never be deleted (regression protection).
"""

from __future__ import annotations

import unittest
from typing import Any

from cognitive.engine import CognitiveEngine
from cognitive.reasoning import CognitiveResponse, MockReasoningProvider
from cognitive.context import ContextBuilder
from events.event import Event


class DummyEventBus:
    def emit(self, event: Event) -> None:
        pass


class DummyTask:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self.goal = "recover"
        self.state = "FAILED"
        self.memory: dict = {}
        self.workflow: dict = {}
        self.history: list = []
        self.metadata: dict = {}

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "state": self.state,
            "memory": self.memory,
            "workflow": self.workflow,
            "history": self.history,
            "metadata": self.metadata,
        }


class DummyTaskManager:
    def get_task(self, task_id: str) -> DummyTask:
        return DummyTask(task_id)


class DummyEventManager:
    def filter_events(self, task_id: str) -> list:
        return []


class DummyWM:
    def load_workflow(self, wf_id: str) -> None:
        raise KeyError(wf_id)


def _engine() -> CognitiveEngine:
    return CognitiveEngine(
        reasoning_provider=MockReasoningProvider(),
        task_manager=DummyTaskManager(),
        workflow_manager=DummyWM(),
        event_manager=DummyEventManager(),
    )


class TestIssue47RecoveryRoutingBug(unittest.TestCase):
    """
    Issue #47: engine.analyze() ignores nested failure_reason path in additional_context.
    """

    def test_nested_timeout_maps_to_retry_with_backoff(self) -> None:
        """
        REGRESSION: Passing failure_reason inside task.metadata must map to
        retry_with_backoff, not retry_immediate.
        """
        engine = _engine()
        resp = engine.analyze(
            "t-reg-47-a",
            "recover from timeout",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "timeout exceeded"}}},
        )
        self.assertEqual(
            resp.recommendation.get("action"),
            "retry_with_backoff",
            "Nested timeout failure_reason must produce retry_with_backoff, not retry_immediate",
        )

    def test_nested_permission_maps_to_fail_fast(self) -> None:
        """
        REGRESSION: Passing failure_reason='permission denied' inside task.metadata
        must map to fail_fast, not retry_immediate.
        """
        engine = _engine()
        resp = engine.analyze(
            "t-reg-47-b",
            "recover from permission denied",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "permission denied: /etc/shadow"}}},
        )
        self.assertEqual(
            resp.recommendation.get("action"),
            "fail_fast",
            "Nested permission failure_reason must produce fail_fast, not retry_immediate",
        )

    def test_flat_key_still_works(self) -> None:
        """
        Flat additional_context['failure_reason'] key must still work (backward compat).
        """
        engine = _engine()
        resp = engine.analyze(
            "t-reg-47-c",
            "recover",
            "Recovery Recommendation",
            additional_context={"failure_reason": "timeout exceeded"},
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_with_backoff")

    def test_unknown_reason_still_defaults_to_retry_immediate(self) -> None:
        """
        Unknown failure reason must still default to retry_immediate (not broken by fix).
        """
        engine = _engine()
        resp = engine.analyze(
            "t-reg-47-d",
            "recover",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {"failure_reason": "disk_full_unexpected"}}},
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_immediate")

    def test_no_additional_context_defaults_to_retry_immediate(self) -> None:
        """
        With no additional_context at all, defaults to retry_immediate (not a crash).
        """
        engine = _engine()
        resp = engine.analyze(
            "t-reg-47-e",
            "recover",
            "Recovery Recommendation",
        )
        self.assertIsInstance(resp, CognitiveResponse)
        self.assertEqual(resp.recommendation.get("action"), "retry_immediate")

    def test_empty_task_metadata_defaults_to_retry_immediate(self) -> None:
        """
        Empty task.metadata dict must not crash; defaults to retry_immediate.
        """
        engine = _engine()
        resp = engine.analyze(
            "t-reg-47-f",
            "recover",
            "Recovery Recommendation",
            additional_context={"task": {"metadata": {}}},
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_immediate")

    def test_recommend_recovery_helper_still_works(self) -> None:
        """
        analyzer.recommend_recovery() helper still produces the correct action.
        (Verifies the analyzer path is not broken by the engine fix.)
        """
        engine = _engine()
        resp = engine.analyzer.recommend_recovery(
            task_id="t-reg-47-g",
            objective="recover",
            failure_reason="timeout exceeded",
        )
        self.assertEqual(resp.recommendation.get("action"), "retry_with_backoff")


if __name__ == "__main__":
    unittest.main()
