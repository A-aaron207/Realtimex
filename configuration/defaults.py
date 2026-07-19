"""
Default Configuration for Realtimex.

Provides default configuration values for all subsystems.
"""

from __future__ import annotations

# Kernel configuration defaults
KERNEL_DEFAULTS = {
    "name": "Realtimex Kernel",
    "version": "1.0.0",
    "environment": "development",
    "debug": True,
    "log_level": "INFO",
}

# Scheduler configuration defaults
SCHEDULER_DEFAULTS = {
    "max_workers": 8,
    "task_timeout": 300,  # 5 minutes
    "heartbeat_interval": 10,
    "max_retries": 3,
}

# Worker configuration defaults
WORKER_DEFAULTS = {
    "timeout": 300,
    "memory_limit": 2048,  # MB
    "cpu_limit": 4,
    "max_concurrent_tasks": 4,
}

# Memory configuration defaults
MEMORY_DEFAULTS = {
    "capacity": 1000000,  # entries
    "retention_days": 30,
    "cleanup_interval": 3600,  # seconds
    "compression": False,
}

# Event System configuration defaults
EVENT_DEFAULTS = {
    "buffer_size": 10000,
    "subscriber_timeout": 5,
    "async_enabled": True,
    "persistence_enabled": False,
}

# Task configuration defaults
TASK_DEFAULTS = {
    "max_input_size": 1000000,  # bytes
    "max_output_size": 10000000,  # bytes
    "timeout": 300,
    "retry_backoff": 1.5,
    "max_retries": 3,
}

# Workflow configuration defaults
WORKFLOW_DEFAULTS = {
    "max_steps": 100,
    "step_timeout": 300,
    "max_parallel_steps": 4,
    "error_handling": "fail_fast",
}

# Model Gateway configuration defaults
MODEL_GATEWAY_DEFAULTS = {
    "default_model": "gpt-4",
    "api_timeout": 30,
    "max_tokens": 4096,
    "temperature": 0.7,
    "retry_count": 3,
}

# Cognitive Engine configuration defaults
COGNITIVE_ENGINE_DEFAULTS = {
    "reasoning_depth": 5,
    "max_branches": 10,
    "cache_enabled": True,
    "cache_ttl": 3600,
}

# Permission System configuration defaults
PERMISSION_DEFAULTS = {
    "cache_ttl": 3600,
    "max_cache_entries": 10000,
    "policy_refresh_interval": 60,
    "default_policy": "deny",
}

# Recovery System configuration defaults
RECOVERY_DEFAULTS = {
    "checkpoint_interval": 300,
    "max_checkpoints": 10,
    "snapshot_enabled": True,
    "auto_cleanup": True,
    "retention_days": 7,
}

# Interface Layer configuration defaults
INTERFACE_DEFAULTS = {
    "cli_enabled": True,
    "rest_enabled": True,
    "rest_port": 8000,
    "websocket_enabled": True,
    "websocket_port": 8001,
    "session_timeout": 3600,
    "max_sessions": 1000,
}

# Logging configuration defaults
LOGGING_DEFAULTS = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_enabled": True,
    "file_path": "logs/realtimex.log",
    "max_file_size": 104857600,  # 100MB
    "backup_count": 5,
}

# All default configurations
ALL_DEFAULTS = {
    "kernel": KERNEL_DEFAULTS,
    "scheduler": SCHEDULER_DEFAULTS,
    "workers": WORKER_DEFAULTS,
    "memory": MEMORY_DEFAULTS,
    "events": EVENT_DEFAULTS,
    "tasks": TASK_DEFAULTS,
    "workflows": WORKFLOW_DEFAULTS,
    "models": MODEL_GATEWAY_DEFAULTS,
    "cognitive": COGNITIVE_ENGINE_DEFAULTS,
    "permissions": PERMISSION_DEFAULTS,
    "recovery": RECOVERY_DEFAULTS,
    "interfaces": INTERFACE_DEFAULTS,
    "logging": LOGGING_DEFAULTS,
}


def get_default(namespace: str, key: str | None = None) -> dict | any:
    """
    Get default configuration value.
    
    Args:
        namespace: Configuration namespace
        key: Optional specific key within namespace
        
    Returns:
        Configuration value or entire namespace dict
    """
    if namespace not in ALL_DEFAULTS:
        return {} if key is None else None
    
    namespace_config = ALL_DEFAULTS[namespace]
    
    if key is None:
        return namespace_config.copy()
    
    return namespace_config.get(key)


def get_all_defaults() -> dict:
    """
    Get all default configuration values.
    
    Returns:
        Complete default configuration dictionary
    """
    return {k: v.copy() for k, v in ALL_DEFAULTS.items()}
