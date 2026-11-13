"""
Tests for the Research Module.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from kernel.api import KernelAPI
from services.registry import ServiceRegistry
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


def test_research_module_loaded(booted_api):
    """Verify that the research module is successfully discovered and loaded."""
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "research" in module_loader._loaded_modules
    
    loaded_module = module_loader._loaded_modules["research"]
    module_instance = loaded_module.instance
    assert "research_topic" in module_instance.capabilities
    assert "retrieve_content" in module_instance.capabilities
    assert "synthesize_findings" in module_instance.capabilities


def test_research_topic(booted_api):
    """Verify the research_topic capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["research"].instance

    context = ExecutionContext(
        task_id="test_research_task",
        workflow_id="test_research_workflow",
        step_id="step_01",
        capability="research_topic",
        input={"topic": "Quantum Computing"},
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("research_topic", context)
    assert result["status"] == "SUCCESS"
    assert "research_outline" in result
    # Accept real content (online) or ⚠ error message (offline / rate-limited)
    outline = result["research_outline"]
    assert "Quantum" in outline or "⚠" in outline or "unavailable" in outline.lower(), f"Unexpected outline: {outline}"
    assert len(result["suggested_queries"]) > 0


def test_retrieve_content(booted_api):
    """Verify the retrieve_content capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["research"].instance

    context = ExecutionContext(
        task_id="test_retrieval_task",
        workflow_id="test_retrieval_workflow",
        step_id="step_02",
        capability="retrieve_content",
        input={"source": "https://arxiv.org/abs/2101.12345"},
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("retrieve_content", context)
    assert result["status"] == "SUCCESS"
    assert "extracted_content" in result
    content = result["extracted_content"]
    # Accept real content (online) or ⚠ error message (offline / rate-limited)
    assert "retriev" in content.lower() or "⚠" in content or "unavailable" in content.lower(), f"Unexpected content: {content}"


def test_synthesize_findings(booted_api):
    """Verify the synthesize_findings capability."""
    module_loader = booted_api._kernel._boot_result.module_loader
    module_instance = module_loader._loaded_modules["research"].instance

    context = ExecutionContext(
        task_id="test_synthesis_task",
        workflow_id="test_synthesis_workflow",
        step_id="step_03",
        capability="synthesize_findings",
        input={
            "findings": [
                "Finding 1: Qubits must remain coherent.",
                "Finding 2: Error correction is vital."
            ]
        },
        permissions={},
        metadata={}
    )
    
    result = module_instance.execute("synthesize_findings", context)
    assert result["status"] == "SUCCESS"
    assert "synthesis" in result
    assert "citations" in result
    assert len(result["citations"]) > 0
