"""
Dedicated event logger to write events to disk as JSON Lines.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from events.event import Event, EventPriority


class EventLogger:
    """Logs every event to a structured JSONL file and optionally to the kernel logger."""
    
    DEFAULT_FILENAME = "event_log.jsonl"
    
    def __init__(self, log_directory: Path, filename: str = DEFAULT_FILENAME, 
                 console_logger: logging.Logger | None = None) -> None:
        self._log_directory = Path(log_directory)
        self._filepath = self._log_directory / filename
        self._console_logger = console_logger or logging.getLogger("realtimex.events.logger")
        self._lock = threading.Lock()
        self._ensure_directory()
    
    def log_event(self, event: Event) -> None:
        """Log an event to both the JSONL file and the console logger."""
        # Log via the console logger at appropriate level
        log_msg = f"Event[{event.name}] id={event.event_id} task={event.task_id} source={event.source}"
        
        priority_val = getattr(event.priority, "value", event.priority)
        if priority_val >= 30:
            self._console_logger.error(log_msg)
        elif priority_val >= 20:
            self._console_logger.warning(log_msg)
        elif priority_val >= 10:
            self._console_logger.info(log_msg)
        else:
            self._console_logger.debug(log_msg)
            
        # Write to JSONL file
        try:
            entry = self._format_log_entry(event)
            self._write_line(entry)
        except Exception as e:
            self._console_logger.error(f"Failed to write event log to file: {e}")
    
    def _format_log_entry(self, event: Event) -> dict[str, Any]:
        """Format event for JSONL logging. Include:
        - timestamp
        - event_id
        - event_type (name)
        - source
        - task_id
        - priority
        - payload
        """
        return {
            "timestamp": event.timestamp.isoformat(),
            "event_id": event.event_id,
            "event_type": event.name,
            "source": event.source,
            "task_id": event.task_id,
            "priority": getattr(event.priority, "name", str(event.priority)),
            "payload": event.payload,
        }
    
    def _write_line(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._ensure_directory()
            with open(self._filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
    
    def _ensure_directory(self) -> None:
        try:
            self._log_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            if self._console_logger:
                self._console_logger.error(f"Failed to create directory {self._log_directory}: {e}")
    
    @property
    def filepath(self) -> Path:
        return self._filepath
