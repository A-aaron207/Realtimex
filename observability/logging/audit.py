"""
Audit Logger for Realtimex.

Handles recording immutable, security-sensitive logs and emitting audit events.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Optional


class AuditLogger:
    """
    Manages security auditing for Realtimex.
    
    Provides append-only records of sensitive actions, writes to
    an audit file trail, and notifies the event system of updates.
    """

    def __init__(
        self,
        event_bus: Any = None,
        filepath: Optional[str] = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize Audit Logger.
        
        Args:
            event_bus: Optional Event Bus for emitting AuditRecorded events
            filepath: Optional file path to write audit logs to disk
            logger: Optional logger instance
        """
        self.bus = event_bus
        self.filepath = filepath
        self.logger = logger or logging.getLogger("realtimex.observability.audit")
        self._records: list[dict[str, Any]] = []
        self._lock = threading.RLock()

        if self.filepath:
            os.makedirs(os.path.dirname(os.path.abspath(self.filepath)), exist_ok=True)

    def record(
        self,
        action: str,
        actor: str,
        status: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Record a security-sensitive event.
        
        Args:
            action: Description of event (e.g. 'permission.approve')
            actor: Subject initiating event (e.g. 'admin_user')
            status: Event outcome status ('success', 'failure')
            details: Optional metadata context dictionary
        """
        entry = {
            "timestamp": time.time(),
            "action": action,
            "actor": actor,
            "status": status,
            "details": details or {},
        }

        with self._lock:
            # Append-only list
            self._records.append(entry)

        # Append to audit file trail if path is present
        if self.filepath:
            try:
                with open(self.filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception as e:
                self.logger.error("Failed to write audit entry to file: %s", e)

        self.logger.info("AUDIT: action=%s actor=%s status=%s", action, actor, status)

        # Emit AuditRecorded event
        self._emit_event("AuditRecorded", entry)

    def get_records(self) -> list[dict[str, Any]]:
        """Retrieve copy of all audit trail records."""
        with self._lock:
            return [rec.copy() for rec in self._records]

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit audit event via Event Bus."""
        if self.bus:
            try:
                from events.event import Event, EventPriority
                self.bus.publish(
                    Event(
                        name=event_type,
                        source="observability.audit",
                        payload=data,
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass
