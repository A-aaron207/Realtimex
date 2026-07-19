"""
Linux-specific Platform Adapter implementation.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any, Callable

from platform_adapter.base import BasePlatform


class PollingDirectoryWatcher:
    """
    Standard library-only directory watcher that polls file modification times.
    """

    def __init__(self, path: str, callback: Callable[[str], None], interval: float = 1.0) -> None:
        self.path = path
        self.callback = callback
        self.interval = interval
        self.files: dict[str, float] = {}
        self.running = True
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._watch_loop, name=f"DirWatcher-{path}", daemon=True)
        
        # Initial scan to populate baseline
        self._scan(is_baseline=True)
        self._thread.start()

    def _watch_loop(self) -> None:
        while True:
            with self._lock:
                if not self.running:
                    break
            time.sleep(self.interval)
            self._scan()

    def _scan(self, is_baseline: bool = False) -> None:
        if not os.path.exists(self.path):
            return
        
        current_files = {}
        for root, _, filenames in os.walk(self.path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                try:
                    mtime = os.path.getmtime(filepath)
                    current_files[filepath] = mtime
                except OSError:
                    pass

        if not is_baseline:
            # Check additions or updates
            for filepath, mtime in current_files.items():
                if filepath not in self.files:
                    # New file
                    self.callback(filepath)
                elif mtime > self.files[filepath]:
                    # Modified
                    self.callback(filepath)
                    
        self.files = current_files

    def stop(self) -> None:
        with self._lock:
            self.running = False


class LinuxPlatform(BasePlatform):
    """
    Linux platform execution adapter.
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
        return os.path.abspath(os.path.join(*parts))

    # --- Process Management ---

    def spawn_process(self, command: list[str] | str, env: dict[str, str] | None = None) -> subprocess.Popen:
        shell = isinstance(command, str)
        return subprocess.Popen(
            command,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env or os.environ.copy()
        )

    def kill_process(self, pid: int) -> bool:
        try:
            import signal
            os.kill(pid, signal.SIGKILL)
            return True
        except OSError:
            return False

    def wait_process(self, process: subprocess.Popen, timeout: float | None = None) -> int | None:
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    # --- Terminal ---

    def run_command(self, command: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
        p = self.spawn_process(command, env)
        stdout, stderr = process_outputs = p.communicate()
        return p.returncode, stdout, stderr

    def interactive_session(self) -> Any:
        # Simply runs bash on Linux for active terminal sessions
        return subprocess.Popen(
            [self.shell_detection()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def shell_detection(self) -> str:
        return os.environ.get("SHELL", "/bin/bash")

    # --- Environment & System ---

    def user_home(self) -> str:
        return os.path.expanduser("~")

    def temp_directory(self) -> str:
        return os.environ.get("TMPDIR", "/tmp")

    def environment_variables(self) -> dict[str, str]:
        return dict(os.environ)

    def cpu_info(self) -> dict[str, Any]:
        info = {
            "cores": os.cpu_count() or 1,
            "architecture": os.uname().machine,
            "model": "Generic Linux CPU"
        }
        # Parse model name from /proc/cpuinfo
        if os.path.exists("/proc/cpuinfo"):
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            info["model"] = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass
        return info

    def memory_info(self) -> dict[str, Any]:
        info = {
            "total_bytes": 0,
            "available_bytes": 0,
            "used_percent": 0.0
        }
        if os.path.exists("/proc/meminfo"):
            try:
                mem_total = 0
                mem_avail = 0
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_total = int(line.split()[1]) * 1024  # kB to bytes
                        elif line.startswith("MemAvailable:"):
                            mem_avail = int(line.split()[1]) * 1024  # kB to bytes
                if mem_total > 0:
                    info["total_bytes"] = mem_total
                    info["available_bytes"] = mem_avail
                    info["used_percent"] = round(((mem_total - mem_avail) / mem_total) * 100, 1)
            except Exception:
                pass
        return info

    # --- Notifications ---

    def desktop_notification(self, title: str, message: str) -> bool:
        try:
            # Check if notify-send command is available
            subprocess.run(["notify-send", title, message], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def sound(self, frequency: int, duration: int) -> None:
        try:
            # Attempt beep using simple beep command if installed
            subprocess.run(["beep", "-f", str(frequency), "-d", str(duration)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # Fallback to standard terminal beep sequence (bell char)
            print("\a", end="", flush=True)

    def tray_icon(self) -> Any:
        return None
