"""
Dependency Container for the Realtimex Kernel.

Holds and resolves core subsystems and manager instances to facilitate
dependency injection throughout the runtime.
"""

from __future__ import annotations
import threading
from typing import Any, Dict


class DependencyContainer:
    """
    A thread-safe dependency container for registering and resolving services.

    All public methods acquire an RLock so that concurrent boot threads,
    hot-reload paths, and background monitors can safely register or resolve
    dependencies without data corruption.
    """

    def __init__(self) -> None:
        """Initialize an empty dependency container."""
        self._registry: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def register(self, key: str, instance: Any) -> None:
        """
        Register a dependency instance with a unique key.

        Args:
            key: The string identifier for the dependency.
            instance: The instance to register.
        """
        with self._lock:
            self._registry[key] = instance

    def resolve(self, key: str) -> Any:
        """
        Resolve and return a registered dependency.

        Args:
            key: The identifier of the dependency to resolve.

        Returns:
            The registered instance.

        Raises:
            KeyError: If no dependency is registered under the given key.
        """
        with self._lock:
            if key not in self._registry:
                raise KeyError(f"Dependency {key!r} not registered in container.")
            return self._registry[key]

    def has(self, key: str) -> bool:
        """
        Check if a dependency is registered under the given key.

        Args:
            key: The identifier to check.

        Returns:
            True if registered, False otherwise.
        """
        with self._lock:
            return key in self._registry
