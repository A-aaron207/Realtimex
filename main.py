"""
Realtimex Kernel entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path
from kernel.api import KernelAPI
from kernel.lifecycle import KernelState

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
MODULES_ROOT = PROJECT_ROOT / "modules"


def main() -> None:
    print("[BOOT] Realtimex Kernel v0.1\n")
    
    # Initialize and boot the kernel
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT
    )
    api.boot()
    
    # Print status checks
    if api.config_manager is not None:
        print("✓ Configuration Loaded")
        
    if api.event_manager is not None:
        print("✓ Event Bus Started")
        
    if api.capability_registry is not None:
        print("✓ Registry Initialized")
        
    if api.dependency_container is not None:
        print("✓ Dependency Container Ready")
        
    if api.loaded_modules is not None:
        print("✓ Services Loaded")
        
    state = api.status().get("state")
    if state == "RUNNING" or state == "KernelState.RUNNING":
        print("✓ Lifecycle -> RUNNING")
        
    print("\nKernel ready.")
    
    # Shutdown cleanly
    api.shutdown()


if __name__ == "__main__":
    main()
