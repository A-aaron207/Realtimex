"""
Windows-specific Platform Adapter implementation.
"""

from __future__ import annotations

import os
import subprocess
import ctypes
from typing import Any, Callable

from platform_adapter.base import BasePlatform
from platform_adapter.linux import PollingDirectoryWatcher


# ctypes structure for Windows Memory Querying
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class WindowsPlatform(BasePlatform):
    """
    Windows platform execution adapter.
    """

    # --- Filesystem ---

    def read_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def watch_directory(self, path: str, callback: Callable[[str], None]) -> Any:
        return PollingDirectoryWatcher(path, callback)

    def resolve_paths(self, *parts: str) -> str:
        # Resolve to standard Windows backslash-separated absolute path
        return os.path.abspath(os.path.join(*parts)).replace("/", "\\")

    # --- Process Management ---

    def spawn_process(self, command: list[str] | str, env: dict[str, str] | None = None) -> subprocess.Popen:
        shell = isinstance(command, str)
        # Windows requires creationflags to avoid popping cmd windows for GUI apps sometimes
        creationflags = 0
        if not shell:
            # CREATE_NO_WINDOW
            creationflags = 0x08000000
        return subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env or os.environ.copy(),
            creationflags=creationflags
        )

    def kill_process(self, pid: int) -> bool:
        try:
            # Use taskkill /F /PID
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def wait_process(self, process: subprocess.Popen, timeout: float | None = None) -> int | None:
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    # --- Terminal ---

    def run_command(self, command: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
        p = self.spawn_process(command, env)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr

    def interactive_session(self) -> Any:
        return subprocess.Popen(
            [self.shell_detection()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def shell_detection(self) -> str:
        return os.environ.get("COMSPEC", "cmd.exe")

    # --- Environment & System ---

    def user_home(self) -> str:
        return os.environ.get("USERPROFILE", os.path.expanduser("~"))

    def temp_directory(self) -> str:
        return os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))

    def environment_variables(self) -> dict[str, str]:
        return dict(os.environ)

    def cpu_info(self) -> dict[str, Any]:
        info = {
            "cores": os.cpu_count() or 1,
            "architecture": os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64"),
            "model": os.environ.get("PROCESSOR_IDENTIFIER", "Generic Windows CPU")
        }
        return info

    def memory_info(self) -> dict[str, Any]:
        info = {
            "total_bytes": 0,
            "available_bytes": 0,
            "used_percent": 0.0
        }
        try:
            # Query global memory status via ctypes kernel32 API call
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                info["total_bytes"] = stat.ullTotalPhys
                info["available_bytes"] = stat.ullAvailPhys
                info["used_percent"] = float(stat.dwMemoryLoad)
        except Exception:
            pass
        return info

    # --- Notifications ---

    def desktop_notification(self, title: str, message: str) -> bool:
        try:
            # Trigger native balloon notification using Powershell cmdlet
            ps_script = (
                f"[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
                f"$notification = New-Object System.Windows.Forms.NotifyIcon; "
                f"$notification.Icon = [System.Drawing.SystemIcons]::Information; "
                f"$notification.BalloonTipTitle = '{title}'; "
                f"$notification.BalloonTipText = '{message}'; "
                f"$notification.Visible = $True; "
                f"$notification.ShowBalloonTip(5000)"
            )
            subprocess.run(["powershell", "-Command", ps_script], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def sound(self, frequency: int, duration: int) -> None:
        try:
            import winsound
            winsound.Beep(frequency, duration)
        except Exception:
            # Bell fallback
            print("\a", end="", flush=True)

    def tray_icon(self) -> Any:
        return None
