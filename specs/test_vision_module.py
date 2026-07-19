"""
Tests for the Vision Module.
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

# Tiny 1×1 white PNG — valid image file usable without Pillow.
_MINIMAL_PNG = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk length + type
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # width=1, height=1
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bit depth, color type, ...
    0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
    0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
    0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
    0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
    0x44, 0xAE, 0x42, 0x60, 0x82
])


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
def vision(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "vision" in module_loader._loaded_modules
    return module_loader._loaded_modules["vision"].instance


@pytest.fixture(scope="module")
def sample_image(tmp_path_factory) -> Path:
    """Write a minimal valid PNG to a temp file for reuse across tests."""
    p = tmp_path_factory.mktemp("imgs") / "sample.png"
    p.write_bytes(_MINIMAL_PNG)
    return p


def _ctx(capability: str, input_data: dict) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_vision",
        workflow_id="test_vision_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


def test_vision_module_loaded(vision):
    for cap in ["analyze_image", "extract_text", "describe_screenshot", "compare_images"]:
        assert cap in vision.capabilities


def test_analyze_image(vision, sample_image):
    result = vision.execute("analyze_image", _ctx("analyze_image", {
        "path": str(sample_image),
        "question": "What colors are present?"
    }))
    assert result["status"] == "SUCCESS"
    assert "analysis" in result
    assert len(result["analysis"]) > 0


def test_extract_text(vision, sample_image):
    result = vision.execute("extract_text", _ctx("extract_text", {
        "path": str(sample_image),
        "language": "en"
    }))
    assert result["status"] == "SUCCESS"
    assert "extracted_text" in result


def test_describe_screenshot(vision, sample_image):
    result = vision.execute("describe_screenshot", _ctx("describe_screenshot", {
        "path": str(sample_image),
        "context": "Realtimex dashboard"
    }))
    assert result["status"] == "SUCCESS"
    assert "ui_description" in result
    assert len(result["ui_description"]) > 0


def test_compare_images(vision, sample_image, tmp_path_factory):
    img_b = tmp_path_factory.mktemp("imgs2") / "sample_b.png"
    img_b.write_bytes(_MINIMAL_PNG)

    result = vision.execute("compare_images", _ctx("compare_images", {
        "path_a": str(sample_image),
        "path_b": str(img_b)
    }))
    assert result["status"] == "SUCCESS"
    assert "comparison" in result
    assert len(result["comparison"]) > 0


def test_missing_image(vision):
    result = vision.execute("analyze_image", _ctx("analyze_image", {
        "path": "/tmp/no_such_image_rtx.png"
    }))
    assert result["status"] == "FAILED"
    assert "not found" in result["error"]
