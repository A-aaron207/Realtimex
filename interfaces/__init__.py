"""
Realtimex Interface Layer.

Provides all external communication with the Kernel through multiple interfaces:
- CLI Interface
- REST API
- WebSocket API
- Voice Interface (placeholder)
- GUI Interface (placeholder)
"""

from .base import Interface, Request, Response
from .manager import InterfaceManager
from .registry import InterfaceRegistry
from .session import SessionManager
from .authentication import AuthenticationManager, AuthorizationManager
from .serialization import SerializationManager

from .cli import CLIInterface
from .api import RESTInterface
from .api.websocket import WebSocketInterface
from .voice import VoiceInterface
from .gui import GUIInterface

from .exceptions import (
    InterfaceError,
    InterfaceInitializationError,
    InterfaceNotAvailableError,
    RequestValidationError,
    ResponseSerializationError,
    SessionError,
    AuthenticationError,
    AuthorizationError,
    InterfaceManagerError,
    SerializationError,
)

__all__ = [
    # Core classes
    "Interface",
    "Request",
    "Response",
    
    # Managers
    "InterfaceManager",
    "InterfaceRegistry",
    "SessionManager",
    "AuthenticationManager",
    "AuthorizationManager",
    "SerializationManager",
    
    # Interface implementations
    "CLIInterface",
    "RESTInterface",
    "WebSocketInterface",
    "VoiceInterface",
    "GUIInterface",
    
    # Exceptions
    "InterfaceError",
    "InterfaceInitializationError",
    "InterfaceNotAvailableError",
    "RequestValidationError",
    "ResponseSerializationError",
    "SessionError",
    "AuthenticationError",
    "AuthorizationError",
    "InterfaceManagerError",
    "SerializationError",
]
