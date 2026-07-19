"""
Capability Registry.

Centralized, thread-safe registry mapping capability names to the
module(s) that provide them. When the Kernel needs to answer "who can
summarize text?", it asks this registry -- it never executes the
capability itself. Execution is the responsibility of a future Task
Manager / Scheduler milestone.

A single capability name may have more than one provider (e.g. two
modules both implementing "web_search"); the registry tracks all of
them and lets callers choose.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from capabilities.base import CapabilityDescriptor


class CapabilityNotFoundError(Exception):
    """Raised when a requested capability has no registered provider."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No provider is registered for capability {name!r}.")


class CapabilityRegistry:
    """
    Thread-safe registry mapping capability names to provider modules.

    Responsibilities:
        - Register a capability along with the module that provides it.
        - Remove a capability (optionally scoped to a specific provider).
        - Find the first available provider for a capability.
        - List every provider registered for a capability.
        - List all known capability names.

    This class performs no execution, invocation, or permission
    checking -- it is purely a lookup table of "who can do what".
    """

    def __init__(self) -> None:
        """Initialize an empty, thread-safe capability registry."""
        self._providers: dict[str, list[CapabilityDescriptor]] = defaultdict(list)
        self._lock = threading.RLock()

    def register(self, capability: str, provider_id: str, metadata: dict[str, Any] | None = None) -> None:
        """
        Register a module as a provider of a capability.

        Registering the same (capability, provider_id) pair twice is
        idempotent -- the second registration simply replaces the
        first's metadata rather than creating a duplicate entry.

        Args:
            capability: The capability name being provided (e.g. "summarize_text").
            provider_id: The module_id of the providing module.
            metadata: Optional additional metadata about this provider's
                implementation of the capability.
        """
        descriptor = CapabilityDescriptor(name=capability, provider_id=provider_id, metadata=metadata or {})
        with self._lock:
            existing = self._providers[capability]
            self._providers[capability] = [d for d in existing if d.provider_id != provider_id]
            self._providers[capability].append(descriptor)

    def unregister(self, capability: str, provider_id: str | None = None) -> None:
        """
        Remove a capability registration.

        Args:
            capability: The capability name to remove.
            provider_id: If given, only remove the registration for
                this specific provider, leaving other providers of the
                same capability intact. If omitted, all providers of
                this capability are removed.
        """
        with self._lock:
            if capability not in self._providers:
                return
            if provider_id is None:
                del self._providers[capability]
            else:
                remaining = [d for d in self._providers[capability] if d.provider_id != provider_id]
                if remaining:
                    self._providers[capability] = remaining
                else:
                    del self._providers[capability]

    def unregister_provider(self, provider_id: str) -> None:
        """
        Remove every capability registration belonging to a given module.

        Used when a module is unloaded, so all of its previously
        advertised capabilities disappear from the registry at once.

        Args:
            provider_id: The module_id whose capabilities should be removed.
        """
        with self._lock:
            for capability in list(self._providers.keys()):
                remaining = [d for d in self._providers[capability] if d.provider_id != provider_id]
                if remaining:
                    self._providers[capability] = remaining
                else:
                    del self._providers[capability]

    def find(self, capability: str) -> CapabilityDescriptor:
        """
        Find the first available provider for a capability.

        Args:
            capability: The capability name to look up.

        Returns:
            The CapabilityDescriptor for the first registered provider.

        Raises:
            CapabilityNotFoundError: If no provider is registered for
                this capability.
        """
        with self._lock:
            descriptors = self._providers.get(capability)
            if not descriptors:
                raise CapabilityNotFoundError(capability)
            return descriptors[0]

    def providers(self, capability: str) -> list[CapabilityDescriptor]:
        """
        List every provider registered for a capability.

        Args:
            capability: The capability name to look up.

        Returns:
            A list of CapabilityDescriptor instances, empty if no
            provider is registered.
        """
        with self._lock:
            return list(self._providers.get(capability, []))

    def list_capabilities(self) -> list[str]:
        """Return the names of all currently registered capabilities."""
        with self._lock:
            return list(self._providers.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._providers)
