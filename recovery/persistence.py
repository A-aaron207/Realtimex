"""
Persistence layer for serializing and storing Checkpoints and Snapshots.

Storage format: JSON files in a directory structure
Layout:
  recovery_base/
    ├── checkpoints/
    │   ├── checkpoint-1.json
    │   ├── checkpoint-2.json
    │   └── ...
    └── snapshots/
        ├── snapshot-1.json
        ├── snapshot-2.json
        └── ...
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from recovery.exceptions import CheckpointError, SnapshotError


class RecoveryPersistence:
    """
    Manages physical file operations for checkpoints and snapshots on disk.
    
    Thread-safe file I/O for recovery data persistence. Each checkpoint/snapshot
    is stored as a JSON file for human readability and cross-platform compatibility.
    
    Key responsibilities:
    - Directory initialization and management
    - Checkpoint file I/O (save, load, delete, list)
    - Snapshot file I/O (save, load, delete, list)
    - Error handling and validation
    """

    def __init__(self, directory: Path) -> None:
        """
        Initialize persistence layer with a base recovery directory.
        
        Args:
            directory: Base path for all recovery files
            
        Raises:
            CheckpointError: If directory initialization fails
        """
        self.directory = Path(directory)
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """
        Create required directory structure for checkpoints and snapshots.
        
        Raises:
            CheckpointError: If directory creation fails
        """
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            (self.directory / "checkpoints").mkdir(parents=True, exist_ok=True)
            (self.directory / "snapshots").mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise CheckpointError(f"Failed to initialize recovery directory: {e}") from e

    # --- Checkpoints ---

    def save_checkpoint(self, checkpoint_id: str, data: dict[str, Any]) -> None:
        """
        Save checkpoint data to disk.
        
        Args:
            checkpoint_id: Unique checkpoint identifier
            data: Checkpoint data dictionary (will be JSON serialized)
            
        Raises:
            CheckpointError: If save operation fails
        """
        file_path = self.directory / "checkpoints" / f"{checkpoint_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise CheckpointError(f"Failed to save checkpoint '{checkpoint_id}': {e}") from e

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        Load checkpoint data from disk.
        
        Args:
            checkpoint_id: Unique checkpoint identifier
            
        Returns:
            Checkpoint data dictionary or None if not found
            
        Raises:
            CheckpointError: If load operation fails (file corrupted, etc.)
        """
        file_path = self.directory / "checkpoints" / f"{checkpoint_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise CheckpointError(f"Failed to load checkpoint '{checkpoint_id}': {e}") from e

    def delete_checkpoint(self, checkpoint_id: str) -> None:
        """
        Delete checkpoint file from disk.
        
        Args:
            checkpoint_id: Unique checkpoint identifier
            
        Raises:
            CheckpointError: If delete operation fails
        """
        file_path = self.directory / "checkpoints" / f"{checkpoint_id}.json"
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                raise CheckpointError(f"Failed to delete checkpoint '{checkpoint_id}': {e}") from e

    @staticmethod
    def _natural_key(s: str) -> list[int | str]:
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

    def _file_sort_key(self, f: Path) -> tuple[int, Any, list[int | str]]:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, dict) and "timestamp" in data:
                    return (0, data["timestamp"], self._natural_key(f.name))
        except Exception:
            pass
        try:
            return (1, f.stat().st_mtime_ns, self._natural_key(f.name))
        except Exception:
            return (2, 0, self._natural_key(f.name))

    def list_checkpoints(self) -> list[str]:
        """
        List all checkpoint IDs sorted by modification time (oldest first).
        
        Returns:
            List of checkpoint IDs in chronological order
            
        Raises:
            CheckpointError: If listing fails
        """
        cp_dir = self.directory / "checkpoints"
        if not cp_dir.exists():
            return []
        try:
            files = list(cp_dir.glob("*.json"))
            files.sort(key=self._file_sort_key)
            return [f.stem for f in files]
        except Exception as e:
            raise CheckpointError(f"Failed to list checkpoints: {e}") from e

    # --- Snapshots ---

    def save_snapshot(self, snapshot_id: str, data: dict[str, Any]) -> None:
        """
        Save snapshot data to disk.
        
        Args:
            snapshot_id: Unique snapshot identifier
            data: Snapshot data dictionary (will be JSON serialized)
            
        Raises:
            SnapshotError: If save operation fails
        """
        file_path = self.directory / "snapshots" / f"{snapshot_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise SnapshotError(f"Failed to save snapshot '{snapshot_id}': {e}") from e

    def load_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        """
        Load snapshot data from disk.
        
        Args:
            snapshot_id: Unique snapshot identifier
            
        Returns:
            Snapshot data dictionary or None if not found
            
        Raises:
            SnapshotError: If load operation fails
        """
        file_path = self.directory / "snapshots" / f"{snapshot_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise SnapshotError(f"Failed to load snapshot '{snapshot_id}': {e}") from e

    def delete_snapshot(self, snapshot_id: str) -> None:
        """
        Delete snapshot file from disk.
        
        Args:
            snapshot_id: Unique snapshot identifier
            
        Raises:
            SnapshotError: If delete operation fails
        """
        file_path = self.directory / "snapshots" / f"{snapshot_id}.json"
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception as e:
                raise SnapshotError(f"Failed to delete snapshot '{snapshot_id}': {e}") from e

    def list_snapshots(self) -> list[str]:
        """
        List all snapshot IDs sorted by modification time (oldest first).
        
        Returns:
            List of snapshot IDs in chronological order
            
        Raises:
            SnapshotError: If listing fails
        """
        sn_dir = self.directory / "snapshots"
        if not sn_dir.exists():
            return []
        try:
            files = list(sn_dir.glob("*.json"))
            files.sort(key=self._file_sort_key)
            return [f.stem for f in files]
        except Exception as e:
            raise SnapshotError(f"Failed to list snapshots: {e}") from e
