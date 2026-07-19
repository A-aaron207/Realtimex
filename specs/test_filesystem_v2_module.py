"""
Tests for the Filesystem v2 Module.
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
def fsv2(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "filesystem_v2" in module_loader._loaded_modules
    return module_loader._loaded_modules["filesystem_v2"].instance


def _ctx(capability: str, input_data: dict) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_fsv2",
        workflow_id="test_fsv2_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


def test_filesystem_v2_loaded(fsv2):
    for cap in ["read_file", "write_file", "list_directory", "search_files", "copy", "delete"]:
        assert cap in fsv2.capabilities


def test_write_and_read(fsv2, tmp_path):
    target = str(tmp_path / "hello.txt")

    write_res = fsv2.execute("write_file", _ctx("write_file", {
        "path": target,
        "content": "Hello, Realtimex Filesystem v2!\n"
    }))
    assert write_res["status"] == "SUCCESS"
    assert write_res["bytes_written"] > 0

    read_res = fsv2.execute("read_file", _ctx("read_file", {"path": target}))
    assert read_res["status"] == "SUCCESS"
    assert "Realtimex" in read_res["content"]


def test_append_mode(fsv2, tmp_path):
    target = str(tmp_path / "log.txt")
    fsv2.execute("write_file", _ctx("write_file", {"path": target, "content": "line1\n"}))
    fsv2.execute("write_file", _ctx("write_file", {"path": target, "content": "line2\n", "mode": "append"}))

    read_res = fsv2.execute("read_file", _ctx("read_file", {"path": target}))
    assert "line1" in read_res["content"]
    assert "line2" in read_res["content"]


def test_list_directory(fsv2, tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.py").write_text("b")

    res = fsv2.execute("list_directory", _ctx("list_directory", {"path": str(tmp_path)}))
    assert res["status"] == "SUCCESS"
    names = [e["name"] for e in res["entries"]]
    assert "a.txt" in names
    assert "b.py" in names


def test_search_files_by_name(fsv2, tmp_path):
    (tmp_path / "module.py").write_text("x = 1")
    (tmp_path / "config.json").write_text("{}")

    res = fsv2.execute("search_files", _ctx("search_files", {
        "root": str(tmp_path),
        "name_pattern": "*.py"
    }))
    assert res["status"] == "SUCCESS"
    paths = [m["path"] for m in res["matches"]]
    assert any("module.py" in p for p in paths)
    assert not any("config.json" in p for p in paths)


def test_search_files_by_content(fsv2, tmp_path):
    (tmp_path / "source.py").write_text("def hello_realtimex():\n    pass\n")

    res = fsv2.execute("search_files", _ctx("search_files", {
        "root": str(tmp_path),
        "content_query": "hello_realtimex"
    }))
    assert res["status"] == "SUCCESS"
    assert res["match_count"] >= 1
    assert res["matches"][0]["hits"][0][1].strip().startswith("def hello_realtimex")


def test_copy_and_delete(fsv2, tmp_path):
    src = str(tmp_path / "original.txt")
    dst = str(tmp_path / "copy.txt")
    Path(src).write_text("copy me")

    copy_res = fsv2.execute("copy", _ctx("copy", {"src": src, "dst": dst}))
    assert copy_res["status"] == "SUCCESS"
    assert Path(dst).exists()

    del_res = fsv2.execute("delete", _ctx("delete", {"path": dst}))
    assert del_res["status"] == "SUCCESS"
    assert not Path(dst).exists()


def test_read_missing_file(fsv2):
    res = fsv2.execute("read_file", _ctx("read_file", {"path": "/tmp/no_such_file_rtx.txt"}))
    assert res["status"] == "FAILED"
    assert "not found" in res["error"]
