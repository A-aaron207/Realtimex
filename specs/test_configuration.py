"""
Unit tests for the Realtimex Configuration System.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock

from configuration.manager import ConfigurationManager
from configuration.exceptions import (
    ConfigurationValidationError,
    ProfileNotFoundError,
)
from events.bus import EventBus


@pytest.fixture
def config_dir():
    """Fixture for temporary configuration directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def event_bus():
    """Fixture for Event Bus."""
    return MagicMock(spec=EventBus)


def test_configuration_manager_initialization(config_dir, event_bus):
    """Test that ConfigurationManager initializes correctly with defaults."""
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    # Check default value
    assert manager.get("kernel.name") == "Realtimex Kernel"
    assert manager.get("scheduler.max_workers") == 8
    
    # Check if event was emitted
    assert event_bus.publish.called


def test_configuration_manager_set_get(config_dir, event_bus):
    """Test setting and getting configuration values."""
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    manager.set("kernel.name", "New Kernel Name")
    assert manager.get("kernel.name") == "New Kernel Name"
    
    # Test getting entire namespace
    kernel_config = manager.get("kernel")
    assert kernel_config["name"] == "New Kernel Name"


def test_configuration_validation(config_dir, event_bus):
    """Test configuration validation."""
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    # Register a rule
    manager.validator.register_rule(
        "kernel", "max_threads", required=True, expected_type=int, min_value=1, max_value=100
    )
    
    # Valid set
    manager.set("kernel.max_threads", 50)
    assert manager.get("kernel.max_threads") == 50
    
    # Invalid type
    with pytest.raises(ConfigurationValidationError):
        manager.set("kernel.max_threads", "not an int")
    
    # Out of range
    with pytest.raises(ConfigurationValidationError):
        manager.set("kernel.max_threads", 200)


def test_configuration_persistence(config_dir, event_bus):
    """Test saving configuration to disk."""
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    manager.set("kernel.name", "Persistent Kernel", persist=True)
    
    # Check if file exists
    config_file = os.path.join(config_dir, "kernel.json")
    assert os.path.exists(config_file)
    
    # Verify content
    import json
    with open(config_file, 'r') as f:
        data = json.load(f)
    assert data["kernel"]["name"] == "Persistent Kernel"


def test_environment_overrides(config_dir, event_bus):
    """Test environment-specific overrides."""
    # Create production override file
    prod_dir = os.path.join(config_dir, "production")
    os.makedirs(prod_dir)
    with open(os.path.join(prod_dir, "kernel.json"), 'w') as f:
        import json
        json.dump({"kernel": {"debug": False}}, f)
        
    manager = ConfigurationManager(
        event_bus=event_bus, config_dir=config_dir, environment="production"
    )
    manager.initialize()
    
    # Built-in production override: debug=False
    # File production override: debug=False
    assert manager.get("kernel.debug") is False
    assert manager.get("logging.level") == "WARNING"


def test_hot_reload_subscription(config_dir, event_bus):
    """Test subscribing to configuration changes."""
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    callback = MagicMock()
    manager.subscribe("kernel", callback)
    
    manager.set("kernel.name", "Hot Reloaded Name")
    
    # Callback should be called with the new namespace config
    callback.assert_called_once()
    assert callback.call_args[0][0]["name"] == "Hot Reloaded Name"


def test_profile_switching(config_dir, event_bus):
    """Test switching configuration profiles."""
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    # Create a custom profile
    manager.profiles.create_profile("high_performance", config={
        "scheduler": {"max_workers": 32},
        "memory": {"capacity": 10000000}
    })
    
    manager.profile("high_performance")
    
    assert manager.get("scheduler.max_workers") == 32
    assert manager.get("memory.capacity") == 10000000
    
    # Shutdown manager to clean up background thread
    manager.shutdown()


def test_yaml_toml_fallback_persistence(config_dir):
    """Test saving configuration with custom YAML and TOML serializers."""
    from configuration.persistence import ConfigurationPersistence
    pers = ConfigurationPersistence()
    
    config = {
        "kernel": {
            "name": "Fallback Test",
            "debug": True,
            "max_workers": 4,
            "tags": ["ai", "orchestrator"]
        }
    }
    
    # Save YAML
    yaml_path = os.path.join(config_dir, "test.yaml")
    pers.save_yaml(yaml_path, config)
    assert os.path.exists(yaml_path)
    
    # Save TOML
    toml_path = os.path.join(config_dir, "test.toml")
    pers.save_toml(toml_path, config)
    assert os.path.exists(toml_path)


def test_hot_reload_file_monitoring(config_dir, event_bus):
    """Test background thread hot reload file change detection."""
    import time
    import json
    
    # Create initial file
    kernel_file = os.path.join(config_dir, "kernel.json")
    with open(kernel_file, "w") as f:
        json.dump({"kernel": {"name": "Initial Name", "debug": True}}, f)
        
    manager = ConfigurationManager(event_bus=event_bus, config_dir=config_dir)
    manager.initialize()
    
    assert manager.get("kernel.name") == "Initial Name"
    
    # Wait to guarantee different mtime resolution
    time.sleep(0.1)
    
    # Modify file
    with open(kernel_file, "w") as f:
        json.dump({"kernel": {"name": "Hot Reloaded File Name", "debug": True}}, f)
        
    # Wait for the background thread to poll (interval is 1.0s, let's wait 1.5s)
    time.sleep(1.5)
    
    # Verify name was reloaded and updated in registry
    assert manager.get("kernel.name") == "Hot Reloaded File Name"
    
    # Cleanup background thread
    manager.shutdown()

