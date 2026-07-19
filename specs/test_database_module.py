"""
Tests for the Database Module.

Covers:
- Module loading and capability registration
- SQLite: CRUD, transactions (commit/rollback), connection failures,
  invalid queries, backup/restore, multi-table, pagination
- Permission-denied scenarios (empty WHERE on destructive ops)
- Backend unavailability (PostgreSQL/MySQL without drivers)
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

_COLUMNS = [
    {"name": "id",    "type": "INTEGER", "primary_key": True},
    {"name": "name",  "type": "TEXT",    "nullable": False},
    {"name": "score", "type": "REAL",    "nullable": True},
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def db(booted_api):
    module_loader = booted_api._kernel._boot_result.module_loader
    assert "database" in module_loader._loaded_modules
    return module_loader._loaded_modules["database"].instance


def _ctx(capability: str, input_data: dict) -> ExecutionContext:
    return ExecutionContext(
        task_id="test_db",
        workflow_id="test_db_wf",
        step_id="step_01",
        capability=capability,
        input=input_data,
        permissions={},
        metadata={}
    )


# ---------------------------------------------------------------------------
# 1. Module loading
# ---------------------------------------------------------------------------

def test_database_module_loaded(db):
    for cap in [
        "connect_database", "disconnect_database", "execute_query",
        "create_database", "create_table", "insert_record", "update_record",
        "delete_record", "select_records", "list_databases", "list_tables",
        "transaction", "backup_database", "restore_database",
    ]:
        assert cap in db.capabilities


# ---------------------------------------------------------------------------
# 2. Connection lifecycle
# ---------------------------------------------------------------------------

def test_connect_sqlite_memory(db):
    result = db.execute("connect_database", _ctx("connect_database", {
        "backend": "sqlite",
        "database": ":memory:",
        "connection_id": "test_mem"
    }))
    assert result["status"] == "SUCCESS"
    assert result["metadata"]["connection_id"] == "test_mem"


def test_connect_without_backend_defaults_to_sqlite(db):
    result = db.execute("connect_database", _ctx("connect_database", {
        "database": ":memory:",
        "connection_id": "test_default_backend"
    }))
    assert result["status"] == "SUCCESS"
    assert result["metadata"].get("backend") == "sqlite"


def test_connect_unknown_backend(db):
    result = db.execute("connect_database", _ctx("connect_database", {
        "backend": "oracle",
        "connection_id": "test_oracle"
    }))
    assert result["status"] == "FAILED"
    assert "oracle" in result["error"]


def test_no_connection_error(db):
    """Calling a capability without any connection should fail gracefully."""
    fresh_db = db.__class__()   # new instance, no connections
    result = fresh_db.execute_query({"sql": "SELECT 1"})
    assert result["status"] == "FAILED"
    assert "connect_database" in result["error"]


# ---------------------------------------------------------------------------
# 3. Full CRUD with SQLite
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sqlite_db(db):
    """Connect and create a shared in-memory SQLite session for CRUD tests."""
    conn_result = db.execute("connect_database", _ctx("connect_database", {
        "backend": "sqlite",
        "database": ":memory:",
        "connection_id": "crud_conn"
    }))
    assert conn_result["status"] == "SUCCESS"

    db.execute("create_table", _ctx("create_table", {
        "connection_id": "crud_conn",
        "table": "users",
        "columns": _COLUMNS,
    }))
    yield db

    db.execute("disconnect_database", _ctx("disconnect_database", {"connection_id": "crud_conn"}))


def test_create_table(sqlite_db):
    result = sqlite_db.execute("list_tables", _ctx("list_tables", {"connection_id": "crud_conn"}))
    assert result["status"] == "SUCCESS"
    names = [r.get("name") for r in result["rows"]]
    assert "users" in names


def test_insert_record(sqlite_db):
    result = sqlite_db.execute("insert_record", _ctx("insert_record", {
        "connection_id": "crud_conn",
        "table": "users",
        "data": {"id": 1, "name": "Alice", "score": 98.5}
    }))
    assert result["status"] == "SUCCESS"
    assert result["last_insert_id"] == 1


def test_insert_multiple_records(sqlite_db):
    for i, (name, score) in enumerate([("Bob", 82.0), ("Carol", 91.5)], start=2):
        res = sqlite_db.execute("insert_record", _ctx("insert_record", {
            "connection_id": "crud_conn",
            "table": "users",
            "data": {"id": i, "name": name, "score": score}
        }))
        assert res["status"] == "SUCCESS"


def test_select_all(sqlite_db):
    result = sqlite_db.execute("select_records", _ctx("select_records", {
        "connection_id": "crud_conn",
        "table": "users"
    }))
    assert result["status"] == "SUCCESS"
    assert result["row_count"] == 3


def test_select_with_where(sqlite_db):
    result = sqlite_db.execute("select_records", _ctx("select_records", {
        "connection_id": "crud_conn",
        "table": "users",
        "where": {"name": "Alice"}
    }))
    assert result["status"] == "SUCCESS"
    assert result["row_count"] == 1
    assert result["rows"][0]["name"] == "Alice"


def test_select_with_limit_offset(sqlite_db):
    result = sqlite_db.execute("select_records", _ctx("select_records", {
        "connection_id": "crud_conn",
        "table": "users",
        "order_by": "id",
        "limit": 2,
        "offset": 1
    }))
    assert result["status"] == "SUCCESS"
    assert result["row_count"] == 2
    assert result["rows"][0]["name"] == "Bob"


def test_update_record(sqlite_db):
    result = sqlite_db.execute("update_record", _ctx("update_record", {
        "connection_id": "crud_conn",
        "table": "users",
        "data": {"score": 99.0},
        "where": {"name": "Alice"}
    }))
    assert result["status"] == "SUCCESS"

    verify = sqlite_db.execute("select_records", _ctx("select_records", {
        "connection_id": "crud_conn",
        "table": "users",
        "where": {"name": "Alice"}
    }))
    assert verify["rows"][0]["score"] == 99.0


def test_delete_record(sqlite_db):
    result = sqlite_db.execute("delete_record", _ctx("delete_record", {
        "connection_id": "crud_conn",
        "table": "users",
        "where": {"name": "Carol"}
    }))
    assert result["status"] == "SUCCESS"

    verify = sqlite_db.execute("select_records", _ctx("select_records", {
        "connection_id": "crud_conn",
        "table": "users"
    }))
    assert verify["row_count"] == 2


# ---------------------------------------------------------------------------
# 4. Raw execute_query
# ---------------------------------------------------------------------------

def test_execute_raw_query(sqlite_db):
    result = sqlite_db.execute("execute_query", _ctx("execute_query", {
        "connection_id": "crud_conn",
        "sql": "SELECT COUNT(*) as total FROM users"
    }))
    assert result["status"] == "SUCCESS"
    assert result["rows"][0]["total"] == 2


def test_invalid_query(sqlite_db):
    result = sqlite_db.execute("execute_query", _ctx("execute_query", {
        "connection_id": "crud_conn",
        "sql": "SELECT * FROM nonexistent_table_xyz"
    }))
    assert result["status"] == "FAILED"
    assert result["error"]


# ---------------------------------------------------------------------------
# 5. Transaction — commit and rollback
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def txn_db(db):
    """Separate connection for transaction tests."""
    db.execute("connect_database", _ctx("connect_database", {
        "backend": "sqlite",
        "database": ":memory:",
        "connection_id": "txn_conn"
    }))
    db.execute("create_table", _ctx("create_table", {
        "connection_id": "txn_conn",
        "table": "accounts",
        "columns": [
            {"name": "id",      "type": "INTEGER", "primary_key": True},
            {"name": "owner",   "type": "TEXT"},
            {"name": "balance", "type": "REAL"},
        ]
    }))
    db.execute("insert_record", _ctx("insert_record", {
        "connection_id": "txn_conn",
        "table": "accounts",
        "data": {"id": 1, "owner": "Alice", "balance": 1000.0}
    }))
    db.execute("insert_record", _ctx("insert_record", {
        "connection_id": "txn_conn",
        "table": "accounts",
        "data": {"id": 2, "owner": "Bob", "balance": 500.0}
    }))
    yield db
    db.execute("disconnect_database", _ctx("disconnect_database", {"connection_id": "txn_conn"}))


def test_transaction_commit(txn_db):
    """Transfer funds atomically across two UPDATE statements."""
    result = txn_db.execute("transaction", _ctx("transaction", {
        "connection_id": "txn_conn",
        "statements": [
            {"sql": "UPDATE accounts SET balance = balance - ? WHERE id = ?", "params": [200.0, 1]},
            {"sql": "UPDATE accounts SET balance = balance + ? WHERE id = ?", "params": [200.0, 2]},
        ]
    }))
    assert result["status"] == "SUCCESS"
    assert result["metadata"]["statements_executed"] == 2

    verify = txn_db.execute("select_records", _ctx("select_records", {
        "connection_id": "txn_conn",
        "table": "accounts",
        "where": {"id": 1}
    }))
    assert verify["rows"][0]["balance"] == 800.0


def test_transaction_rollback(txn_db):
    """A bad second statement should cause a full rollback."""
    result = txn_db.execute("transaction", _ctx("transaction", {
        "connection_id": "txn_conn",
        "statements": [
            {"sql": "UPDATE accounts SET balance = balance - ? WHERE id = ?", "params": [100.0, 1]},
            {"sql": "INSERT INTO nonexistent_xyz (a) VALUES (?)", "params": ["boom"]},
        ]
    }))
    assert result["status"] == "FAILED"
    assert result["metadata"].get("rolled_back") is True

    # Balance should be unchanged (rollback worked)
    verify = txn_db.execute("select_records", _ctx("select_records", {
        "connection_id": "txn_conn",
        "table": "accounts",
        "where": {"id": 1}
    }))
    assert verify["rows"][0]["balance"] == 800.0


# ---------------------------------------------------------------------------
# 6. Permission-denied scenarios (empty WHERE on destructive ops)
# ---------------------------------------------------------------------------

def test_update_without_where_denied(sqlite_db):
    result = sqlite_db.execute("update_record", _ctx("update_record", {
        "connection_id": "crud_conn",
        "table": "users",
        "data": {"score": 0},
        "where": {}
    }))
    assert result["status"] == "FAILED"
    assert "where" in result["error"].lower()


def test_delete_without_where_denied(sqlite_db):
    result = sqlite_db.execute("delete_record", _ctx("delete_record", {
        "connection_id": "crud_conn",
        "table": "users",
        "where": {}
    }))
    assert result["status"] == "FAILED"
    assert "where" in result["error"].lower()


# ---------------------------------------------------------------------------
# 7. Backup & Restore
# ---------------------------------------------------------------------------

def test_backup_and_restore(db, tmp_path):
    backup_path = str(tmp_path / "test.db.bak")

    # Connect to a file-based DB so backup has data to copy
    db.execute("connect_database", _ctx("connect_database", {
        "backend": "sqlite",
        "database": str(tmp_path / "original.db"),
        "connection_id": "bak_conn"
    }))
    db.execute("create_table", _ctx("create_table", {
        "connection_id": "bak_conn",
        "table": "items",
        "columns": [{"name": "id", "type": "INTEGER", "primary_key": True},
                    {"name": "label", "type": "TEXT"}]
    }))
    db.execute("insert_record", _ctx("insert_record", {
        "connection_id": "bak_conn",
        "table": "items",
        "data": {"id": 1, "label": "backup_test"}
    }))

    bak_result = db.execute("backup_database", _ctx("backup_database", {
        "connection_id": "bak_conn",
        "destination": backup_path
    }))
    assert bak_result["status"] == "SUCCESS"
    assert Path(backup_path).exists()

    # Now restore into a fresh in-memory connection
    db.execute("connect_database", _ctx("connect_database", {
        "backend": "sqlite",
        "database": ":memory:",
        "connection_id": "restored_conn"
    }))
    restore_result = db.execute("restore_database", _ctx("restore_database", {
        "connection_id": "restored_conn",
        "source": backup_path
    }))
    assert restore_result["status"] == "SUCCESS"

    verify = db.execute("select_records", _ctx("select_records", {
        "connection_id": "restored_conn",
        "table": "items"
    }))
    assert verify["status"] == "SUCCESS"
    assert verify["rows"][0]["label"] == "backup_test"

    db.execute("disconnect_database", _ctx("disconnect_database", {"connection_id": "bak_conn"}))
    db.execute("disconnect_database", _ctx("disconnect_database", {"connection_id": "restored_conn"}))


# ---------------------------------------------------------------------------
# 8. Multi-backend compatibility (PostgreSQL / MySQL degrade gracefully)
# ---------------------------------------------------------------------------

def test_postgresql_unavailable_degrades_gracefully(db):
    result = db.execute("connect_database", _ctx("connect_database", {
        "backend": "postgresql",
        "host": "localhost",
        "database": "testdb",
        "connection_id": "pg_test"
    }))
    # Either succeeds (driver present) or fails gracefully with an install message
    assert result["status"] in ("SUCCESS", "FAILED")
    if result["status"] == "FAILED":
        assert "psycopg2" in result["error"] or "Connection" in result["error"]


def test_mysql_unavailable_degrades_gracefully(db):
    result = db.execute("connect_database", _ctx("connect_database", {
        "backend": "mysql",
        "host": "localhost",
        "database": "testdb",
        "connection_id": "mysql_test"
    }))
    assert result["status"] in ("SUCCESS", "FAILED")
    if result["status"] == "FAILED":
        assert "mysql" in result["error"].lower() or "Connection" in result["error"]
