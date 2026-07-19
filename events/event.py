"""
Core event definition for the Realtimex Event System.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

class EventPriority(IntEnum):
    """Priority levels for event dispatch."""
    LOW = 0
    NORMAL = 10
    HIGH = 20
    CRITICAL = 30

@dataclass(frozen=True)
class Event:
    """
    Immutable representation of an event in the system.
    """
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "kernel"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    event_type: str = ""
    task_id: str = ""
    priority: EventPriority = EventPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type:
            object.__setattr__(self, "event_type", self.name)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the event to a dictionary."""
        return {
            "name": self.name,
            "payload": self.payload,
            "source": self.source,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "task_id": self.task_id,
            "priority": self.priority.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize an event from a dictionary."""
        kwargs = data.copy()
        if "timestamp" in kwargs and isinstance(kwargs["timestamp"], str):
            kwargs["timestamp"] = datetime.fromisoformat(kwargs["timestamp"])
        if "priority" in kwargs and isinstance(kwargs["priority"], int):
            kwargs["priority"] = EventPriority(kwargs["priority"])
            
        return cls(**kwargs)

    def __str__(self) -> str:
        """Return a descriptive string representation of the event."""
        return f"Event(name={self.name!r}, source={self.source!r}, priority={self.priority.name}, timestamp={self.timestamp.isoformat()})"
