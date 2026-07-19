"""
Realtimex Kernel entry point and first task execution.
"""

from __future__ import annotations

import sys
import time
import logging
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
    
    # Load environment variables from .env file if present
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        import os
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k:
                            os.environ[k] = v
        except Exception:
            pass
    
    # Check if setup mode is requested or config.json is missing
    if (len(sys.argv) > 1 and sys.argv[1] == "setup") or not CONFIG_PATH.exists():
        from kernel.setup import run_setup
        success = run_setup()
        sys.exit(0 if success else 1)

    # Initialize Kernel API
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT
    )

    # Check if doctor mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        from kernel.doctor import run_doctor
        success = run_doctor(api)
        sys.exit(0 if success else 1)
    
    # Boot the kernel
    try:
        api.boot()
    except Exception as e:
        print(f"\n✗ Kernel Boot Failed: {e}")
        from kernel.doctor import generate_diagnostic_bundle
        bundle_path = generate_diagnostic_bundle(api=api, error=e)
        print(f"🏥 Generated crash report diagnostic bundle: {bundle_path}")
        print("Please provide this file when reporting issues.")
        sys.exit(1)

    # Check if developer mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        from kernel.dev_mode import run_developer_mode
        run_developer_mode(api)
        sys.exit(0)
    
    print("✓ Configuration Loaded")
    print("✓ Event Bus Started")
    print("✓ Registry Initialized")
    print("✓ Dependency Container Ready")
    print("✓ Services Loaded")
    print("✓ Lifecycle -> RUNNING\n")
    print("Kernel ready.\n")

    # Determine interactive vs single-command mode
    # If arguments are passed, treat them as a single command. Otherwise run REPL loop.
    is_interactive = (len(sys.argv) == 1)
    single_cmd = None
    if not is_interactive:
        single_cmd = " ".join(sys.argv[1:])
    else:
        # Mute all console logs during interactive REPL session to keep CLI clean
        for logger_name in list(logging.Logger.manager.loggerDict.keys()) + ["realtimex"]:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setLevel(logging.CRITICAL)

    cli = CLIInterface(
        user_id="user_cli",
        interactive=is_interactive,
        single_command=single_cmd,
        use_colors=True
    )
    
    # Unregister default CLI interface first to avoid duplicate registration error
    api.interface_manager.registry.unregister("cli")
    
    # Register CLI interface with Interface Manager
    api.interface_manager.register_interface(cli)
    api.interface_manager.start_interface("cli")
    
    print("==================================================")
    print("🚀 Welcome to Realtimex CLI Interface")
    if is_interactive:
        print("Type your task/request or type 'exit'/'quit' to exit.")
    else:
        print(f"Executing: '{single_cmd}'")
    print("==================================================\n")

    while True:
        try:
            request = api.interface_manager.receive("cli")
            if not request:
                if not is_interactive:
                    break
                continue

            # Allow user to quit
            user_input = request.user_input
            if isinstance(user_input, dict):
                raw_text = user_input.get("raw", "").strip().lower()
                action_text = user_input.get("action", "").strip().lower()
                if raw_text in ("exit", "quit") or action_text in ("exit", "quit"):
                    print("Exiting Realtimex CLI session.")
                    break

            # Route to Kernel and process request
            response = api.interface_manager.process_request(request)
            
            # Send immediate error response
            if response.status == "error":
                api.interface_manager.send(response)
                if not is_interactive:
                    break
                continue

            task_id = response.metadata.get("task_id")
            if task_id:
                # Wait/Poll silently until completion
                start_time = time.time()
                completed = False
                
                # Read task timeout from configuration (defaulting to 300)
                task_timeout = 300.0
                try:
                    task_timeout = float(api.config_manager.get("tasks", {}).get("timeout", 300.0))
                except Exception:
                    pass
                
                while time.time() - start_time < task_timeout:
                    task = api.task_manager.get_task(task_id)
                    if task.state == TaskState.COMPLETED:
                        completed = True
                        break
                    elif task.state == TaskState.FAILED:
                        break
                    time.sleep(0.1)
                    
                if completed:
                    # Fetch final response from memory
                    memories = api.memory_manager.search(query={"owner": task_id, "scope": "task"})
                    if memories:
                        raw_result = memories[0].content
                        clean_result = raw_result
                        if clean_result.startswith("Workflow result:"):
                            clean_result = clean_result[len("Workflow result:"):].strip()
                        if clean_result.startswith("[") and "]" in clean_result:
                            clean_result = clean_result.split("]", 1)[1].strip()
                        
                        print(f"\n{clean_result}\n")
                    else:
                        print("\n[No response content generated]\n")
                else:
                    print("\n✗ Task execution failed or timed out.\n")
            else:
                # Bypassed task system, send response directly
                api.interface_manager.send(response)
            
            if not is_interactive:
                break
                
        except KeyboardInterrupt:
            print("\nExiting Realtimex CLI session.")
            break
        except Exception as e:
            print(f"Error executing command: {e}")
            if not is_interactive:
                break

    # Shutdown kernel
    api.shutdown()


if __name__ == "__main__":
    main()
