"""
Custom exceptions for the Realtimex Interface Layer.
"""

from __future__ import annotations


class InterfaceError(Exception):
    """Base exception for all Interface Layer errors."""


class InterfaceInitializationError(InterfaceError):
    """Raised when interface initialization fails."""


class InterfaceNotAvailableError(InterfaceError):
    """Raised when interface is not available or not started."""


class RequestValidationError(InterfaceError):
    """Raised when request validation fails."""


class ResponseSerializationError(InterfaceError):
    """Raised when response serialization fails."""


class SessionError(InterfaceError):
    """Raised when session management fails."""


class AuthenticationError(InterfaceError):
    """Raised when authentication fails."""


class AuthorizationError(InterfaceError):
    """Raised when authorization fails."""


class InterfaceManagerError(InterfaceError):
    """Raised when interface manager operations fail."""


class SerializationError(InterfaceError):
    """Raised when serialization/deserialization fails."""
