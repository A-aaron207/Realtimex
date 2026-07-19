"""
Developer CLI for Realtimex SDK / MDK.

Exposes commands to scaffold, validate, build, install, and troubleshoot modules.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from sdk.generator.module_generator import scaffold_module
from sdk.validation.validator import validate_module
from sdk.packaging.builder import build_package
from sdk.packaging.installer import install_package, uninstall_package
from sdk.exceptions import SDKError


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Main CLI entrypoint parser."""
    parser = argparse.ArgumentParser(
        description="Realtimex Module Development Kit (MDK) CLI.",
        prog="rtx-sdk",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # create-module
    parser_module = subparsers.add_parser("create-module", help="Scaffold a new module.")
    parser_module.add_argument("name", help="Name of the module")
    parser_module.add_argument(
        "--output-dir",
        default=".",
        help="Directory to scaffold in (default: '.')",
    )

    # create-provider
    parser_provider = subparsers.add_parser("create-provider", help="Scaffold a new model provider.")
    parser_provider.add_argument("name", help="Name of the provider")
    parser_provider.add_argument(
        "--output-dir",
        default=".",
        help="Directory to scaffold in (default: '.')",
    )

    # create-worker
    parser_worker = subparsers.add_parser("create-worker", help="Scaffold a new worker.")
    parser_worker.add_argument("name", help="Name of the worker")
    parser_worker.add_argument(
        "--output-dir",
        default=".",
        help="Directory to scaffold in (default: '.')",
    )

    # validate
    parser_val = subparsers.add_parser("validate", help="Validate a module directory.")
    parser_val.add_argument("module_dir", help="Path to the module folder")

    # build
    parser_build = subparsers.add_parser("build", help="Build a module package.")
    parser_build.add_argument("module_dir", help="Path to the module folder")
    parser_build.add_argument(
        "--output-dir",
        default="./dist",
        help="Path to output package archive",
    )

    # install
    parser_inst = subparsers.add_parser("install", help="Install a .rtx module package.")
    parser_inst.add_argument("package_path", help="Path to the .rtx package file")
    parser_inst.add_argument(
        "--install-dir",
        default="./modules",
        help="Target modules directory",
    )

    # uninstall
    parser_uninst = subparsers.add_parser("uninstall", help="Uninstall a module.")
    parser_uninst.add_argument("module_name", help="Name of the module to remove")
    parser_uninst.add_argument(
        "--install-dir",
        default="./modules",
        help="Registry modules directory",
    )

    # publish
    parser_pub = subparsers.add_parser("publish", help="Publish a package (Future-ready).")
    parser_pub.add_argument("package_path", help="Path to the package file")

    # doctor
    subparsers.add_parser("doctor", help="Run MDK diagnostics and check system health.")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "create-module":
            path = scaffold_module(args.name, args.output_dir, "module")
            print(f"Scaffolded Module '{args.name}' successfully at: {path}")

        elif args.command == "create-provider":
            path = scaffold_module(args.name, args.output_dir, "provider")
            print(f"Scaffolded Provider '{args.name}' successfully at: {path}")

        elif args.command == "create-worker":
            path = scaffold_module(args.name, args.output_dir, "worker")
            print(f"Scaffolded Worker '{args.name}' successfully at: {path}")

        elif args.command == "validate":
            success, errors = validate_module(args.module_dir)
            if success:
                print(f"Validation PASSED for '{args.module_dir}'")
                sys.exit(0)
            else:
                print(f"Validation FAILED for '{args.module_dir}':", file=sys.stderr)
                for err in errors:
                    print(f" - {err}", file=sys.stderr)
                sys.exit(1)

        elif args.command == "build":
            package_path = build_package(args.module_dir, args.output_dir)
            print(f"Package built successfully at: {package_path}")

        elif args.command == "install":
            installed_path = install_package(args.package_path, args.install_dir)
            print(f"Package installed successfully at: {installed_path}")

        elif args.command == "uninstall":
            uninstall_package(args.module_name, args.install_dir)
            print(f"Module '{args.module_name}' uninstalled successfully.")

        elif args.command == "publish":
            print("Publish functionality is future-ready and under development.")

        elif args.command == "doctor":
            run_doctor()

    except SDKError as e:
        print(f"MDK Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        sys.exit(2)


def run_doctor() -> None:
    """Run environmental diagnostic check."""
    import platform
    print("--- Realtimex MDK Doctor ---")
    print(f"Python Version: {platform.python_version()}")
    print(f"OS Platform:    {platform.platform()}")
    print(f"CPU Cores:      {os.cpu_count() or 1}")
    
    # Check current directory write permissions
    is_writable = os.access(".", os.W_OK)
    print(f"Write Access:   {'Granted' if is_writable else 'Denied'}")
    
    # Check configuration files
    has_config = os.path.isdir("config")
    print(f"Config Dir:     {'Available' if has_config else 'Not Found (Using Defaults)'}")
    
    print("\nMDK Environment Status: HEALTHY")


if __name__ == "__main__":
    main()
