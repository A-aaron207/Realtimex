"""
Regression tests for Architecture Audit Finding #3:
Elimination of global static state and singleton anti-pattern in ServiceRegistry.
Verifies thread-safe, context-local isolation and multi-instance independence.
"""

from __future__ import annotations

import concurrent.futures
import threading

import pytest

from services.base import SimpleService
from services.registry import DuplicateServiceError, ServiceNotFoundError, ServiceRegistry


def test_independent_instances():
    """Two ServiceRegistry instances must not share or pollute each other's state."""
    reg1 = ServiceRegistry(set_as_current=False)
    reg2 = ServiceRegistry(set_as_current=False)

    svc1 = SimpleService("test_service", {"id": 1})
    svc2 = SimpleService("test_service", {"id": 2})

    reg1.register(svc1)
    reg2.register(svc2)

    assert reg1.get("test_service").metadata["id"] == 1
    assert reg2.get("test_service").metadata["id"] == 2
    assert len(reg1) == 1
    assert len(reg2) == 1


def test_context_manager_scoping():
    """ServiceRegistry.as_current() scopes get_instance() to the context block."""
    reg1 = ServiceRegistry(set_as_current=False)
    reg2 = ServiceRegistry(set_as_current=False)

    reg1.register(SimpleService("svc", {"val": "alpha"}))
    reg2.register(SimpleService("svc", {"val": "beta"}))

    with reg1.as_current():
        active = ServiceRegistry.get_instance()
        assert active is reg1
        assert active.get("svc").metadata["val"] == "alpha"

    with reg2.as_current():
        active = ServiceRegistry.get_instance()
        assert active is reg2
        assert active.get("svc").metadata["val"] == "beta"


def test_concurrent_threads_context_isolation():
    """Concurrent threads running different registries must never cross-talk."""
    reg_a = ServiceRegistry(set_as_current=False)
    reg_b = ServiceRegistry(set_as_current=False)

    reg_a.register(SimpleService("token", {"owner": "thread_a"}))
    reg_b.register(SimpleService("token", {"owner": "thread_b"}))

    results = {}
    barrier = threading.Barrier(2)

    def worker_a():
        with reg_a.as_current():
            barrier.wait()
            # Repeatedly sample get_instance()
            for _ in range(100):
                active = ServiceRegistry.get_instance()
                val = active.get("token").metadata["owner"]
                if val != "thread_a":
                    results["a_error"] = val
                    return
            results["a"] = "success"

    def worker_b():
        with reg_b.as_current():
            barrier.wait()
            # Repeatedly sample get_instance()
            for _ in range(100):
                active = ServiceRegistry.get_instance()
                val = active.get("token").metadata["owner"]
                if val != "thread_b":
                    results["b_error"] = val
                    return
            results["b"] = "success"

    t1 = threading.Thread(target=worker_a)
    t2 = threading.Thread(target=worker_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results.get("a") == "success", f"Thread A saw unexpected registry: {results.get('a_error')}"
    assert results.get("b") == "success", f"Thread B saw unexpected registry: {results.get('b_error')}"


def test_fallback_singleton_compatibility():
    """Legacy singleton _instance fallback functions properly when no context is active."""
    ServiceRegistry.reset()

    # When none set, raise RuntimeError
    with pytest.raises(RuntimeError, match="ServiceRegistry has not been initialized"):
        ServiceRegistry.get_instance()

    legacy_reg = ServiceRegistry(set_as_current=False)
    ServiceRegistry._instance = legacy_reg
    assert ServiceRegistry.get_instance() is legacy_reg

    # Context override takes priority over legacy singleton
    isolated_reg = ServiceRegistry(set_as_current=False)
    with isolated_reg.as_current():
        assert ServiceRegistry.get_instance() is isolated_reg

    # Reverts back to legacy singleton after context exit
    assert ServiceRegistry.get_instance() is legacy_reg

    ServiceRegistry.reset()
