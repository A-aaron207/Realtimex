"""
Permission manifest registry for the Realtimex Permission System.
"""

from __future__ import annotations

import fnmatch
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SecurityManifest:
    """
    Declared manifest for a worker, module, or service defining its intended action scope.
    """
    entity_id: str
    allowed_actions: list[str] = field(default_factory=list)
    allowed_targets: list[str] = field(default_factory=list)  # Glob/exact patterns
    metadata: dict[str, Any] = field(default_factory=dict)


class PermissionRegistry:
    """
    Thread-safe registry mapping modules/workers/services to their declared SecurityManifests.
    Used to verify pre-declarations in sandboxed environments.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Map: entity_id -> SecurityManifest
        self._manifests: dict[str, SecurityManifest] = {}

    def register_manifest(self, manifest: SecurityManifest) -> None:
        """Register a declared security manifest for a worker/module."""
        with self._lock:
            self._manifests[manifest.entity_id] = manifest

    def unregister_manifest(self, entity_id: str) -> None:
        """Remove a security manifest."""
        with self._lock:
            if entity_id in self._manifests:
                del self._manifests[entity_id]

    def get_manifest(self, entity_id: str) -> SecurityManifest | None:
        """Retrieve manifest for an entity."""
        with self._lock:
            return self._manifests.get(entity_id)

    def is_declared(self, entity_id: str, action: str, target: str) -> bool:
        """
        Check if the action and target are pre-declared in the entity's manifest.
        Uses glob matching for targets.
        """
        manifest = self.get_manifest(entity_id)
        if manifest is None:
            return False

        # 1. Check Action
        if action not in manifest.allowed_actions:
            return False

        # 2. Check Target (support glob patterns, e.g. '/workspace/*' matches '/workspace/code.py')
        if not manifest.allowed_targets:
            return True  # If empty, target constraints are unrestricted under allowed action

        for pattern in manifest.allowed_targets:
            if fnmatch.fnmatch(target, pattern):
                return True

        return False

    def clear(self) -> None:
        """Clear all registered manifests."""
        with self._lock:
            self._manifests.clear()
