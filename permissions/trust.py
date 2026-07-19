"""
Trust Manager implementation for tracking worker/module trust in the Realtimex Permission System.
"""

from __future__ import annotations

import threading


class TrustManager:
    """
    Manages trust levels for workers, modules, services, and plugins.
    Trust scores range from 0.0 (untrusted) to 1.0 (fully trusted) and
    influence user review delegation, but cannot override rule/policy bans.
    """

    def __init__(self, default_trust: float = 0.5) -> None:
        self.default_trust = default_trust
        self._lock = threading.Lock()
        self._trust_scores: dict[str, float] = {}

    def get_trust_score(self, entity_id: str) -> float:
        """Get the trust score of an entity (defaulting if not explicitly registered)."""
        with self._lock:
            return self._trust_scores.get(entity_id, self.default_trust)

    def set_trust_score(self, entity_id: str, score: float) -> None:
        """Set the trust score of an entity."""
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"Trust score must be between 0.0 and 1.0. Got: {score}")
        with self._lock:
            self._trust_scores[entity_id] = score

    def is_trusted(self, entity_id: str, threshold: float = 0.5) -> bool:
        """Check if an entity meets a specific trust threshold."""
        return self.get_trust_score(entity_id) >= threshold

    def clear(self) -> None:
        """Clear all stored trust scores."""
        with self._lock:
            self._trust_scores.clear()
