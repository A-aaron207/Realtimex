"""
Base Capability definitions.

A "capability" is a named unit of functionality (e.g. "summarize_text",
"web_search") that a module declares it can provide. The Kernel
tracks *which module provides which capability* through the
Capability Registry, but it never invokes the capability itself --
execution belongs to a future Task Manager / Scheduler milestone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CapabilityProvider(Protocol):
    """
    Structural interface a module must satisfy to provide capabilities.

    Any object exposing a `module_id` attribute and a `capabilities`
    sequence can act as a capability provider. Concrete modules
    implement this informally by defining those attributes on their
    `module.py` entry point class -- no explicit inheritance is
    required, since this is a Protocol.
    """

    module_id: str
    capabilities: list[str]


@dataclass(frozen=True)
class CapabilityDescriptor:
    """
    Metadata describing a single registered capability.

    Attributes:
        name: The capability's unique identifier (e.g. "summarize_text").
        provider_id: The module_id of the module that provides this capability.
        metadata: Arbitrary additional metadata about the capability.
    """

    name: str
    provider_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
