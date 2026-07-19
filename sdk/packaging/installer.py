"""
Package Installer for Realtimex MDK.

Extracts .rtx package archives into a specified installation directory.
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
from typing import Any, Optional

from sdk.exceptions import PackagingError


def install_package(
    package_path: str,
    install_dir: str,
    event_bus: Any = None,
) -> str:
    """
    Install a .rtx package by extracting it into the target install path.
    
    Args:
        package_path: Path to the .rtx package archive
        install_dir: Registry/installation directory for Realtimex extensions
        event_bus: Optional Event Bus for event-driven updates
        
    Returns:
        Absolute path to the installed module folder
        
    Raises:
        PackagingError: If target package is missing or extraction fails
    """
    if not os.path.isfile(package_path):
        raise PackagingError(f"Package file not found: {package_path}")

    # Build intermediate temp extraction dir
    temp_extract = os.path.join(install_dir, f".temp_install_{os.path.basename(package_path)}")
    if os.path.exists(temp_extract):
        try:
            shutil.rmtree(temp_extract)
        except Exception:
            pass

    try:
        os.makedirs(temp_extract, exist_ok=True)
        
        # Extract files
        with tarfile.open(package_path, "r:gz") as tar:
            tar.extractall(path=temp_extract)

        # Inspect manifest
        manifest_path = os.path.join(temp_extract, "manifest.json")
        if not os.path.exists(manifest_path):
            raise PackagingError("Invalid package: missing manifest.json")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        module_name = manifest["name"]
        version = manifest.get("version", "1.0.0")

        # Move to permanent home
        target_path = os.path.join(install_dir, module_name)
        if os.path.exists(target_path):
            shutil.rmtree(target_path)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.move(temp_extract, target_path)

        # Emit PackageInstalled event
        if event_bus:
            try:
                from events.event import Event, EventPriority
                event_bus.publish(
                    Event(
                        name="PackageInstalled",
                        source="sdk.packaging.installer",
                        payload={
                            "name": module_name,
                            "version": version,
                            "path": os.path.abspath(target_path),
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass

        return os.path.abspath(target_path)

    except Exception as e:
        if os.path.exists(temp_extract):
            try:
                shutil.rmtree(temp_extract)
            except Exception:
                pass
        raise PackagingError(f"Failed to install package: {e}") from e


def uninstall_package(
    module_name: str,
    install_dir: str,
    event_bus: Any = None,
) -> None:
    """
    Remove an installed Realtimex extension.
    
    Args:
        module_name: Extension name
        install_dir: Directory where extensions are installed
        event_bus: Optional Event Bus for event-driven updates
        
    Raises:
        PackagingError: If target module is not found or deletion fails
    """
    target_path = os.path.join(install_dir, module_name)
    if not os.path.exists(target_path):
        raise PackagingError(f"Module '{module_name}' is not installed at: {target_path}")

    try:
        shutil.rmtree(target_path)

        # Emit PackageRemoved event
        if event_bus:
            try:
                from events.event import Event, EventPriority
                event_bus.publish(
                    Event(
                        name="PackageRemoved",
                        source="sdk.packaging.installer",
                        payload={"name": module_name},
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass

    except Exception as e:
        raise PackagingError(f"Failed to uninstall module '{module_name}': {e}") from e
