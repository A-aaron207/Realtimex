"""
Realtimex Kernel entry point and first task execution.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from kernel.api import KernelAPI
from kernel.lifecycle import KernelState
from interfaces.cli.interface import CLIInterface
from tasks.states import TaskState

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
MODULES_ROOT = PROJECT_ROOT / "modules"


def main() -> None:
    print("[BOOT] Realtimex Kernel v0.1\n")
    
    # Initialize Kernel API
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT
    )
    
    # Boot the kernel
    api.boot()
    
    print("✓ Configuration Loaded")
    print("✓ Event Bus Started")
    print("✓ Registry Initialized")
    print("✓ Dependency Container Ready")
    print("✓ Services Loaded")
    print("✓ Lifecycle -> RUNNING\n")
    print("Kernel ready.\n")

    # Define the input text to summarize
    input_text = "Our team successfully completed Sprint 1 ahead of schedule. All integration tests passed, and the boot sequence is now fully deterministic."
    command_str = f"Summarize this text: {input_text}"
    
    print(f"User Input:\n{command_str}\n")
    
    # Initialize CLI interface in single command mode
    cli = CLIInterface(
        user_id="user_cli",
        interactive=False,
        single_command=command_str,
        use_colors=True
    )
    
    # Unregister default CLI interface first to avoid duplicate registration error
    api.interface_manager.registry.unregister("cli")
    
    # Register CLI interface with Interface Manager
    api.interface_manager.register_interface(cli)
    api.interface_manager.start_interface("cli")
    
    # Receive the request from CLI
    request = api.interface_manager.receive("cli")
    if request:
        print("[ROUTE] CLI -> Kernel")
        
        # Process the request to spawn task and workflow asynchronously
        response = api.interface_manager.process_request(request)
        api.interface_manager.send(response)
        
        task_id = response.metadata.get("task_id")
        if task_id:
            # Poll task state to block main thread until completion
            print("[WAIT] Orchestrating task execution...")
            start_time = time.time()
            completed = False
            
            while time.time() - start_time < 10.0:
                task = api.task_manager.get_task(task_id)
                if task.state == TaskState.COMPLETED:
                    completed = True
                    break
                elif task.state == TaskState.FAILED:
                    print("✗ Task execution failed!")
                    break
                time.sleep(0.1)
                
            if completed:
                print("✓ Task Execution Successful.")
                
                # Fetch memory update to verify
                memories = api.memory_manager.search(query={"owner": task_id, "scope": "task"})
                if memories:
                    print(f"\n[MEMORY] Retrieved memory update for task:")
                    for m in memories:
                        print(f"  - {m.content}")
            else:
                print("✗ Task execution timed out.")
                
    # Shutdown kernel
    api.shutdown()


if __name__ == "__main__":
    main()
