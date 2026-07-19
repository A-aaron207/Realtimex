"""
Tests for the Browser Module.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from kernel.api import KernelAPI
from workers.context import ExecutionContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
MODULES_ROOT = PROJECT_ROOT / "modules"


@pytest.fixture(scope="module")
def booted_api():
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT
    )
    api.boot()
    yield api
    api.shutdown()


@pytest.fixture(scope="module")
def browser(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "browser" in module_loader._loaded_modules
    return module_loader._loaded_modules["browser"].instance


def _ctx(capability: str, input_data: dict) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_browser",
        workflow_id="test_browser_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


def test_browser_module_loaded(browser):
    assert "navigate" in browser.capabilities
    assert "extract_content" in browser.capabilities
    assert "click_element" in browser.capabilities
    assert "fill_form" in browser.capabilities


def test_navigate(browser):
    result = browser.execute("navigate", _ctx("navigate", {"url": "https://example.com"}))
    assert result["status"] == "SUCCESS"
    assert result["url"] == "https://example.com"
    assert "page_snapshot" in result
    assert len(result["page_snapshot"]) > 0


def test_extract_content(browser):
    # Navigate first so snapshot is populated
    browser.execute("navigate", _ctx("navigate", {"url": "https://example.com"}))
    result = browser.execute("extract_content", _ctx("extract_content", {"selector": "main heading"}))
    assert result["status"] == "SUCCESS"
    assert "extracted_content" in result
    assert len(result["extracted_content"]) > 0


def test_click_element(browser):
    browser.execute("navigate", _ctx("navigate", {"url": "https://example.com"}))
    result = browser.execute("click_element", _ctx("click_element", {"element": "Learn More"}))
    assert result["status"] == "SUCCESS"
    assert "outcome" in result
    assert len(result["outcome"]) > 0


def test_fill_form(browser):
    browser.execute("navigate", _ctx("navigate", {"url": "https://example.com/signup"}))
    result = browser.execute("fill_form", _ctx("fill_form", {
        "fields": {"username": "realtimex_user", "email": "user@realtimex.io", "password": "securepass"},
        "submit": True
    }))
    assert result["status"] == "SUCCESS"
    assert result["submitted"] is True
    assert "outcome" in result
