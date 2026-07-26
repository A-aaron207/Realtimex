"""
Task Trajectory Memory component for Memory 2.0.

Records full execution histories of tasks (actions, outputs, files created/modified,
errors, final states) and enables task auditing and 'undo last task' capabilities.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TaskTrajectoryRecord:
    """
    Complete record of a task's execution trajectory.
    """
    task_id: str
    objective: str
    actions_executed: list[dict[str, Any]] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    modified_files: list[dict[str, Any]] = field(default_factory=list)  # {"path": ..., "previous_content": ...}
    outputs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    final_state: str = "COMPLETED"  # COMPLETED | FAILED
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def record_action(self, step_id: str, capability: str, input_data: dict[str, Any], output: dict[str, Any]) -> None:
        self.actions_executed.append({
            "step_id": step_id,
            "capability": capability,
            "input": input_data,
            "output": output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_file_creation(self, file_path: str) -> None:
        abs_p = str(Path(file_path).resolve())
        if abs_p not in self.created_files:
            self.created_files.append(abs_p)

    def record_file_modification(self, file_path: str, previous_content: str | None = None) -> None:
        abs_p = str(Path(file_path).resolve())
        self.modified_files.append({
            "path": abs_p,
            "previous_content": previous_content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "actions_executed": self.actions_executed,
            "created_files": self.created_files,
            "modified_files": self.modified_files,
            "outputs": self.outputs,
            "errors": self.errors,
            "final_state": self.final_state,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskTrajectoryRecord:
        start_time = datetime.now(timezone.utc)
        if "start_time" in data:
            try:
                start_time = datetime.fromisoformat(data["start_time"])
            except ValueError:
                pass

        end_time = None
        if data.get("end_time"):
            try:
                end_time = datetime.fromisoformat(data["end_time"])
            except ValueError:
                pass

        return cls(
            task_id=data["task_id"],
            objective=data.get("objective", ""),
            actions_executed=data.get("actions_executed", []),
            created_files=data.get("created_files", []),
            modified_files=data.get("modified_files", []),
            outputs=data.get("outputs", []),
            errors=data.get("errors", []),
            final_state=data.get("final_state", "COMPLETED"),
            start_time=start_time,
            end_time=end_time,
            metadata=data.get("metadata", {}),
        )


class TaskTrajectoryStore:
    """
    Store for managing task execution histories and enabling undo operations.
    """

    def __init__(self) -> None:
        self._trajectories: dict[str, TaskTrajectoryRecord] = {}
        self._task_history_order: list[str] = []

    def start_task(self, task_id: str, objective: str) -> TaskTrajectoryRecord:
        rec = TaskTrajectoryRecord(task_id=task_id, objective=objective)
        self._trajectories[task_id] = rec
        self._task_history_order.append(task_id)
        return rec

    def get_trajectory(self, task_id: str) -> TaskTrajectoryRecord | None:
        return self._trajectories.get(task_id)

    def finish_task(self, task_id: str, final_state: str = "COMPLETED") -> TaskTrajectoryRecord | None:
        rec = self._trajectories.get(task_id)
        if rec:
            rec.final_state = final_state
            rec.end_time = datetime.now(timezone.utc)
        return rec

    def get_last_task(self) -> TaskTrajectoryRecord | None:
        if self._task_history_order:
            last_id = self._task_history_order[-1]
            return self._trajectories.get(last_id)
        return None

    def undo_task(self, task_id: str) -> dict[str, Any]:
        """
        Revert actions performed in the specified task (delete created files,
        restore modified files to previous_content).
        """
        rec = self._trajectories.get(task_id)
        if not rec:
            return {"status": "FAILED", "reason": f"Task trajectory '{task_id}' not found."}

        deleted_files: list[str] = []
        reverted_files: list[str] = []
        failed_files: list[str] = []

        # 1. Delete created files
        for file_path in reversed(rec.created_files):
            p = Path(file_path)
            if p.exists():
                try:
                    p.unlink()
                    deleted_files.append(file_path)
                except Exception:
                    failed_files.append(file_path)

        # 2. Restore modified files
        for mod in reversed(rec.modified_files):
            file_path = mod["path"]
            prev_content = mod.get("previous_content")
            if prev_content is not None:
                p = Path(file_path)
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(prev_content)
                    reverted_files.append(file_path)
                except Exception:
                    failed_files.append(file_path)

        return {
            "status": "SUCCESS",
            "task_id": task_id,
            "deleted_files": deleted_files,
            "reverted_files": reverted_files,
            "failed_files": failed_files,
        }
