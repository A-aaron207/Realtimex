"""
Module entry point contract.

Every module's `module.py` must define a top-level class named
`Module` that satisfies this contract: it must be constructible with
no arguments, expose a `module_id` attribute matching its manifest,
and expose a `capabilities` list. The loader uses this contract to
verify a dynamically imported module before registering it, without
needing to know anything about what the module actually does.

Modules never communicate with each other and never instantiate
services directly -- they only declare what they provide and depend
on; the Kernel wires everything together.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ModuleEntryPoint(ABC):
    """
    Abstract base class that every module's `Module` class should extend.

    Responsibilities:
        - Declare a `module_id` matching the manifest's module_id.
        - Declare the list of capability names this module provides.

    Concrete modules may optionally implement `on_load` /
    `on_unload` hooks for future lifecycle milestones; Milestone 2
    does not call them yet beyond simple instantiation.
    """

    #: Unique identifier, expected to match the manifest's module_id.
    module_id: str = ""

    #: Capability names this module provides, expected to match the manifest.
    capabilities: list[str] = []

    @abstractmethod
    def describe(self) -> str:
        """Return a short human-readable description of this module."""
        raise NotImplementedError
