"""
Session Manager for Realtimex Interface Layer.

Manages user sessions across all interfaces.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Session:
    """
    User session information.
    
    Attributes:
        session_id: Unique session identifier
        user_id: User who owns this session
        interface_type: Type of interface (cli, rest, websocket, etc.)
        created_at: When session was created
        last_activity: Timestamp of last activity
        active_tasks: IDs of tasks active in this session
        context: Session context data
        metadata: Additional session metadata
    """
    session_id: str
    user_id: str
    interface_type: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_tasks: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def age_seconds(self) -> float:
        """Get session age in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
    
    @property
    def idle_seconds(self) -> float:
        """Get idle time in seconds."""
        return (datetime.now(timezone.utc) - self.last_activity).total_seconds()
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "interface_type": self.interface_type,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "active_tasks": self.active_tasks,
            "context": self.context,
            "metadata": self.metadata,
            "age_seconds": self.age_seconds,
            "idle_seconds": self.idle_seconds,
        }


class SessionManager:
    """
    Manages user sessions across all interfaces.
    
    Thread-safe session management with creation, tracking, and cleanup.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize session manager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.interfaces.session")
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()
    
    def create_session(
        self,
        user_id: str,
        interface_type: str,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new session.
        
        Thread-safe session creation.
        
        Args:
            user_id: User creating the session
            interface_type: Interface type (cli, rest, websocket, etc.)
            context: Optional session context data
            metadata: Optional session metadata
            
        Returns:
            New Session object
        """
        with self._lock:
            session_id = str(uuid.uuid4())
            session = Session(
                session_id=session_id,
                user_id=user_id,
                interface_type=interface_type,
                context=context or {},
                metadata=metadata or {},
            )
            self._sessions[session_id] = session
            self.logger.info(
                "Session created: %s (user=%s, interface=%s)",
                session_id, user_id, interface_type
            )
            return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session object or None if not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.update_activity()
            return session
    
    def close_session(self, session_id: str) -> bool:
        """
        Close a session.
        
        Args:
            session_id: Session ID to close
            
        Returns:
            True if session was closed, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                self.logger.info("Session closed: %s (user=%s)", session_id, session.user_id)
                return True
            return False
    
    def add_task(self, session_id: str, task_id: str) -> bool:
        """
        Add task to session's active tasks.
        
        Args:
            session_id: Session ID
            task_id: Task ID to add
            
        Returns:
            True if added, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                if task_id not in session.active_tasks:
                    session.active_tasks.append(task_id)
                    session.update_activity()
                return True
            return False
    
    def remove_task(self, session_id: str, task_id: str) -> bool:
        """
        Remove task from session's active tasks.
        
        Args:
            session_id: Session ID
            task_id: Task ID to remove
            
        Returns:
            True if removed, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                if task_id in session.active_tasks:
                    session.active_tasks.remove(task_id)
                    session.update_activity()
                return True
            return False
    
    def update_context(self, session_id: str, context: dict[str, Any]) -> bool:
        """
        Update session context.
        
        Args:
            session_id: Session ID
            context: Context data to merge
            
        Returns:
            True if updated, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.context.update(context)
                session.update_activity()
                return True
            return False
    
    def list_sessions(self) -> list[Session]:
        """
        List all active sessions.
        
        Returns:
            List of Session objects
        """
        with self._lock:
            return list(self._sessions.values())
    
    def list_user_sessions(self, user_id: str) -> list[Session]:
        """
        List sessions for a specific user.
        
        Args:
            user_id: User ID to filter by
            
        Returns:
            List of Session objects for user
        """
        with self._lock:
            return [s for s in self._sessions.values() if s.user_id == user_id]
    
    def session_count(self) -> int:
        """Get total number of active sessions."""
        with self._lock:
            return len(self._sessions)
    
    def cleanup_idle_sessions(self, idle_timeout_seconds: float) -> int:
        """
        Remove sessions that have been idle for too long.
        
        Args:
            idle_timeout_seconds: Idle time threshold in seconds
            
        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            to_remove = []
            
            for session_id, session in self._sessions.items():
                idle_seconds = (now - session.last_activity).total_seconds()
                if idle_seconds > idle_timeout_seconds:
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                session = self._sessions.pop(session_id)
                self.logger.info(
                    "Session cleaned up (idle): %s (user=%s)",
                    session_id, session.user_id
                )
            
            return len(to_remove)
