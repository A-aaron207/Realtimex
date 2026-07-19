"""
Policy Loader for Realtimex.

Parses policies from JSON, YAML, or TOML files and directories.
"""

from __future__ import annotations

import json
import os
from typing import Any


class PolicyLoader:
    """Reads policy configuration files from the filesystem."""

    def load_json(self, path: str) -> dict[str, Any]:
        """Load policy from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_yaml(self, path: str) -> dict[str, Any]:
        """Load policy from YAML file, with fallback parser if PyYAML is not installed."""
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            # Basic fallback for reading simple key-value YAML files
            res = {}
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.split("#")[0].strip()
                    if not line or ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if v.startswith("[") and v.endswith("]"):
                        # Parse simple list
                        v = [item.strip().strip('"').strip("'") for item in v[1:-1].split(",") if item.strip()]
                    elif v in ("true", "True"):
                        v = True
                    elif v in ("false", "False"):
                        v = False
                    elif v.isdigit():
                        v = int(v)
                    else:
                        v = v.strip('"').strip("'")
                    res[k] = v
            return res

    def load_toml(self, path: str) -> dict[str, Any]:
        """Load policy from TOML file, with standard library support."""
        try:
            # Python 3.11+ standard library
            import tomllib
            with open(path, "rb") as f:
                return tomllib.load(f)
        except ImportError:
            try:
                import tomli
                with open(path, "rb") as f:
                    return tomli.load(f)
            except ImportError:
                # Basic fallback
                return {}

    def load_directory(self, directory: str) -> list[dict[str, Any]]:
        """Scan a directory and load all JSON, YAML, and TOML policy files."""
        policies = []
        if not os.path.isdir(directory):
            return policies

        import glob
        for filepath in glob.glob(os.path.join(directory, "*.*")):
            filename = os.path.basename(filepath)
            if filename.startswith(".") or os.path.isdir(filepath):
                continue
                
            try:
                if filepath.endswith(".json"):
                    policies.append(self.load_json(filepath))
                elif filepath.endswith((".yaml", ".yml")):
                    policies.append(self.load_yaml(filepath))
                elif filepath.endswith(".toml"):
                    policies.append(self.load_toml(filepath))
            except Exception:
                continue

        return policies
