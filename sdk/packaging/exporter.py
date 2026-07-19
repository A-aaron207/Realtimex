"""
Package Exporter for Realtimex MDK.

Handles copying package files to an export location.
"""

from __future__ import annotations

import os
import shutil

from sdk.exceptions import PackagingError


def export_package(package_path: str, export_path: str) -> None:
    """
    Export a built package to another destination path.
    
    Args:
        package_path: Path to the built package
        export_path: Destination path
        
    Raises:
        PackagingError: If export operations fail
    """
    if not os.path.isfile(package_path):
        raise PackagingError(f"Package file not found: {package_path}")

    try:
        os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
        shutil.copy2(package_path, export_path)
    except Exception as e:
        raise PackagingError(f"Failed to export package to {export_path}: {e}") from e
