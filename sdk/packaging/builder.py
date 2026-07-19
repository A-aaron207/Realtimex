"""
Package Builder for Realtimex MDK.

Bundles validated extension directories into a versioned tar.gz package with the .rtx extension.
"""

from __future__ import annotations

import json
import os
import tarfile
from typing import Any, Optional

from sdk.validation.validator import validate_module
from sdk.exceptions import PackagingError


def build_package(
    module_dir: str,
    output_dir: str,
    event_bus: Any = None,
) -> str:
    """
    Validate and build a versioned package archive for a module.
    
    Args:
        module_dir: Source module directory
        output_dir: Output directory to place the built package
        event_bus: Optional Event Bus for event-driven updates
        
    Returns:
        Absolute path to the built .rtx package file
        
    Raises:
        PackagingError: If validation fails or archive creation encounters errors
    """
    # 1. Validate module first
    success, errors = validate_module(module_dir)
    blocking_errors = [
        err for err in errors 
        if not err.startswith("Folder structure check warning:") 
        and not err.startswith("Source check warning:")
    ]
    if not success or blocking_errors:
        raise PackagingError(f"Validation failed prior to building: {blocking_errors}")

    # 2. Extract manifest info
    manifest_path = os.path.join(module_dir, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        raise PackagingError(f"Failed to read manifest for build: {e}") from e

    name = manifest["name"]
    version = manifest["version"]

    # 3. Build tar.gz package
    os.makedirs(output_dir, exist_ok=True)
    package_filename = f"{name}-{version}.rtx"
    package_path = os.path.join(output_dir, package_filename)

    try:
        with tarfile.open(package_path, "w:gz") as tar:
            for root, _, files in os.walk(module_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Relative path inside the tarball
                    arcname = os.path.relpath(file_path, module_dir)
                    tar.add(file_path, arcname=arcname)

        # Emit PackageBuilt event
        if event_bus:
            try:
                from events.event import Event, EventPriority
                event_bus.publish(
                    Event(
                        name="PackageBuilt",
                        source="sdk.packaging.builder",
                        payload={
                            "name": name,
                            "version": version,
                            "path": os.path.abspath(package_path),
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass

        return os.path.abspath(package_path)

    except Exception as e:
        if os.path.exists(package_path):
            try:
                os.remove(package_path)
            except Exception:
                pass
        raise PackagingError(f"Failed to build package archive: {e}") from e
