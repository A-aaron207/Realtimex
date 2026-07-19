"""
Unit tests for the Realtimex SDK / Module Development Kit (MDK).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock

from events.bus import EventBus
from sdk import (
    create_module,
    validate,
    build,
    install,
    package,
    doctor,
    generate_docs,
    SDKError,
    GeneratorError,
    SDKValidationError,
    PackagingError,
)


@pytest.fixture
def temp_dir():
    """Fixture for temporary directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def event_bus():
    """Fixture for Event Bus."""
    return MagicMock(spec=EventBus)


def test_module_scaffolding(temp_dir, event_bus):
    """Test scaffolding a module, provider, and worker."""
    # Scaffold Module
    mod_path = create_module("weather_module", temp_dir, "module", event_bus)
    assert os.path.exists(mod_path)
    assert os.path.exists(os.path.join(mod_path, "manifest.json"))
    assert os.path.exists(os.path.join(mod_path, "weather_module.py"))
    assert os.path.exists(os.path.join(mod_path, "tests"))
    assert os.path.exists(os.path.join(mod_path, "prompts"))
    assert os.path.exists(os.path.join(mod_path, "assets"))
    
    # Verify manifest details
    with open(os.path.join(mod_path, "manifest.json"), "r") as f:
        manifest = json.load(f)
    assert manifest["name"] == "weather_module"
    assert manifest["type"] == "module"
    assert manifest["entrypoint"] == "weather_module.py"
    
    # EventBus trigger check
    assert event_bus.publish.called

    # Scaffold Worker
    worker_path = create_module("image_worker", temp_dir, "worker")
    assert os.path.exists(worker_path)
    assert os.path.exists(os.path.join(worker_path, "image_worker.py"))

    # Scaffold Provider
    provider_path = create_module("gpt_provider", temp_dir, "provider")
    assert os.path.exists(provider_path)
    assert os.path.exists(os.path.join(provider_path, "gpt_provider.py"))

    # Fail on existing directory
    with pytest.raises(GeneratorError):
        create_module("weather_module", temp_dir, "module")


def test_validation_rules(temp_dir):
    """Test validator on valid/invalid manifest structure and AST lints."""
    mod_path = create_module("my_mod", temp_dir, "module")
    
    # Validate initial scaffold (should pass)
    success, errors = validate(mod_path)
    assert success
    assert len(errors) == 0

    # Test invalid json manifest parsing
    manifest_file = os.path.join(mod_path, "manifest.json")
    with open(manifest_file, "w") as f:
        f.write("{invalid-json}")
    success, errors = validate(mod_path)
    assert not success
    assert "Failed to parse JSON" in errors[0]

    # Test missing manifest
    os.remove(manifest_file)
    success, errors = validate(mod_path)
    assert not success
    assert "Missing required file" in errors[0]

    # Test invalid type schema values
    manifest_err = {
        "name": "MY_MOD",  # Upper case should fail regex rules
        "version": "1.0",   # Incorrect semver
        "type": "database", # Incorrect type
        "entrypoint": "db.py"
    }
    with open(manifest_file, "w") as f:
        json.dump(manifest_err, f)
    success, errors = validate(mod_path)
    assert not success
    # Check all failures are detected
    assert any("name must be lowercase" in err for err in errors)
    assert any("version must follow" in err for err in errors)
    assert any("type must be one of" in err for err in errors)


def test_packaging_building_and_exporting(temp_dir, event_bus):
    """Test building extension tarball packages."""
    mod_path = create_module("pack_module", temp_dir, "module")
    dist_dir = os.path.join(temp_dir, "dist")
    
    # Build package successfully
    package_path = build(mod_path, dist_dir, event_bus)
    assert os.path.exists(package_path)
    assert package_path.endswith("pack_module-1.0.0.rtx")
    assert event_bus.publish.called

    # Alias check
    package_path_alias = package(mod_path, dist_dir)
    assert os.path.exists(package_path_alias)


def test_package_installation_and_uninstallation(temp_dir, event_bus):
    """Test extracting, installing, and removing packages."""
    mod_path = create_module("install_module", temp_dir, "module")
    dist_dir = os.path.join(temp_dir, "dist")
    install_dir = os.path.join(temp_dir, "modules")
    
    # Build
    package_path = build(mod_path, dist_dir)
    
    # Install
    installed_dir = install(package_path, install_dir, event_bus)
    assert os.path.exists(installed_dir)
    assert os.path.exists(os.path.join(installed_dir, "manifest.json"))
    assert os.path.exists(os.path.join(installed_dir, "install_module.py"))
    assert event_bus.publish.called
    
    # Uninstall
    from sdk.packaging.installer import uninstall_package
    uninstall_package("install_module", install_dir, event_bus)
    assert not os.path.exists(installed_dir)


def test_documentation_generation(temp_dir):
    """Test automated markdown documentation output."""
    docs_path = os.path.join(temp_dir, "docs", "REFERENCE.md")
    path = generate_docs(docs_path)
    assert os.path.exists(path)
    with open(path, "r") as f:
        content = f.read()
    assert "Realtimex Extension Development Reference" in content
    assert "manifest.json" in content


def test_doctor_check():
    """Test doctor environment analyzer diagnostic checks."""
    # Runs the diagnostics check and prints out status
    doctor()
    assert True


def test_cli_parser(temp_dir):
    """Test MDK CLI parser routing execution."""
    from sdk.cli.realtimex_sdk import main as cli_main
    
    # Create module via CLI
    module_name = "cli_module"
    cli_main(["create-module", module_name, "--output-dir", temp_dir])
    
    cli_path = os.path.join(temp_dir, module_name)
    assert os.path.exists(cli_path)
    assert os.path.exists(os.path.join(cli_path, "manifest.json"))
    
    # Run validate via CLI
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        cli_main(["validate", cli_path])
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
