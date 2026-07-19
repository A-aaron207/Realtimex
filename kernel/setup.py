"""
Realtimex Setup Wizard.
Guides first-time users through configuration and system setup.
"""

from __future__ import annotations

import os
import json
from pathlib import Path


def run_setup() -> bool:
    """
    Interactively set up config.json, directories, and API keys.
    """
    print("\n==================================================")
    print("🔧 Realtimex First-Launch Setup Wizard")
    print("==================================================\n")
    print("This wizard will prepare your config.json and directory structures.\n")
    
    # 1. Choose Model Provider
    print("Select your preferred AI model provider:")
    print("  1) Anthropic (Claude models)")
    print("  2) OpenAI (GPT models)")
    print("  3) OpenRouter")
    print("  4) Gemini")
    print("  5) Mock/Testing (No API key required)")
    
    choice = ""
    while choice not in ("1", "2", "3", "4", "5"):
        choice = input("\nEnter choice (1-5) [default: 5]: ").strip()
        if not choice:
            choice = "5"
            
    provider_map = {
        "1": ("anthropic", "ANTHROPIC_API_KEY"),
        "2": ("openai", "OPENAI_API_KEY"),
        "3": ("openrouter", "OPENROUTER_API_KEY"),
        "4": ("gemini", "GEMINI_API_KEY"),
        "5": ("mock", None)
    }
    
    provider_name, api_key_name = provider_map[choice]
    api_key_val = ""
    
    if api_key_name:
        print(f"\nYou selected {provider_name.upper()}.")
        api_key_val = input(f"Enter your {api_key_name} (optional if set in env): ").strip()
        if api_key_val:
            os.environ[api_key_name] = api_key_val
            print(f"✓ API key captured.")
        else:
            print(f"No key entered. Ensure {api_key_name} is set in your environment.")
            
    # 2. Setup Directory Paths
    default_work_dir = os.getcwd()
    work_dir = input(f"\nEnter the workspace/log directory [default: {default_work_dir}]: ").strip()
    if not work_dir:
        work_dir = default_work_dir
        
    base_path = Path(work_dir)
    print(f"\nPreparing directory structures at: {base_path}")
    
    dirs_to_create = [
        "logs",
        "config",
        "modules",
        "workflows",
        "tasks",
        "permissions"
    ]
    
    for d in dirs_to_create:
        path = base_path / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created directory: {d}/")
        
    # 3. Create default config.json
    config_data = {
        "kernel": {
            "name": "realtimex-kernel",
            "version": "1.0.0",
            "environment": "production"
        },
        "logging": {
            "level": "INFO",
            "filename": "kernel.log"
        },
        "event_bus": {
            "enabled": True,
            "history_max_size": 10000,
            "persistence_filename": "events.jsonl",
            "event_log_filename": "event_log.jsonl"
        },
        "task_system": {
            "enabled": True,
            "tasks_directory": "tasks"
        },
        "workflow_engine": {
            "enabled": True,
            "workflows_directory": "workflows"
        },
        "service_registry": {
            "enabled": True
        },
        "capability_registry": {
            "enabled": True
        },
        "recovery_manager": {
            "enabled": True
        },
        "model_gateway": {
            "default_provider": provider_name,
            "providers": {
                "anthropic": {
                    "model": "claude-3-5-sonnet"
                },
                "openai": {
                    "model": "gpt-4o"
                },
                "openrouter": {
                    "model": "meta-llama/llama-3.1-70b-instruct"
                },
                "gemini": {
                    "model": "gemini-1.5-pro"
                },
                "mock": {
                    "model": "mock-model"
                }
            }
        }
    }
    
    config_file = base_path / "config" / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"  ✓ Written configuration: config/config.json")
    
    # 4. Save API Key to env file
    if api_key_val and api_key_name:
        env_file = base_path / ".env"
        with open(env_file, "a", encoding="utf-8") as f:
            f.write(f"\n{api_key_name}={api_key_val}\n")
        print(f"  ✓ Saved API key in env file: .env")

    print("\n==================================================")
    print("✓ Setup Complete! Running environment diagnostics...")
    print("==================================================\n")
    
    # Run doctor check
    from kernel.doctor import run_doctor
    run_doctor(None)
    
    return True
