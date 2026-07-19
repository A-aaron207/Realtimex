"""
Worker Health monitoring data model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

@dataclass
class WorkerHealth:
    """
    Mutable state records tracking worker diagnostics, heartbeat timings, and restarts.
    """
    alive: bool = True
    busy: bool = False
    failed: bool = False
    restart_count: int = 0
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize health state."""
        return {
            "alive": self.alive,
            "busy": self.busy,
            "failed": self.failed,
            "restart_count": self.restart_count,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }
