"""
Base interface contract for Realtimex interfaces.

All interfaces must implement this contract to communicate with the Kernel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Request:
    """
    Standard request object passed to the Kernel.
    
    Attributes:
        request_id: Unique request identifier
        session_id: Session ID for this request
        timestamp: When request was created
        user_input: Input from user (command, query, data, etc.)
        interface_type: Type of interface (cli, rest, websocket, voice, gui)
        user_id: User making the request
        metadata: Additional request metadata
    """
    request_id: str
    session_id: str
    timestamp: datetime
    user_input: Any
    interface_type: str
    user_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    """
    Standard response object returned from the Kernel.
    
    Attributes:
        request_id: ID of the request this responds to
        status: Response status (success, error, pending, etc.)
        message: Human-readable response message
        data: Response payload/data
        artifacts: Files, logs, or other artifacts
        events: Events generated during processing
        metadata: Additional response metadata
    """
    request_id: str
    status: str  # success, error, pending, cancelled
    message: str = ""
    data: Any = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize response to dictionary."""
        return {
            "request_id": self.request_id,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "artifacts": self.artifacts,
            "events": self.events,
            "metadata": self.metadata,
        }


class Interface(ABC):
    """
    Abstract base class for all Realtimex interfaces.
    
    Every interface must implement this contract to communicate with the Kernel.
    Interfaces translate requests and responses but contain NO business logic.
    """

    def __init__(self, name: str, interface_type: str) -> None:
        """
        Initialize interface.
        
        Args:
            name: Interface name (e.g., "CLI", "REST API", "WebSocket")
            interface_type: Interface type identifier (e.g., "cli", "rest", "ws")
        """
        self.name = name
        self.interface_type = interface_type
        self.is_running = False

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the interface.
        
        Setup connections, load configurations, prepare resources.
        Called before start().
        
        Raises:
            InterfaceInitializationError: If initialization fails
        """

    @abstractmethod
    def start(self) -> None:
        """
        Start the interface.
        
        Begin accepting requests from users/clients.
        
        Raises:
            InterfaceInitializationError: If startup fails
        """

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the interface.
        
        Gracefully shutdown, close connections, cleanup resources.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """
        Perform final shutdown.
        
        Called when kernel is shutting down.
        Ensure all resources are released.
        """

    @abstractmethod
    def receive(self) -> Optional[Request]:
        """
        Receive next request from user/client.
        
        Block until a request is available or return None if no request.
        
        Returns:
            Request object or None if no requests available
        """

    @abstractmethod
    def send(self, response: Response) -> None:
        """
        Send response back to user/client.
        
        Args:
            response: Response object to send
        """

    @property
    def is_available(self) -> bool:
        """Check if interface is available and running."""
        return self.is_running

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} (type={self.interface_type}, running={self.is_running})"
