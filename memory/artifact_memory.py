"""
Artifact Memory component for Memory 2.0.

Tracks generated artifacts (code, HTML, images, reports, markdown, JSON) with metadata,
checksums, task origin, and search indexing.
"""

from __future__ import annotations

import hashlib

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ArtifactType = Literal["code", "html", "image", "report", "markdown", "json", "media", "data"]


@dataclass
class ArtifactRecord:
    """
    Representation of a generated artifact in Memory 2.0.
    """
    artifact_id: str
    artifact_type: ArtifactType
    file_path: str
    name: str
    checksum: str = ""
    task_id: str | None = None
    step_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "file_path": self.file_path,
            "name": self.name,
            "checksum": self.checksum,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactRecord:
        created_at = datetime.now(timezone.utc)
        if "created_at" in data:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except ValueError:
                pass

        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data.get("artifact_type", "data"),
            file_path=data["file_path"],
            name=data.get("name", Path(data["file_path"]).name),
            checksum=data.get("checksum", ""),
            task_id=data.get("task_id"),
            step_id=data.get("step_id"),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


class ArtifactMemoryStore:
    """
    Store for managing and retrieving generated artifact records.
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, ArtifactRecord] = {}

    def register_artifact(
        self,
        artifact_id: str,
        artifact_type: ArtifactType,
        file_path: str,
        name: str | None = None,
        task_id: str | None = None,
        step_id: str | None = None,
        content: str | bytes | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Register a new generated artifact."""
        abs_p = str(Path(file_path).resolve())
        checksum = ""

        if content is not None:
            if isinstance(content, str):
                checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
            else:
                checksum = hashlib.sha256(content).hexdigest()
        elif Path(abs_p).exists():
            try:
                data = Path(abs_p).read_bytes()
                checksum = hashlib.sha256(data).hexdigest()
            except Exception:
                pass

        rec = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            file_path=abs_p,
            name=name or Path(abs_p).name,
            checksum=checksum,
            task_id=task_id,
            step_id=step_id,
            metadata=metadata or {},
        )
        self._artifacts[artifact_id] = rec
        return rec

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        return self._artifacts.get(artifact_id)

    def list_artifacts(self, artifact_type: ArtifactType | None = None, task_id: str | None = None) -> list[ArtifactRecord]:
        """Query stored artifacts filtered by type or task_id."""
        results = list(self._artifacts.values())
        if artifact_type:
            results = [r for r in results if r.artifact_type == artifact_type]
        if task_id:
            results = [r for r in results if r.task_id == task_id]
        return results
