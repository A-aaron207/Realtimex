"""
Persistence engine for saving trust states and persistent approvals to disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from permissions.exceptions import PermissionValidationError


class PermissionPersistence:
    """
    Saves and loads security policies, overrides, and trust records to disk.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise PermissionValidationError(f"Failed to initialize permission directory: {e}") from e

    def save_trust_scores(self, scores: dict[str, float]) -> None:
        """Serialize and save trust score ratings to disk."""
        file_path = self.directory / "trust_scores.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(scores, f, indent=2)
        except Exception as e:
            raise PermissionValidationError(f"Failed to persist trust scores: {e}") from e

    def load_trust_scores(self) -> dict[str, float]:
        """Load and deserialize trust scores from disk."""
        file_path = self.directory / "trust_scores.json"
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return {k: float(v) for k, v in data.items()}
        except Exception as e:
            raise PermissionValidationError(f"Failed to load trust scores: {e}") from e

    def save_persistent_approvals(self, approvals: list[dict[str, Any]]) -> None:
        """Serialize and save persistent approvals to disk."""
        file_path = self.directory / "persistent_approvals.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(approvals, f, indent=2)
        except Exception as e:
            raise PermissionValidationError(f"Failed to persist approvals: {e}") from e

    def load_persistent_approvals(self) -> list[dict[str, Any]]:
        """Load persistent approvals from disk."""
        file_path = self.directory / "persistent_approvals.json"
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
        except Exception as e:
            raise PermissionValidationError(f"Failed to load persistent approvals: {e}") from e
