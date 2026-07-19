"""
Base Platform Adapter class defining the cross-platform abstraction contract.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from typing import Any, Callable


class BasePlatform(ABC):
    """
    Abstract Base Class for platform-specific adapters.
    """

    # --- Filesystem ---

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read text content from a file path."""
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        """Write text content to a file path."""
        pass

    @abstractmethod
    def watch_directory(self, path: str, callback: Callable[[str], None]) -> Any:
        """Watch a directory for file change events."""
        pass

    @abstractmethod
    def resolve_paths(self, *parts: str) -> str:
        """Resolve path parts into a clean platform-specific absolute path."""
        pass

    # --- Process Management ---

    @abstractmethod
    def spawn_process(self, command: list[str] | str, env: dict[str, str] | None = None) -> subprocess.Popen:
        """Spawn a background process."""
        pass

    @abstractmethod
    def kill_process(self, pid: int) -> bool:
        """Terminate a process by PID."""
        pass

    @abstractmethod
    def wait_process(self, process: subprocess.Popen, timeout: float | None = None) -> int | None:
        """Wait for a process to terminate and return its exit code."""
        pass

    # --- Terminal ---

    @abstractmethod
    def run_command(self, command: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
        """Run a command synchronously and return (exit_code, stdout, stderr)."""
        pass

    @abstractmethod
    def interactive_session(self) -> Any:
        """Start/manage an interactive shell session."""
        pass

    @abstractmethod
    def shell_detection(self) -> str:
        """Detect the default shell for the platform."""
        pass

    # --- Environment & System ---

    @abstractmethod
    def user_home(self) -> str:
        """Get the path to the current user's home directory."""
        pass

    @abstractmethod
    def temp_directory(self) -> str:
        """Get the system temp directory path."""
        pass

    @abstractmethod
    def environment_variables(self) -> dict[str, str]:
        """Get all environment variables."""
        pass

    @abstractmethod
    def cpu_info(self) -> dict[str, Any]:
        """Get system CPU information."""
        pass

    @abstractmethod
    def memory_info(self) -> dict[str, Any]:
        """Get system memory information."""
        pass

    # --- Notifications ---

    @abstractmethod
    def desktop_notification(self, title: str, message: str) -> bool:
        """Send a native desktop notification."""
        pass

    @abstractmethod
    def sound(self, frequency: int, duration: int) -> None:
        """Play a beep sound with the specified frequency (Hz) and duration (ms)."""
        pass

    @abstractmethod
    def tray_icon(self) -> Any:
        """Return system tray interface helper (placeholder)."""
        pass
