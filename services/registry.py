"""
Service Registry.

Centralized, thread-safe registry of services known to the Kernel.
Modules declare the services they depend on in their manifest; the
Kernel resolves those dependencies against this registry. The
registry itself never instantiates, starts, or stops services -- it
only tracks which service objects exist and makes them retrievable by
name.
"""

from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager

from services.base import BaseService

_current_registry: contextvars.ContextVar[ServiceRegistry | None] = contextvars.ContextVar(
    "current_service_registry", default=None
)


class DuplicateServiceError(Exception):
    """Raised when attempting to register a service name that already exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"A service named {name!r} is already registered.")


class ServiceNotFoundError(Exception):
    """Raised when a requested service name is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No service named {name!r} is registered.")


class ServiceRegistry:
    """
    Thread-safe registry mapping service names to service instances.

    Responsibilities:
        - Register and unregister BaseService instances.
        - Retrieve services by name.
        - Report whether a service name is registered.
        - List all registered service names.

    This class contains no business logic about what a service does;
    it is purely a lookup table guarded by a lock so it can safely be
    shared across the Kernel and any concurrently loading modules.
    Supports context-local isolation so multiple Kernel instances
    can run in the same process without global singleton collisions.
    """

    _instance: ServiceRegistry | None = None

    @classmethod
    def get_instance(cls) -> ServiceRegistry:
        """
        Get the active ServiceRegistry instance.
        Prioritizes the context-local instance if set, falling back to the singleton instance.
        """
        ctx_instance = _current_registry.get()
        if ctx_instance is not None:
            return ctx_instance
        if cls._instance is not None:
            return cls._instance
        raise RuntimeError("ServiceRegistry has not been initialized.")

    @classmethod
    def set_current(cls, instance: ServiceRegistry | None) -> None:
        """Set the current context-local ServiceRegistry instance."""
        _current_registry.set(instance)

    @classmethod
    def reset(cls) -> None:
        """Reset both global singleton and context-local instances."""
        cls._instance = None
        _current_registry.set(None)

    @contextmanager
    def as_current(self):
        """Context manager to scope this ServiceRegistry instance to the current context."""
        token = _current_registry.set(self)
        try:
            yield self
        finally:
            _current_registry.reset(token)

    def __init__(self, set_as_current: bool = True) -> None:
        """Initialize an empty, thread-safe service registry."""
        self._services: dict[str, BaseService] = {}
        self._lock = threading.RLock()
        if set_as_current:
            _current_registry.set(self)

    def register(self, service: BaseService) -> None:
        """
        Register a service instance.

        Args:
            service: The BaseService instance to register, keyed by
                its `name` property.

        Raises:
            DuplicateServiceError: If a service with the same name is
                already registered.
        """
        with self._lock:
            if service.name in self._services:
                raise DuplicateServiceError(service.name)
            self._services[service.name] = service

    def unregister(self, name: str) -> None:
        """
        Remove a service from the registry, if present.

        Args:
            name: The name of the service to remove. Silently does
                nothing if no such service is registered.
        """
        with self._lock:
            self._services.pop(name, None)

    def get(self, name: str) -> BaseService:
        """
        Retrieve a registered service by name.

        Args:
            name: The name of the service to retrieve.

        Returns:
            The registered BaseService instance.

        Raises:
            ServiceNotFoundError: If no service with that name is registered.
        """
        with self._lock:
            service = self._services.get(name)
            if service is None:
                raise ServiceNotFoundError(name)
            return service

    def exists(self, name: str) -> bool:
        """
        Check whether a service name is currently registered.

        Args:
            name: The service name to check.

        Returns:
            True if a service with that name is registered, False otherwise.
        """
        with self._lock:
            return name in self._services

    def list_services(self) -> list[str]:
        """Return the names of all currently registered services."""
        with self._lock:
            return list(self._services.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._services)
