"""
Event persistence to disk as JSON Lines (.jsonl).
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from events.event import Event


class EventPersistence:
    """Persists events to disk as JSON Lines (.jsonl)."""
    
    DEFAULT_FILENAME = "events.jsonl"
    
    def __init__(self, log_directory: Path, filename: str = DEFAULT_FILENAME) -> None:
        self._log_directory = Path(log_directory)
        self._filepath = self._log_directory / filename
        self._lock = threading.Lock()
        self._logger = logging.getLogger("realtimex.events.persistence")
        self._ensure_directory()
    
    def persist(self, event: Event) -> None:
        """Append a single event as a JSON line to the events file.
        Thread-safe. Catches and logs I/O errors without raising."""
        try:
            line = self._serialize_event(event)
            with self._lock:
                with open(self._filepath, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            self._logger.error(f"Failed to persist event {event.event_id}: {e}")
    
    def load_all(self) -> list[Event]:
        """Load all persisted events from the file. Returns empty list if file doesn't exist."""
        if not self._filepath.exists():
            return []
            
        events = []
        with self._lock:
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        event = self._deserialize_event(line.strip())
                        if event:
                            events.append(event)
            except Exception as e:
                self._logger.error(f"Failed to load events from {self._filepath}: {e}")
                
        return events
    
    def load_since(self, since: datetime) -> list[Event]:
        """Load events persisted after the given timestamp."""
        events = []
        for event in self.load_all():
            if event.timestamp > since:
                events.append(event)
        return events
    
    def load_for_task(self, task_id: str) -> list[Event]:
        """Load all events associated with a specific task_id."""
        events = []
        for event in self.load_all():
            if event.task_id == task_id:
                events.append(event)
        return events
    
    @property
    def filepath(self) -> Path:
        return self._filepath
    
    def _ensure_directory(self) -> None:
        try:
            self._log_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._logger.error(f"Failed to create directory {self._log_directory}: {e}")
    
    def _serialize_event(self, event: Event) -> str:
        """Serialize event to a JSON string."""
        return json.dumps(event.to_dict())
    
    def _deserialize_event(self, line: str) -> Event | None:
        """Deserialize a JSON line to an Event. Returns None on parse failure."""
        if not line:
            return None
        try:
            data = json.loads(line)
            return Event.from_dict(data)
        except Exception as e:
            self._logger.warning(f"Failed to deserialize event line: {e}")
            return None
