"""
Realtimex Doctor and Crash Diagnostics tool.
Verifies host system capabilities and packages crash reports into diagnostic bundles.
"""

from __future__ import annotations

import os
import sys
import shutil
import json
import traceback
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_adapter import Platform


def run_doctor(api: Any) -> bool:
    """
    Verify host environment health and suitability for running Realtimex.
    """
    print("\n==================================================")
    print("🏥 Realtimex Doctor Diagnostics")
    print("==================================================\n")
    
    success = True
    
    # 1. Check Python version
    py_version = sys.version_info
    py_version_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    if py_version >= (3, 12):
        print(f"[✓] Python version: {py_version_str} (Required: >= 3.12)")
    else:
        print(f"[✗] Python version: {py_version_str} (Required: >= 3.12)")
        success = False

    # 2. Check Platform Adapter
    try:
        adapter = Platform.current()
        os_name = adapter.__class__.__name__
        print(f"[✓] Platform Adapter: {os_name} (OS: {platform.system()})")
    except Exception as e:
        print(f"[✗] Platform Adapter: Failed to load ({e})")
        success = False
        adapter = None

    # 3. Check Config File
    config_file = Path("config/config.json")
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                json.load(f)
            print(f"[✓] Configuration File: config/config.json is valid JSON")
        except Exception as e:
            print(f"[✗] Configuration File: config/config.json is invalid JSON ({e})")
            success = False
    else:
        print(f"[✗] Configuration File: config/config.json does not exist")
        success = False

    # 4. Check Log Directory permissions
    log_dir = Path("logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / ".doctor_write_test"
        test_file.write_text("ok", encoding="utf-8")
        assert test_file.read_text(encoding="utf-8") == "ok"
        test_file.unlink()
        print(f"[✓] Directory Permissions: Read/Write to logs directory is OK")
    except Exception as e:
        print(f"[✗] Directory Permissions: Failed to write to logs directory ({e})")
        success = False

    # 5. Check Disk Space
    try:
        total, used, free = shutil.disk_usage(".")
        free_gb = free / (1024**3)
        if free_gb >= 1.0:
            print(f"[✓] Disk Space: {free_gb:.1f} GB free space available")
        else:
            print(f"[✗] Disk Space: Only {free_gb:.1f} GB free space available (Recommend > 1.0 GB)")
            success = False
    except Exception as e:
        print(f"[✗] Disk Space: Failed to check disk usage ({e})")
        success = False

    # 6. Check Module Discovery
    modules_root = Path("modules")
    if modules_root.exists():
        try:
            module_dirs = [d for d in modules_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
            print(f"[✓] Module Discovery: Discovered {len(module_dirs)} modules in {modules_root}")
        except Exception as e:
            print(f"[✗] Module Discovery: Failed to read modules folder ({e})")
            success = False
    else:
        print(f"[✗] Module Discovery: {modules_root} directory does not exist")
        success = False

    # 7. Model Gateway Provider keys check
    env_keys = [k for k in os.environ if "API_KEY" in k]
    if env_keys:
        print(f"[✓] Model Gateway: Detected configured environment keys: {', '.join(env_keys)}")
    else:
        # Fallback to config check
        has_provider = False
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    cfg = json.load(f)
                    if "model_gateway" in cfg:
                        has_provider = True
            except Exception:
                pass
        if has_provider:
            print(f"[✓] Model Gateway: Configured using local/custom model providers in config.json")
        else:
            print(f"[!] Model Gateway: No model API keys detected in environment variables. Model calls may fall back.")

    print("\n==================================================")
    if success:
        print("✓ System is healthy and ready to run.")
    else:
        print("✗ System checks failed. Please address checks marked with [✗].")
    print("==================================================\n")
    
    return success


def generate_diagnostic_bundle(api: Any | None = None, error: Exception | None = None) -> Path:
    """
    Assemble system configuration, stack trace, and log records, and export a diagnostic bundle JSON.
    """
    import traceback
    
    adapter = Platform.current()
    snapshot = {}
    try:
        from observability.diagnostics.snapshots import take_system_snapshot
        snapshot = take_system_snapshot()
    except Exception:
        pass

    error_info = {}
    if error:
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }

    bundle = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": error_info,
        "system": {
            "os": platform.system(),
            "python_version": sys.version,
            "cpu": adapter.cpu_info() if adapter else {},
            "memory": adapter.memory_info() if adapter else {},
        },
        "kernel": api.status() if api else "Not Booted",
        "snapshot": snapshot,
    }

    log_dir = api._kernel._boot_paths.log_directory if api else Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_file = log_dir / f"realtimex_diagnostics_bundle_{timestamp_str}.json"

    with open(bundle_file, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    return bundle_file
