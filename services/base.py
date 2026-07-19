"""
Base Service definition.

A "service" in Realtimex is a named, long-lived component that the
Kernel makes available to modules -- for example a logger, a model
gateway, or a future memory store. Modules never instantiate services
themselves; they declare which services they need in their manifest,
and the Kernel resolves those declarations through the Service
Registry.

This module defines the minimal contract a service must satisfy to be
registered. Milestone 2 does not implement service lifecycle
management (start/stop/health checks) -- only identity and metadata.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseService(ABC):
    """
    Abstract base class for all Kernel-managed services.

    Responsibilities:
        - Expose a stable, unique service name.
        - Expose descriptive metadata about the service.

    Concrete services (LoggerService, ModelGatewayService, etc.) are
    implemented in future milestones. Milestone 2 only needs the
    contract so the Service Registry has something concrete to store
    and validate against.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique, stable name this service is registered under."""
        raise NotImplementedError

    @property
    def metadata(self) -> dict[str, Any]:
        """
        Descriptive metadata about this service.

        Subclasses may override this to expose version, capabilities,
        or configuration details. Defaults to an empty dictionary.
        """
        return {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


class SimpleService(BaseService):
    """
    A minimal, concrete BaseService implementation backed by a plain
    name and metadata dictionary.

    Useful for registering lightweight or placeholder services (as
    used internally by the Kernel boot sequence) without requiring a
    dedicated class for each one.
    """

    def __init__(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        """
        Initialize a SimpleService.

        Args:
            name: The unique name to register this service under.
            metadata: Optional descriptive metadata about the service.
        """
        self._name = name
        self._metadata = metadata or {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)
