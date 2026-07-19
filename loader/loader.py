"""
Module Loader.

Coordinates the full module-loading pipeline: discover module
directories, validate their manifests, dynamically import their
entry points, and register their declared capabilities and services
with the Kernel's registries. A failure in any single module is
isolated -- logged, reported via a ModuleFailed event, and skipped --
so the Kernel never crashes because of a bad plugin.

The loader never executes a module's capabilities. It only discovers,
validates, imports, and registers.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from capabilities.registry import CapabilityRegistry
from events.event import Event
from events.event_bus import EventBus
from events.event_types import KernelEventType
from loader.discovery import DiscoveredModule, ManifestParseError, ModuleDiscovery
from loader.module_base import ModuleEntryPoint
from loader.validator import ManifestValidationError, ManifestValidator, ModuleManifest
from services.registry import ServiceRegistry


class ModuleImportError(Exception):
    """Raised when a module's module.py cannot be imported or lacks a valid entry point."""

    def __init__(self, module_id: str, reason: str) -> None:
        self.module_id = module_id
        self.reason = reason
        super().__init__(f"Failed to import module {module_id!r}: {reason}")


@dataclass
class LoadedModule:
    """
    A fully loaded, registered module.

    Attributes:
        manifest: The validated manifest for this module.
        instance: The instantiated entry point object from module.py.
        module_path: Filesystem path to the module's directory.
    """

    manifest: ModuleManifest
    instance: ModuleEntryPoint
    module_path: Path


@dataclass
class ModuleLoadFailure:
    """
    A record of a module that failed to load, for diagnostics.

    Attributes:
        module_path: Filesystem path of the module directory that failed.
        stage: The pipeline stage at which the failure occurred
            ("discovery", "validation", or "import").
        reason: A human-readable description of the failure.
    """

    module_path: str
    stage: str
    reason: str


class ModuleLoader:
    """
    Orchestrates discovery, validation, dynamic import, and
    registration of modules found under a modules directory.

    Responsibilities:
        - Discover candidate module directories.
        - Validate each manifest against the Realtimex schema.
        - Dynamically import each module's `module.py` entry point.
        - Register declared capabilities with the CapabilityRegistry.
        - Track declared service dependencies (service resolution
          itself is not performed here -- that belongs to whichever
          future component actually invokes the module).
        - Emit lifecycle events for every step, and continue past
          individual module failures without raising.

    This class holds no global state; all registries and the event
    bus are supplied via dependency injection at construction time.
    """

    def __init__(
        self,
        modules_root: Path,
        capability_registry: CapabilityRegistry,
        service_registry: ServiceRegistry,
        event_bus: EventBus,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize the Module Loader.

        Args:
            modules_root: Directory under which module subdirectories live.
            capability_registry: Registry to record each module's
                declared capabilities against.
            service_registry: Registry used to check which declared
                service dependencies are actually available.
            event_bus: Event Bus used to announce discovery, validation,
                load, and failure events.
            logger: Logger for structured diagnostic output.
        """
        self._discovery = ModuleDiscovery(modules_root=modules_root)
        self._validator = ManifestValidator()
        self._capability_registry = capability_registry
        self._service_registry = service_registry
        self._event_bus = event_bus
        self._logger = logger
        self._lock = threading.RLock()

        self._loaded_modules: dict[str, LoadedModule] = {}
        self._failures: list[ModuleLoadFailure] = []

    @property
    def modules_root(self) -> Path:
        """The directory this loader scans for modules."""
        return self._discovery.modules_root

    def discover(self) -> list[DiscoveredModule]:
        """
        Scan the modules directory for candidate modules.

        Emits a ModuleDiscovered event for each module directory found
        that contains a manifest.json. Directories whose manifest.json
        cannot even be parsed as JSON are recorded as failures rather
        than raised, so discovery never aborts the whole scan.

        Returns:
            The list of successfully discovered (but not yet validated) modules.
        """
        discovered_modules = self._discovery.discover()

        for parse_failure in self._discovery.parse_failures():
            self._fail_module(str(parse_failure.manifest_path.parent), "discovery", str(parse_failure))

        for discovered in discovered_modules:
            self._logger.info("Discovered module at %s", discovered.module_path)
            self._event_bus.emit(
                Event(
                    name=KernelEventType.MODULE_DISCOVERED,
                    source="loader.discovery",
                    payload={"module_path": str(discovered.module_path)},
                )
            )

        return discovered_modules

    def validate(self, discovered_modules: list[DiscoveredModule]) -> list[tuple[DiscoveredModule, ModuleManifest]]:
        """
        Validate the manifests of previously discovered modules.

        Emits a ModuleValidated event for each manifest that passes
        validation, and a ModuleFailed event (plus a logged error) for
        each one that does not. Invalid modules are excluded from the
        returned list but do not halt validation of the rest.

        Args:
            discovered_modules: Modules previously returned by `discover()`.

        Returns:
            A list of (DiscoveredModule, ModuleManifest) pairs for
            every module that passed validation.
        """
        validated: list[tuple[DiscoveredModule, ModuleManifest]] = []

        for discovered in discovered_modules:
            try:
                manifest = self._validator.validate(str(discovered.module_path), discovered.raw_manifest)
            except ManifestValidationError as error:
                self._fail_module(str(discovered.module_path), "validation", str(error))
                continue

            self._logger.info("Validated manifest for module %r", manifest.module_id)
            self._event_bus.emit(
                Event(
                    name=KernelEventType.MODULE_VALIDATED,
                    source="loader.validator",
                    payload={"module_id": manifest.module_id, "version": manifest.version},
                )
            )
            validated.append((discovered, manifest))

        return validated

    def load(self) -> list[LoadedModule]:
        """
        Run the full discover -> validate -> import -> register pipeline.

        This is the primary entry point for booting the module system.
        Any module that fails at any stage is skipped, logged, and
        reported via a ModuleFailed event; the pipeline always
        completes and returns whatever modules succeeded.

        Returns:
            The list of successfully loaded and registered modules.
        """
        discovered_modules = self.discover()
        validated_modules = self.validate(discovered_modules)

        for discovered, manifest in validated_modules:
            self._load_single_module(discovered, manifest)

        return self.list_modules()

    def _load_single_module(self, discovered: DiscoveredModule, manifest: ModuleManifest) -> None:
        """
        Import, instantiate, and register a single validated module.

        Args:
            discovered: The discovery record for this module.
            manifest: The validated manifest for this module.
        """
        try:
            instance = self._import_entry_point(discovered, manifest)
        except ModuleImportError as error:
            self._fail_module(manifest.module_id, "import", str(error))
            return

        with self._lock:
            self._loaded_modules[manifest.module_id] = LoadedModule(
                manifest=manifest,
                instance=instance,
                module_path=discovered.module_path,
            )

        self._register_capabilities(manifest)
        self._check_service_dependencies(manifest)

        self._logger.info("Loaded module %r (%s)", manifest.module_id, manifest.name)
        self._event_bus.emit(
            Event(
                name=KernelEventType.MODULE_LOADED,
                source="loader.loader",
                payload={
                    "module_id": manifest.module_id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "capabilities": manifest.capabilities,
                },
            )
        )

    def _import_entry_point(self, discovered: DiscoveredModule, manifest: ModuleManifest) -> ModuleEntryPoint:
        """
        Dynamically import a module's module.py and instantiate its Module class.

        Args:
            discovered: The discovery record for this module.
            manifest: The validated manifest for this module.

        Returns:
            An instantiated entry point object.

        Raises:
            ModuleImportError: If module.py is missing, fails to
                import, has no `Module` class, or the class cannot be
                instantiated.
        """
        if not discovered.entry_point_path.is_file():
            raise ModuleImportError(manifest.module_id, f"missing module.py at {discovered.entry_point_path}")

        qualified_name = f"realtimex_modules.{manifest.module_id}"
        spec = importlib.util.spec_from_file_location(qualified_name, discovered.entry_point_path)
        if spec is None or spec.loader is None:
            raise ModuleImportError(manifest.module_id, "could not build an import spec for module.py")

        python_module: ModuleType = importlib.util.module_from_spec(spec)

        try:
            sys.modules[qualified_name] = python_module
            spec.loader.exec_module(python_module)
        except Exception as error:
            sys.modules.pop(qualified_name, None)
            raise ModuleImportError(manifest.module_id, f"error executing module.py: {error}") from error

        entry_class = getattr(python_module, "Module", None)
        if entry_class is None:
            raise ModuleImportError(manifest.module_id, "module.py has no top-level 'Module' class")

        try:
            instance = entry_class()
        except Exception as error:
            raise ModuleImportError(manifest.module_id, f"failed to instantiate Module(): {error}") from error

        if getattr(instance, "module_id", None) != manifest.module_id:
            raise ModuleImportError(
                manifest.module_id,
                "Module.module_id does not match manifest module_id",
            )

        return instance

    def _register_capabilities(self, manifest: ModuleManifest) -> None:
        """
        Register every capability declared in a manifest with the CapabilityRegistry.

        Args:
            manifest: The validated manifest declaring the capabilities.
        """
        for capability_name in manifest.capabilities:
            self._capability_registry.register(
                capability=capability_name,
                provider_id=manifest.module_id,
                metadata={"module_name": manifest.name, "version": manifest.version},
            )
            self._logger.info("Registered capability %r from module %r", capability_name, manifest.module_id)
            self._event_bus.emit(
                Event(
                    name=KernelEventType.CAPABILITY_REGISTERED,
                    source="loader.loader",
                    payload={"capability": capability_name, "provider_id": manifest.module_id},
                )
            )

    def _check_service_dependencies(self, manifest: ModuleManifest) -> None:
        """
        Log a warning for any service a module depends on that is not
        currently registered.

        Milestone 2 does not fail module loading over missing
        services -- service resolution and injection belong to a
        future milestone -- but it surfaces the gap for visibility.

        Args:
            manifest: The validated manifest declaring service dependencies.
        """
        for service_name in manifest.services:
            if not self._service_registry.exists(service_name):
                self._logger.warning(
                    "Module %r declares dependency on unregistered service %r",
                    manifest.module_id,
                    service_name,
                )

    def _fail_module(self, identifier: str, stage: str, reason: str) -> None:
        """
        Record a module failure: log it, store it, and emit ModuleFailed.

        Args:
            identifier: The module_id (or path, if module_id is unknown) that failed.
            stage: The pipeline stage at which the failure occurred.
            reason: A human-readable description of the failure.
        """
        self._record_failure(identifier, stage, reason)
        self._logger.error("Module %r failed during %s: %s", identifier, stage, reason)
        self._event_bus.emit(
            Event(
                name=KernelEventType.MODULE_FAILED,
                source="loader.loader",
                payload={"module": identifier, "stage": stage, "reason": reason},
            )
        )

    def _record_failure(self, identifier: str, stage: str, reason: str) -> None:
        """Append a failure record without emitting an event (used pre-logger-availability)."""
        with self._lock:
            self._failures.append(ModuleLoadFailure(module_path=identifier, stage=stage, reason=reason))

    def reload(self, module_id: str) -> LoadedModule | None:
        """
        Reload a single module by module_id.

        If the module is currently loaded, it is unloaded first
        (removing its capabilities from the registry). The modules
        directory is then re-scanned and the module is re-validated,
        re-imported, and re-registered from scratch. This works even
        if the module was not previously loaded, as long as its
        directory and manifest exist on disk.

        Args:
            module_id: The module_id of the module to reload.

        Returns:
            The newly loaded module, or None if no module with that
            module_id could be discovered and loaded successfully.
        """
        with self._lock:
            already_loaded = module_id in self._loaded_modules

        if already_loaded:
            self.unload(module_id)

        for discovered in self.discover():
            for candidate_discovered, manifest in self.validate([discovered]):
                if manifest.module_id != module_id:
                    continue
                self._load_single_module(candidate_discovered, manifest)
                with self._lock:
                    return self._loaded_modules.get(manifest.module_id)

        self._logger.warning("Cannot reload module %r: not found during discovery", module_id)
        return None

    def unload(self, module_id: str) -> None:
        """
        Unload a previously loaded module, removing its capabilities
        from the CapabilityRegistry.

        Args:
            module_id: The module_id of the module to unload. Silently
                does nothing if the module is not currently loaded.
        """
        with self._lock:
            loaded = self._loaded_modules.pop(module_id, None)

        if loaded is None:
            return

        self._capability_registry.unregister_provider(module_id)
        qualified_name = f"realtimex_modules.{module_id}"
        sys.modules.pop(qualified_name, None)

        self._logger.info("Unloaded module %r", module_id)
        self._event_bus.emit(
            Event(
                name=KernelEventType.MODULE_UNLOADED,
                source="loader.loader",
                payload={"module_id": module_id},
            )
        )

    def list_modules(self) -> list[LoadedModule]:
        """Return every currently loaded module."""
        with self._lock:
            return list(self._loaded_modules.values())

    def failures(self) -> list[ModuleLoadFailure]:
        """Return every module failure recorded since this loader was created."""
        with self._lock:
            return list(self._failures)
