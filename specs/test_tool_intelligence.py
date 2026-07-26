"""
Project D — Tool Intelligence Unit Tests
========================================
Covers: ToolCandidate representation, ToolPerformanceTracker metrics tracking,
        ToolIntelligenceEngine multi-metric ranking (confidence, reliability, latency, cost),
        best tool selection (e.g. Browser 95% vs Search 89% vs Requests 40%),
        dynamic ranking updates based on runtime execution outcomes, and CognitivePlanner integration.
"""

from __future__ import annotations

import unittest
from cognitive.planner import CognitivePlanner
from cognitive.reasoning import MockReasoningProvider
from cognitive.tool_intelligence import (
    ToolCandidate,
    ToolIntelligenceEngine,
    ToolPerformanceTracker,
)


class TestToolPerformanceTracker(unittest.TestCase):
    """Test runtime performance tracking for capabilities."""

    def test_default_reliability_and_latency(self) -> None:
        tracker = ToolPerformanceTracker()
        self.assertEqual(tracker.get_reliability_rate("unknown_tool"), 1.0)
        self.assertEqual(tracker.get_average_latency_ms("unknown_tool"), 50.0)

    def test_record_execution_updates_metrics(self) -> None:
        tracker = ToolPerformanceTracker()
        tracker.record_execution("browser", success=True, latency_ms=100.0)
        tracker.record_execution("browser", success=True, latency_ms=200.0)
        tracker.record_execution("browser", success=False, latency_ms=300.0)

        self.assertEqual(tracker.get_reliability_rate("browser"), 2.0 / 3.0)
        self.assertEqual(tracker.get_average_latency_ms("browser"), 200.0)


class TestToolIntelligenceEngine(unittest.TestCase):
    """Test ToolIntelligenceEngine multi-metric ranking and selection."""

    def setUp(self) -> None:
        self.engine = ToolIntelligenceEngine()

    def test_rank_candidates_internet_search(self) -> None:
        """
        REGRESSION / PROJECT D EXAMPLE TEST:
        User intent: "search internet"
        Candidates:
            - Browser: confidence 95%, reliability 100%
            - Web Search: confidence 89%, reliability 100%
            - Python Requests: confidence 40%, reliability 50%
        Verifies Browser is ranked #1.
        """
        browser = ToolCandidate("navigate", "browser", confidence_score=0.95, historical_reliability=1.0, estimated_latency_ms=120)
        web_search = ToolCandidate("search", "search", confidence_score=0.89, historical_reliability=1.0, estimated_latency_ms=80)
        py_requests = ToolCandidate("python_http", "python_runtime", confidence_score=0.40, historical_reliability=0.5, estimated_latency_ms=300)

        ranked = self.engine.rank_candidates("search internet", [py_requests, browser, web_search])
        self.assertEqual(len(ranked), 3)

        # Browser should be ranked #1
        self.assertEqual(ranked[0].module_id, "browser")
        self.assertEqual(ranked[1].module_id, "search")
        self.assertEqual(ranked[2].module_id, "python_runtime")

    def test_select_best_tool(self) -> None:
        c1 = ToolCandidate("cap_a", "mod_a", confidence_score=0.60)
        c2 = ToolCandidate("cap_b", "mod_b", confidence_score=0.98)
        best = self.engine.select_best_tool("do task", [c1, c2])
        self.assertIsNotNone(best)
        self.assertEqual(best.module_id, "mod_b")

    def test_dynamic_ranking_update_after_failures(self) -> None:
        """
        Tool A has higher initial confidence (0.95 vs 0.90), but suffers multiple runtime failures.
        Dynamic ranking should demote Tool A below Tool B.
        """
        tool_a = ToolCandidate("tool_a", "mod_a", confidence_score=0.95)
        tool_b = ToolCandidate("tool_b", "mod_b", confidence_score=0.90)

        # Initial ranking: Tool A should win
        initial_best = self.engine.select_best_tool("task", [tool_a, tool_b])
        self.assertEqual(initial_best.module_id, "mod_a")

        # Record 4 failures for Tool A
        for _ in range(4):
            self.engine.record_tool_result("tool_a", success=False, latency_ms=500)
        self.engine.record_tool_result("tool_b", success=True, latency_ms=50)

        # Updated ranking: Tool B should now win due to higher reliability!
        updated_best = self.engine.select_best_tool("task", [tool_a, tool_b])
        self.assertEqual(updated_best.module_id, "mod_b")


class DummyEngine:
    def reason(self, req: Any, decision_type: str) -> Any:
        return None


class TestCognitivePlannerToolIntelligence(unittest.TestCase):
    """Test CognitivePlanner integration with ToolIntelligenceEngine."""

    def setUp(self) -> None:
        self.planner = CognitivePlanner(DummyEngine())

    def test_planner_rank_tools(self) -> None:
        c1 = ToolCandidate("cap_a", "mod_a", confidence_score=0.50)
        c2 = ToolCandidate("cap_b", "mod_b", confidence_score=0.90)
        ranked = self.planner.rank_tools("task", [c1, c2])
        self.assertEqual(ranked[0].module_id, "mod_b")

    def test_planner_select_best_tool(self) -> None:
        c1 = ToolCandidate("cap_a", "mod_a", confidence_score=0.50)
        c2 = ToolCandidate("cap_b", "mod_b", confidence_score=0.90)
        best = self.planner.select_best_tool("task", [c1, c2])
        self.assertEqual(best.module_id, "mod_b")


if __name__ == "__main__":
    unittest.main()
