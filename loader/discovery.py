"""
Module discovery.

Scans the `modules/` directory tree for candidate plugin modules --
any subdirectory containing a `manifest.json` file -- without
importing or validating them. Discovery is deliberately a separate,
side-effect-free step from validation and loading, so each phase can
be tested, logged, and reasoned about independently.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DiscoveredModule:
    """
    A module directory found on disk, with its manifest parsed as raw JSON.

    Attributes:
        module_path: Filesystem path to the module's directory.
        manifest_path: Filesystem path to the module's manifest.json.
        entry_point_path: Filesystem path to the module's module.py.
        raw_manifest: The manifest file's contents, parsed as a plain
            dictionary. Not yet schema-validated.
    """

    module_path: Path
    manifest_path: Path
    entry_point_path: Path
    raw_manifest: dict[str, Any]


class ManifestParseError(Exception):
    """Raised when a manifest.json file cannot be read or parsed as JSON."""

    def __init__(self, manifest_path: Path, reason: str) -> None:
        self.manifest_path = manifest_path
        self.reason = reason
        super().__init__(f"Could not parse manifest at {manifest_path}: {reason}")


class ModuleDiscovery:
    """
    Scans a modules directory for candidate plugin modules.

    Responsibilities:
        - Enumerate immediate subdirectories of the modules root.
        - Identify which ones contain a manifest.json.
        - Parse each manifest.json as JSON (schema validation happens
          later, in ManifestValidator).

    A directory without a manifest.json is silently skipped -- it is
    not considered a module and is not reported as an error.
    """

    _MANIFEST_FILENAME = "manifest.json"
    _ENTRY_POINT_FILENAME = "module.py"

    def __init__(self, modules_root: Path) -> None:
        """
        Initialize the discovery scanner.

        Args:
            modules_root: The directory under which module
                subdirectories live (typically the `modules/` folder).
        """
        self._modules_root = modules_root
        self._parse_failures: list[ManifestParseError] = []

    @property
    def modules_root(self) -> Path:
        """The directory this scanner searches for modules."""
        return self._modules_root

    def discover(self) -> list[DiscoveredModule]:
        """
        Scan the modules root and return every directory containing a
        manifest.json that parses successfully as JSON.

        Returns:
            A list of DiscoveredModule entries, one per subdirectory
            that contains a manifest.json. Returns an empty list if the
            modules root does not exist. Directories whose
            manifest.json fails to parse are skipped and reported
            through `parse_failures()` rather than raised, so a single
            malformed module cannot abort discovery of the rest.
        """
        if not self._modules_root.exists():
            return []

        discovered: list[DiscoveredModule] = []
        self._parse_failures = []

        for candidate in sorted(self._modules_root.iterdir()):
            if not candidate.is_dir():
                continue

            manifest_path = candidate / self._MANIFEST_FILENAME
            if not manifest_path.is_file():
                continue

            try:
                raw_manifest = self._parse_manifest(manifest_path)
            except ManifestParseError as error:
                self._parse_failures.append(error)
                continue

            entry_point_path = candidate / self._ENTRY_POINT_FILENAME

            discovered.append(
                DiscoveredModule(
                    module_path=candidate,
                    manifest_path=manifest_path,
                    entry_point_path=entry_point_path,
                    raw_manifest=raw_manifest,
                )
            )

        return discovered

    def parse_failures(self) -> list[ManifestParseError]:
        """Return manifest parse failures recorded during the most recent `discover()` call."""
        return list(self._parse_failures)

    @staticmethod
    def _parse_manifest(manifest_path: Path) -> dict[str, Any]:
        """
        Read and parse a manifest.json file.

        Args:
            manifest_path: Path to the manifest.json file.

        Returns:
            The parsed manifest as a dictionary.

        Raises:
            ManifestParseError: If the file cannot be read or is not valid JSON.
        """
        try:
            with manifest_path.open("r", encoding="utf-8") as manifest_file:
                return json.load(manifest_file)
        except (OSError, json.JSONDecodeError) as error:
            raise ManifestParseError(manifest_path, str(error)) from error
