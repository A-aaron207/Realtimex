"""
Security Audit Logger for Realtimex.

Handles append-only tracking of security violations, permission checks, and policy overrides.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Optional


class SecurityAuditor:
    """Immutable audit trail for permission audits and sandbox boundary breaches."""

    def __init__(
        self,
        event_bus: Any = None,
        filepath: Optional[str] = None,
    ) -> None:
        """
        Initialize SecurityAuditor.
        
        Args:
            event_bus: Optional Event Bus for event-driven updates
            filepath: Optional audit trail log file path
        """
        self.bus = event_bus
        self.filepath = filepath
        self._records: list[dict[str, Any]] = []
        self._lock = threading.RLock()

        if self.filepath:
            os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)

    def record(self, event_type: str, status: str, details: dict[str, Any]) -> None:
        """
        Record a security-sensitive event.
        
        Args:
            event_type: Category (e.g. 'SandboxViolation', 'PermissionDecision')
            status: Outcome ('ALLOWED', 'DENIED', 'VIOLATED')
            details: Extra details metadata dictionary
        """
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "status": status,
            "details": details,
        }

        with self._lock:
            self._records.append(entry)

        if self.filepath:
            try:
                with open(self.filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception:
                pass

        # Emit AuditRecorded event
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name="AuditRecorded",
                        source="security.audit",
                        payload=entry,
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass

    def get_records(self) -> list[dict[str, Any]]:
        """Retrieve copy of all audit trail records."""
        with self._lock:
            return [rec.copy() for rec in self._records]
