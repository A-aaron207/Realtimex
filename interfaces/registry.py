"""
Interface Registry for Realtimex.

Discovers and manages available interfaces.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from interfaces.base import Interface
from interfaces.exceptions import InterfaceNotAvailableError


class InterfaceRegistry:
    """
    Registry for discovering and managing available interfaces.
    
    Allows registration, retrieval, and iteration of interfaces.
    Thread-safe operations.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize registry.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.interfaces.registry")
        self._interfaces: dict[str, Interface] = {}  # by interface_type
        self._lock = threading.RLock()
    
    def register(self, interface: Interface) -> None:
        """
        Register an interface.
        
        Thread-safe registration.
        
        Args:
            interface: Interface instance to register
            
        Raises:
            ValueError: If interface with same type already registered
        """
        with self._lock:
            if interface.interface_type in self._interfaces:
                raise ValueError(
                    f"Interface type '{interface.interface_type}' already registered"
                )
            self._interfaces[interface.interface_type] = interface
            self.logger.info(
                "Interface registered: %s (type=%s)",
                interface.name, interface.interface_type
            )
    
    def unregister(self, interface_type: str) -> bool:
        """
        Unregister an interface.
        
        Args:
            interface_type: Interface type to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        with self._lock:
            if interface_type in self._interfaces:
                interface = self._interfaces.pop(interface_type)
                self.logger.info("Interface unregistered: %s", interface.name)
                return True
            return False
    
    def get(self, interface_type: str) -> Optional[Interface]:
        """
        Get interface by type.
        
        Args:
            interface_type: Interface type to retrieve
            
        Returns:
            Interface object or None if not found
        """
        with self._lock:
            return self._interfaces.get(interface_type)
    
    def get_available(self) -> list[Interface]:
        """
        Get all registered and running interfaces.
        
        Returns:
            List of available interfaces
        """
        with self._lock:
            return [i for i in self._interfaces.values() if i.is_available]
    
    def list_all(self) -> list[Interface]:
        """
        List all registered interfaces.
        
        Returns:
            List of all Interface objects
        """
        with self._lock:
            return list(self._interfaces.values())
    
    def list(self) -> list[Interface]:
        """
        List all registered interfaces (alias for list_all).
        
        Returns:
            List of all Interface objects
        """
        return self.list_all()
    
    def list_by_type(self, interface_type: str) -> Optional[Interface]:
        """
        Get interface by type.
        
        Args:
            interface_type: Interface type identifier
            
        Returns:
            Interface object or None
        """
        with self._lock:
            return self._interfaces.get(interface_type)
    
    def count(self) -> int:
        """Get total number of registered interfaces."""
        with self._lock:
            return len(self._interfaces)
    
    def count_available(self) -> int:
        """Get number of available (running) interfaces."""
        with self._lock:
            return sum(1 for i in self._interfaces.values() if i.is_available)
