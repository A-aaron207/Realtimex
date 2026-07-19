"""
Serialization utilities for Realtimex Interface Layer.

Handles JSON serialization/deserialization for Request/Response objects
and complex types.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Type, TypeVar
from dataclasses import asdict, is_dataclass

from interfaces.base import Request, Response
from interfaces.exceptions import SerializationError


T = TypeVar('T')


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for complex types."""

    def default(self, obj: Any) -> Any:
        """Encode complex types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        if is_dataclass(obj):
            return asdict(obj)
        
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        
        if isinstance(obj, Exception):
            return {
                "type": type(obj).__name__,
                "message": str(obj),
            }
        
        return super().default(obj)


class SerializationManager:
    """
    Manages serialization and deserialization of interface objects.
    
    Supports:
    - Request/Response serialization
    - JSON encoding/decoding
    - Type validation
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize SerializationManager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.interfaces.serialization")

    def serialize_request(self, request: Request) -> str:
        """
        Serialize Request to JSON string.
        
        Args:
            request: Request object to serialize
            
        Returns:
            JSON string representation
            
        Raises:
            SerializationError: If serialization fails
        """
        try:
            data = {
                "request_id": request.request_id,
                "session_id": request.session_id,
                "timestamp": request.timestamp.isoformat(),
                "user_input": request.user_input,
                "interface_type": request.interface_type,
                "user_id": request.user_id,
                "metadata": request.metadata,
            }
            return json.dumps(data, cls=JSONEncoder)
        except Exception as e:
            raise SerializationError(f"Failed to serialize Request: {e}") from e

    def deserialize_request(self, data: str | dict) -> Request:
        """
        Deserialize Request from JSON string or dict.
        
        Args:
            data: JSON string or dictionary
            
        Returns:
            Request object
            
        Raises:
            SerializationError: If deserialization fails
        """
        try:
            if isinstance(data, str):
                obj = json.loads(data)
            else:
                obj = data
            
            return Request(
                request_id=obj.get("request_id"),
                session_id=obj.get("session_id"),
                timestamp=datetime.fromisoformat(obj.get("timestamp", "")),
                user_input=obj.get("user_input"),
                interface_type=obj.get("interface_type"),
                user_id=obj.get("user_id"),
                metadata=obj.get("metadata", {}),
            )
        except Exception as e:
            raise SerializationError(f"Failed to deserialize Request: {e}") from e

    def serialize_response(self, response: Response) -> str:
        """
        Serialize Response to JSON string.
        
        Args:
            response: Response object to serialize
            
        Returns:
            JSON string representation
            
        Raises:
            SerializationError: If serialization fails
        """
        try:
            data = {
                "request_id": response.request_id,
                "status": response.status,
                "message": response.message,
                "artifacts": response.artifacts,
                "events": response.events,
                "metadata": response.metadata,
            }
            return json.dumps(data, cls=JSONEncoder)
        except Exception as e:
            raise SerializationError(f"Failed to serialize Response: {e}") from e

    def deserialize_response(self, data: str | dict) -> Response:
        """
        Deserialize Response from JSON string or dict.
        
        Args:
            data: JSON string or dictionary
            
        Returns:
            Response object
            
        Raises:
            SerializationError: If deserialization fails
        """
        try:
            if isinstance(data, str):
                obj = json.loads(data)
            else:
                obj = data
            
            return Response(
                request_id=obj.get("request_id"),
                status=obj.get("status", "unknown"),
                message=obj.get("message", ""),
                artifacts=obj.get("artifacts", {}),
                events=obj.get("events", []),
                metadata=obj.get("metadata", {}),
            )
        except Exception as e:
            raise SerializationError(f"Failed to deserialize Response: {e}") from e

    def serialize_object(self, obj: Any) -> str:
        """
        Serialize arbitrary object to JSON string.
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON string representation
            
        Raises:
            SerializationError: If serialization fails
        """
        try:
            return json.dumps(obj, cls=JSONEncoder)
        except Exception as e:
            raise SerializationError(f"Failed to serialize object: {e}") from e

    def deserialize_object(self, data: str) -> Any:
        """
        Deserialize arbitrary object from JSON string.
        
        Args:
            data: JSON string
            
        Returns:
            Deserialized object
            
        Raises:
            SerializationError: If deserialization fails
        """
        try:
            return json.loads(data)
        except Exception as e:
            raise SerializationError(f"Failed to deserialize object: {e}") from e

    def to_dict(self, obj: Any) -> dict:
        """
        Convert object to dictionary.
        
        Args:
            obj: Object to convert
            
        Returns:
            Dictionary representation
        """
        if is_dataclass(obj):
            return asdict(obj)
        
        if hasattr(obj, '__dict__'):
            return obj.__dict__.copy()
        
        return {}

    def validate_type(self, obj: Any, expected_type: Type) -> bool:
        """
        Validate object type.
        
        Args:
            obj: Object to validate
            expected_type: Expected type
            
        Returns:
            True if object is of expected type
        """
        return isinstance(obj, expected_type)
