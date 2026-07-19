"""
Module manifest validation.

Every module directory under `modules/` must contain a `manifest.json`
describing its identity, the capabilities it provides, the services it
depends on, and its sandbox permissions. This module defines the
expected schema, validates raw manifest data against it, and produces
a typed `ModuleManifest` for the rest of the loader to work with.

Permission enforcement is explicitly out of scope for Milestone 2 --
this module only parses and validates the permission block, storing it
as-is for a future Permission Engine to act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ManifestValidationError(Exception):
    """Raised when a module manifest fails schema validation."""

    def __init__(self, module_path: str, reason: str) -> None:
        self.module_path = module_path
        self.reason = reason
        super().__init__(f"Invalid manifest at {module_path!r}: {reason}")


@dataclass(frozen=True)
class ModulePermissions:
    """
    Sandbox permission metadata declared by a module.

    Milestone 2 stores these values verbatim for later enforcement by
    a future Permission Engine; no access control is applied here.

    Attributes:
        filesystem: Declared filesystem access level (e.g. "none",
            "read", "read_write").
        network: Whether the module declares it needs network access.
        terminal: Whether the module declares it needs terminal/shell access.
        memory: Declared memory access scope (e.g. "none", "task_only", "global").
    """

    filesystem: str = "none"
    network: bool = False
    terminal: bool = False
    memory: str = "none"

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ModulePermissions":
        """Build a ModulePermissions from a raw permissions dictionary."""
        return ModulePermissions(
            filesystem=data.get("filesystem", "none"),
            network=bool(data.get("network", False)),
            terminal=bool(data.get("terminal", False)),
            memory=data.get("memory", "none"),
        )


@dataclass(frozen=True)
class ModuleManifest:
    """
    Typed representation of a validated module manifest.

    Attributes:
        module_id: Unique, stable identifier for the module.
        name: Human-readable display name.
        version: Module version string.
        author: Module author.
        capabilities: Capability names this module provides.
        services: Service names this module depends on.
        worker_type: Declared execution model (e.g. "replicable", "singleton").
        permissions: Parsed sandbox permission metadata.
        raw: The full underlying manifest dictionary, for forward
            compatibility with fields not yet promoted to typed attributes.
    """

    module_id: str
    name: str
    version: str
    author: str
    capabilities: list[str]
    services: list[str]
    worker_type: str
    permissions: ModulePermissions
    raw: dict[str, Any] = field(default_factory=dict)


class ManifestValidator:
    """
    Validates raw manifest dictionaries against the Realtimex module schema.

    Responsibilities:
        - Verify required fields are present and correctly typed.
        - Produce a typed ModuleManifest from valid raw data.

    This class performs schema validation only. It does not check
    whether declared services actually exist, or whether declared
    capabilities conflict with other modules -- those checks happen
    later in the loading pipeline, where a partial failure can be
    isolated to a single module.
    """

    _REQUIRED_STRING_FIELDS: tuple[str, ...] = ("module_id", "name", "version", "author")

    def validate(self, module_path: str, data: dict[str, Any]) -> ModuleManifest:
        """
        Validate a raw manifest dictionary and return a typed ModuleManifest.

        Args:
            module_path: Filesystem path of the module directory, used
                only for error reporting.
            data: The parsed contents of manifest.json.

        Returns:
            A validated, typed ModuleManifest.

        Raises:
            ManifestValidationError: If the manifest is missing
                required fields or has incorrectly typed values.
        """
        if not isinstance(data, dict):
            raise ManifestValidationError(module_path, "manifest.json must contain a JSON object.")

        for required_field in self._REQUIRED_STRING_FIELDS:
            value = data.get(required_field)
            if not isinstance(value, str) or not value.strip():
                raise ManifestValidationError(
                    module_path, f"missing or invalid required field {required_field!r}."
                )

        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
            raise ManifestValidationError(module_path, "'capabilities' must be a list of strings.")

        services = data.get("services", [])
        if not isinstance(services, list) or not all(isinstance(item, str) for item in services):
            raise ManifestValidationError(module_path, "'services' must be a list of strings.")

        worker_type = data.get("worker_type", "singleton")
        if not isinstance(worker_type, str) or not worker_type.strip():
            raise ManifestValidationError(module_path, "'worker_type' must be a non-empty string.")

        permissions_raw = data.get("permissions", {})
        if not isinstance(permissions_raw, dict):
            raise ManifestValidationError(module_path, "'permissions' must be an object.")

        return ModuleManifest(
            module_id=data["module_id"],
            name=data["name"],
            version=data["version"],
            author=data["author"],
            capabilities=list(capabilities),
            services=list(services),
            worker_type=worker_type,
            permissions=ModulePermissions.from_dict(permissions_raw),
            raw=data,
        )
