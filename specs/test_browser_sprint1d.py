"""
Sprint 1D — Browser Reliability Tests
======================================
Covers: browser navigation, content extraction, element interaction,
        form filling, state tracking, error handling for missing inputs,
        automatic navigation on URL change, capability contracts, and
        edge cases.

Target: reach 90/90 on the Browser subsystem.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any

from kernel.api import KernelAPI
from loader.module_base import ModuleEntryPoint
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


@pytest.fixture(scope="function")
def browser(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "browser" in module_loader._loaded_modules
    browser_instance = module_loader._loaded_modules["browser"].instance
    # Reset internal page state per test
    browser_instance._current_url = None
    browser_instance._page_snapshot = ""
    return browser_instance


def _ctx(capability: str, input_data: dict[str, Any]) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_browser_task",
        workflow_id="test_browser_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


def test_browser_module_contract(browser):
    """Browser module implements ModuleEntryPoint interface."""
    assert isinstance(browser, ModuleEntryPoint)
    assert browser.module_id == "browser"
    assert "navigate" in browser.capabilities
    assert "extract_content" in browser.capabilities
    assert "click_element" in browser.capabilities
    assert "fill_form" in browser.capabilities


def test_describe_returns_non_empty_string(browser):
    """describe() returns module summary string."""
    desc = browser.describe()
    assert isinstance(desc, str)
    assert len(desc) > 0


# --- Navigate ---

def test_navigate_missing_url(browser):
    """navigate without URL returns FAILED status."""
    result = browser.navigate({})
    assert result["status"] == "FAILED"
    assert "error" in result


def test_navigate_empty_url(browser):
    """navigate with empty string URL returns FAILED status."""
    result = browser.navigate({"url": ""})
    assert result["status"] == "FAILED"


def test_navigate_valid_url(browser):
    """navigate with valid URL returns SUCCESS status and updates current_url."""
    result = browser.navigate({"url": "https://example.com"})
    assert result["status"] == "SUCCESS"
    assert result["url"] == "https://example.com"
    assert browser._current_url == "https://example.com"
    assert "page_snapshot" in result


# --- Extract Content ---

def test_extract_content_no_page_loaded(browser):
    """extract_content without prior navigation or URL returns FAILED status."""
    result = browser.extract_content({"selector": "h1"})
    assert result["status"] == "FAILED"
    assert "No page loaded" in result["error"]


def test_extract_content_with_auto_navigate(browser):
    """extract_content with explicit URL auto-navigates and succeeds."""
    result = browser.extract_content({"url": "https://example.com/about", "selector": "title"})
    assert result["status"] == "SUCCESS"
    assert browser._current_url == "https://example.com/about"
    assert "extracted_content" in result


def test_extract_content_uses_description_fallback(browser):
    """extract_content falls back to 'description' when 'selector' is missing."""
    browser.navigate({"url": "https://example.com"})
    result = browser.extract_content({"description": "hero section"})
    assert result["status"] == "SUCCESS"
    assert result["selector"] == "hero section"


# --- Click Element ---

def test_click_element_missing_target(browser):
    """click_element with no element or text returns FAILED status."""
    result = browser.click_element({})
    assert result["status"] == "FAILED"
    assert "error" in result


def test_click_element_valid(browser):
    """click_element with valid element succeeds."""
    browser.navigate({"url": "https://example.com"})
    result = browser.click_element({"element": "Submit Button"})
    assert result["status"] == "SUCCESS"
    assert result["element_clicked"] == "Submit Button"
    assert "outcome" in result


def test_click_element_auto_navigate(browser):
    """click_element with new URL auto-navigates before clicking."""
    result = browser.click_element({"url": "https://example.com/login", "text": "Login"})
    assert result["status"] == "SUCCESS"
    assert browser._current_url == "https://example.com/login"


# --- Fill Form ---

def test_fill_form_missing_fields(browser):
    """fill_form without fields returns FAILED status."""
    result = browser.fill_form({})
    assert result["status"] == "FAILED"
    assert "error" in result


def test_fill_form_invalid_fields_type(browser):
    """fill_form with non-dict fields returns FAILED status."""
    result = browser.fill_form({"fields": "invalid_string_format"})
    assert result["status"] == "FAILED"


def test_fill_form_valid(browser):
    """fill_form with valid fields dictionary succeeds."""
    browser.navigate({"url": "https://example.com/contact"})
    result = browser.fill_form({
        "fields": {"name": "Test User", "message": "Hello!"},
        "submit": True
    })
    assert result["status"] == "SUCCESS"
    assert result["submitted"] is True
    assert result["fields_filled"]["name"] == "Test User"


def test_fill_form_no_submit(browser):
    """fill_form with submit=False returns submitted=False."""
    browser.navigate({"url": "https://example.com/contact"})
    result = browser.fill_form({
        "fields": {"search": "query"},
        "submit": False
    })
    assert result["status"] == "SUCCESS"
    assert result["submitted"] is False


# --- Execute Interface ---

def test_execute_dispatch_navigate(browser):
    """execute() correctly dispatches 'navigate' capability."""
    result = browser.execute("navigate", _ctx("navigate", {"url": "https://example.com"}))
    assert result["status"] == "SUCCESS"


def test_execute_dispatch_extract_content(browser):
    """execute() correctly dispatches 'extract_content' capability."""
    browser.navigate({"url": "https://example.com"})
    result = browser.execute("extract_content", _ctx("extract_content", {"selector": "p"}))
    assert result["status"] == "SUCCESS"


def test_execute_dispatch_click_element(browser):
    """execute() correctly dispatches 'click_element' capability."""
    browser.navigate({"url": "https://example.com"})
    result = browser.execute("click_element", _ctx("click_element", {"element": "Docs"}))
    assert result["status"] == "SUCCESS"


def test_execute_dispatch_fill_form(browser):
    """execute() correctly dispatches 'fill_form' capability."""
    browser.navigate({"url": "https://example.com"})
    result = browser.execute("fill_form", _ctx("fill_form", {"fields": {"q": "search"}}))
    assert result["status"] == "SUCCESS"


def test_execute_unknown_capability_raises(browser):
    """execute() with unknown capability raises NotImplementedError."""
    with pytest.raises(NotImplementedError):
        browser.execute("non_existent_cap", _ctx("non_existent_cap", {}))
