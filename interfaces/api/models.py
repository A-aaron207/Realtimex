"""
REST API Models for Realtimex.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TaskCreateRequest:
    """Model for task submission request."""
    goal: str
    priority: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResponse:
    """Model for task response."""
    task_id: str
    goal: str
    state: str
    progress: int = 0
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class MemoryQueryRequest:
    """Model for memory query request."""
    query: str
    scope: Optional[str] = None
    limit: int = 10


@dataclass
class HealthResponse:
    """Model for health response."""
    status: str
    timestamp: str
    version: str = "1.0.0"


@dataclass
class MetricsResponse:
    """Model for metrics response."""
    uptime_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    active_sessions: int
