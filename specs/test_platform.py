"""
Cross-platform tests validating Platform Adapters.
"""

from __future__ import annotations

import os
import sys
import tempfile
import pytest
import platform
import subprocess

from platform_adapter import Platform
from platform_adapter.linux import LinuxPlatform
from platform_adapter.windows import WindowsPlatform
from platform_adapter.raspberry_pi import RaspberryPiPlatform


# Helper to determine if we can run live OS commands for an adapter
def can_run_live(adapter_class) -> bool:
    current_sys = platform.system()
    if current_sys == "Linux":
        return adapter_class in {LinuxPlatform, RaspberryPiPlatform}
    elif current_sys == "Windows":
        return adapter_class in {WindowsPlatform}
    return False


@pytest.mark.parametrize(
    "adapter_class",
    [LinuxPlatform, WindowsPlatform, RaspberryPiPlatform]
)
class TestPlatformAdapters:
    """
    Test suite executed against Linux, Windows, and Raspberry Pi adapters.
    """

    # --- Filesystem Tests ---

    def test_path_resolution(self, adapter_class):
        adapter = adapter_class()
        # Test basic path join and resolution
        resolved = adapter.resolve_paths("some", "sub", "dir")
        assert "some" in resolved
        assert "dir" in resolved
        if adapter_class == WindowsPlatform:
            assert "\\" in resolved
        else:
            assert "/" in resolved

    def test_file_read_write(self, adapter_class):
        adapter = adapter_class()
        # Write to a temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.txt")
            test_content = "Hello Cross Platform World!"
            
            # Write via adapter
            adapter.write_file(file_path, test_content)
            
            # Read via adapter
            content = adapter.read_file(file_path)
            assert content == test_content

    def test_watch_directory(self, adapter_class):
        adapter = adapter_class()
        changed_files = []
        
        def callback(path: str):
            changed_files.append(path)
            
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = adapter.watch_directory(tmpdir, callback)
            try:
                # Create a file inside watch directory
                test_file = os.path.join(tmpdir, "new_file.txt")
                with open(test_file, "w") as f:
                    f.write("trigger change")
                
                # Give it a brief moment to poll/scan
                import time
                time.sleep(1.2)
                
                assert len(changed_files) > 0
                assert test_file in changed_files[0]
            finally:
                watcher.stop()

    # --- Environment Tests ---

    def test_user_home(self, adapter_class):
        adapter = adapter_class()
        home = adapter.user_home()
        assert home
        assert os.path.isdir(home) or not can_run_live(adapter_class)

    def test_temp_directory(self, adapter_class):
        adapter = adapter_class()
        temp = adapter.temp_directory()
        assert temp
        assert os.path.isdir(temp) or not can_run_live(adapter_class)

    def test_environment_variables(self, adapter_class):
        adapter = adapter_class()
        env = adapter.environment_variables()
        assert isinstance(env, dict)
        if can_run_live(adapter_class):
            assert len(env) > 0

    # --- Live System Operations (Skipped on incompatible hosts) ---

    def test_cpu_and_memory_info(self, adapter_class):
        if not can_run_live(adapter_class):
            pytest.skip("Cannot run live OS hardware metrics for this adapter on current host")
            
        adapter = adapter_class()
        cpu = adapter.cpu_info()
        assert "cores" in cpu
        assert cpu["cores"] >= 1
        assert "model" in cpu
        
        mem = adapter.memory_info()
        assert "total_bytes" in mem
        assert "available_bytes" in mem
        assert "used_percent" in mem
        assert mem["total_bytes"] >= 0

    def test_spawn_and_kill_process(self, adapter_class):
        if not can_run_live(adapter_class):
            pytest.skip("Cannot run live process spawning for this adapter on current host")
            
        adapter = adapter_class()
        cmd = ["sleep", "10"] if adapter_class != WindowsPlatform else ["timeout", "10"]
        
        proc = adapter.spawn_process(cmd)
        assert isinstance(proc, subprocess.Popen)
        assert proc.poll() is None  # Process is running
        
        # Terminate process
        killed = adapter.kill_process(proc.pid)
        assert killed
        
        # Wait with timeout
        exit_code = adapter.wait_process(proc, timeout=2.0)
        assert exit_code is not None

    def test_run_command(self, adapter_class):
        if not can_run_live(adapter_class):
            pytest.skip("Cannot run live command execution for this adapter on current host")
            
        adapter = adapter_class()
        cmd = "echo hello" if adapter_class != WindowsPlatform else "cmd /c echo hello"
        
        exit_code, stdout, stderr = adapter.run_command(cmd)
        assert exit_code == 0
        assert "hello" in stdout.lower()

    def test_shell_detection(self, adapter_class):
        adapter = adapter_class()
        shell = adapter.shell_detection()
        assert shell
        if adapter_class == WindowsPlatform:
            assert "cmd" in shell.lower() or "powershell" in shell.lower()
        else:
            assert "bin" in shell or "sh" in shell
