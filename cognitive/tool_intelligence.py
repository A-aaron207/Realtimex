"""
Tool Intelligence module for Project D.

Ranks candidate tools and capabilities based on confidence, historical reliability,
latency budgets, and estimated costs before execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ToolCandidate:
    """
    Candidate tool option evaluated for a task intent or capability request.
    """
    capability_name: str
    module_id: str
    confidence_score: float = 1.0  # 0.0 to 1.0
    historical_reliability: float = 1.0  # 0.0 to 1.0
    estimated_latency_ms: float = 50.0
    estimated_cost: float = 0.0
    rank_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_name": self.capability_name,
            "module_id": self.module_id,
            "confidence_score": self.confidence_score,
            "historical_reliability": self.historical_reliability,
            "estimated_latency_ms": self.estimated_latency_ms,
            "estimated_cost": self.estimated_cost,
            "rank_score": self.rank_score,
            "metadata": self.metadata,
        }


class ToolPerformanceTracker:
    """
    Tracks runtime execution statistics (success rates, latencies) per capability tool.
    """

    def __init__(self) -> None:
        self._stats: dict[str, dict[str, Any]] = {}

    def record_execution(self, capability_name: str, success: bool, latency_ms: float) -> None:
        """Record an execution outcome for a capability."""
        if capability_name not in self._stats:
            self._stats[capability_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_latency_ms": 0.0,
            }

        s = self._stats[capability_name]
        s["total_calls"] += 1
        if success:
            s["successful_calls"] += 1
        else:
            s["failed_calls"] += 1
        s["total_latency_ms"] += latency_ms

    def get_reliability_rate(self, capability_name: str) -> float:
        """Get historical reliability rate (0.0 to 1.0). Defaults to 1.0 for untracked tools."""
        s = self._stats.get(capability_name)
        if not s or s["total_calls"] == 0:
            return 1.0
        return s["successful_calls"] / s["total_calls"]

    def get_average_latency_ms(self, capability_name: str) -> float:
        """Get average latency in ms. Defaults to 50.0 ms for untracked tools."""
        s = self._stats.get(capability_name)
        if not s or s["total_calls"] == 0:
            return 50.0
        return s["total_latency_ms"] / s["total_calls"]


class ToolIntelligenceEngine:
    """
    Ranks tool candidates based on weighted multi-metric optimization:
    Rank Score = 0.40 * Confidence + 0.30 * Reliability + 0.15 * LatencyScore + 0.15 * CostScore
    """

    def __init__(
        self,
        tracker: ToolPerformanceTracker | None = None,
        confidence_weight: float = 0.40,
        reliability_weight: float = 0.30,
        latency_weight: float = 0.15,
        cost_weight: float = 0.15,
    ) -> None:
        self.tracker = tracker or ToolPerformanceTracker()
        self.confidence_weight = confidence_weight
        self.reliability_weight = reliability_weight
        self.latency_weight = latency_weight
        self.cost_weight = cost_weight

    def rank_candidates(
        self,
        intent: str,
        candidates: list[ToolCandidate],
        latency_budget_ms: float = 1000.0,
        max_cost_budget: float = 1.0,
    ) -> list[ToolCandidate]:
        """
        Rank a list of ToolCandidate objects and return them sorted descending by rank_score.
        """
        if not candidates:
            return []

        ranked: list[ToolCandidate] = []

        for candidate in candidates:
            # Update historical reliability from performance tracker if available
            rel = self.tracker.get_reliability_rate(candidate.capability_name)
            candidate.historical_reliability = rel

            # Compute normalized Latency Score (1.0 = 0 ms, 0.0 = >= budget)
            latency_score = max(0.0, 1.0 - (candidate.estimated_latency_ms / max(1.0, latency_budget_ms)))

            # Compute normalized Cost Score (1.0 = $0, 0.0 = >= budget)
            cost_score = max(0.0, 1.0 - (candidate.estimated_cost / max(0.01, max_cost_budget)))

            # Composite weighted rank score
            candidate.rank_score = round(
                (self.confidence_weight * candidate.confidence_score) +
                (self.reliability_weight * candidate.historical_reliability) +
                (self.latency_weight * latency_score) +
                (self.cost_weight * cost_score),
                4
            )
            ranked.append(candidate)

        # Sort descending by rank_score
        ranked.sort(key=lambda c: c.rank_score, reverse=True)
        return ranked

    def select_best_tool(
        self,
        intent: str,
        candidates: list[ToolCandidate],
        latency_budget_ms: float = 1000.0,
    ) -> ToolCandidate | None:
        """
        Return the top ranked tool candidate.
        """
        ranked = self.rank_candidates(intent, candidates, latency_budget_ms)
        return ranked[0] if ranked else None

    def record_tool_result(self, capability_name: str, success: bool, latency_ms: float) -> None:
        """Update tracker with runtime execution outcome."""
        self.tracker.record_execution(capability_name, success, latency_ms)
