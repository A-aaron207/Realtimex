"""
Workspace Memory component for Memory 2.0.

Maintains real-time knowledge of the active project workspace, directory state,
recently modified files, active Git branch/status, python environment, terminal,
and browser state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class WorkspaceContext:
    """
    State container for active workspace memory.
    """
    project_root: str
    project_name: str
    current_dir: str
    recent_files: list[dict[str, Any]] = field(default_factory=list)
    git_branch: str | None = None
    git_status: str | None = None
    python_venv: str | None = None
    active_terminal_sessions: list[str] = field(default_factory=list)
    active_browser_url: str | None = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch_file(self, file_path: str, action: str = "modified") -> None:
        """Record file interaction in recent_files (de-duplicating recent entries)."""
        abs_path = str(Path(file_path).resolve())
        # Filter existing entry for same file
        self.recent_files = [f for f in self.recent_files if f.get("path") != abs_path]
        self.recent_files.insert(0, {
            "path": abs_path,
            "filename": Path(abs_path).name,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep top 50 recent files
        self.recent_files = self.recent_files[:50]
        self.last_updated = datetime.now(timezone.utc)

    def get_continuation_summary(self) -> str:
        """
        Generate a concise narrative summary of active context so 'continue'
        requests resolve state immediately without prompt ambiguity.
        """
        summary_parts = [
            f"Project: {self.project_name} ({self.project_root})",
            f"Current Working Directory: {self.current_dir}",
        ]
        if self.git_branch:
            summary_parts.append(f"Git Branch: {self.git_branch}")
        if self.python_venv:
            summary_parts.append(f"Python Environment: {self.python_venv}")
        if self.recent_files:
            latest = self.recent_files[0]
            summary_parts.append(f"Last Modified File: {latest['path']} ({latest['action']})")
        if self.active_browser_url:
            summary_parts.append(f"Active Browser URL: {self.active_browser_url}")

        return " | ".join(summary_parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "project_name": self.project_name,
            "current_dir": self.current_dir,
            "recent_files": self.recent_files,
            "git_branch": self.git_branch,
            "git_status": self.git_status,
            "python_venv": self.python_venv,
            "active_terminal_sessions": self.active_terminal_sessions,
            "active_browser_url": self.active_browser_url,
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceContext:
        last_updated = datetime.now(timezone.utc)
        if "last_updated" in data:
            try:
                last_updated = datetime.fromisoformat(data["last_updated"])
            except ValueError:
                pass

        return cls(
            project_root=data.get("project_root", str(Path.cwd())),
            project_name=data.get("project_name", Path.cwd().name),
            current_dir=data.get("current_dir", str(Path.cwd())),
            recent_files=data.get("recent_files", []),
            git_branch=data.get("git_branch"),
            git_status=data.get("git_status"),
            python_venv=data.get("python_venv"),
            active_terminal_sessions=data.get("active_terminal_sessions", []),
            active_browser_url=data.get("active_browser_url"),
            last_updated=last_updated,
            metadata=data.get("metadata", {}),
        )


class WorkspaceMemoryStore:
    """
    Manager store for workspace state persistence and lookups.
    """

    def __init__(self, default_root: str | Path | None = None) -> None:
        root_path = Path(default_root).resolve() if default_root else Path.cwd()
        self._context = WorkspaceContext(
            project_root=str(root_path),
            project_name=root_path.name,
            current_dir=str(root_path),
        )

    def get_context(self) -> WorkspaceContext:
        return self._context

    def update_context(self, **kwargs: Any) -> WorkspaceContext:
        """Update workspace context attributes dynamically."""
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
        self._context.last_updated = datetime.now(timezone.utc)
        return self._context

    def record_file_activity(self, file_path: str, action: str = "modified") -> None:
        self._context.touch_file(file_path, action)
