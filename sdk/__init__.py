"""
Realtimex Module Development Kit (MDK).

Provides core base classes, validation schema lints, scaffolding generators,
and packaging utilities to extend the Realtimex Kernel.
"""

from __future__ import annotations

from sdk.generator.module_generator import scaffold_module as create_module
from sdk.validation.validator import validate_module as validate
from sdk.packaging.builder import build_package as build
from sdk.packaging.builder import build_package as package
from sdk.packaging.installer import install_package as install
from sdk.cli.realtimex_sdk import run_doctor as doctor
from sdk.generator.docs_generator import generate_docs

from sdk.exceptions import (
    SDKError,
    GeneratorError,
    SDKValidationError,
    PackagingError,
)

__all__ = [
    # Public APIs
    "create_module",
    "validate",
    "build",
    "install",
    "package",
    "doctor",
    "generate_docs",
    
    # Exceptions
    "SDKError",
    "GeneratorError",
    "SDKValidationError",
    "PackagingError",
]
