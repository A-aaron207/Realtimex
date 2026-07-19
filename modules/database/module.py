"""
Database Module entry point.

Universal database interface with pluggable backend adapters.

Supported backends: sqlite (primary), postgresql, mysql
Future backends:    mongodb, redis, duckdb, chromadb, milvus

Architecture:
    Module  ──►  Adapter Registry  ──►  Backend Adapter
                                             │
                                     SQLiteAdapter
                                     PostgreSQLAdapter
                                     MySQLAdapter

One consistent public API. Backend adapters handle all implementation
differences. All operations return ExecutionResult objects.
"""

from __future__ import annotations

import threading
from typing import Any

from loader.module_base import ModuleEntryPoint
from modules.database.result import ExecutionResult
from modules.database.adapters.sqlite_adapter import SQLiteAdapter
from modules.database.adapters.postgres_adapter import PostgreSQLAdapter
from modules.database.adapters.mysql_adapter import MySQLAdapter

_ADAPTER_REGISTRY: dict[str, type] = {
    "sqlite": SQLiteAdapter,
    "postgresql": PostgreSQLAdapter,
    "postgres": PostgreSQLAdapter,   # alias
    "mysql": MySQLAdapter,
}

# Destructive capabilities that require explicit permission acknowledgement.
_DESTRUCTIVE = {"delete_record", "backup_database", "restore_database", "create_database"}


class Module(ModuleEntryPoint):
    """Entry point for the Database Module."""

    module_id = "database"
    capabilities = [
        "connect_database",
        "disconnect_database",
        "execute_query",
        "create_database",
        "create_table",
        "insert_record",
        "update_record",
        "delete_record",
        "select_records",
        "list_databases",
        "list_tables",
        "transaction",
        "backup_database",
        "restore_database",
    ]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Connection pool: connection_id -> adapter instance
        self._pool: dict[str, Any] = {}
        # Default connection id used when none is specified
        self._default_conn: str | None = None

    def describe(self) -> str:
        return (
            "Universal database interface supporting SQLite, PostgreSQL, and MySQL "
            "via pluggable adapters. One consistent API across all backends."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_adapter(self, input_data: dict[str, Any]) -> tuple[Any | None, ExecutionResult | None]:
        """Resolve the adapter for this call. Returns (adapter, None) or (None, error_result)."""
        conn_id = input_data.get("connection_id") or self._default_conn
        if conn_id is None or conn_id not in self._pool:
            return None, ExecutionResult.failure(
                "No active database connection. Call connect_database first.",
            ).to_dict()
        return self._pool[conn_id], None

    def _result(self, r: ExecutionResult) -> dict[str, Any]:
        return r.to_dict()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect_database(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Open a new database connection and register it in the pool."""
        backend = (input_data.get("backend") or "sqlite").lower()
        connection_id = input_data.get("connection_id") or f"{backend}_default"

        adapter_cls = _ADAPTER_REGISTRY.get(backend)
        if adapter_cls is None:
            return self._result(ExecutionResult.failure(
                f"Unknown backend '{backend}'. Supported: {list(_ADAPTER_REGISTRY.keys())}"
            ))

        adapter = adapter_cls()
        result = adapter.connect(input_data)

        if result.status == "SUCCESS":
            with self._lock:
                self._pool[connection_id] = adapter
                if self._default_conn is None:
                    self._default_conn = connection_id
            result.metadata["connection_id"] = connection_id

        return self._result(result)

    def disconnect_database(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Close a connection and remove it from the pool."""
        conn_id = input_data.get("connection_id") or self._default_conn
        if conn_id is None or conn_id not in self._pool:
            return self._result(ExecutionResult.failure("Connection not found."))

        adapter = self._pool[conn_id]
        result = adapter.disconnect()

        with self._lock:
            self._pool.pop(conn_id, None)
            if self._default_conn == conn_id:
                self._default_conn = next(iter(self._pool), None)

        result.metadata["connection_id"] = conn_id
        return self._result(result)

    # ------------------------------------------------------------------
    # Capability dispatch
    # ------------------------------------------------------------------

    def execute_query(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        sql = input_data.get("sql") or input_data.get("query", "")
        params = input_data.get("params")
        return self._result(adapter.execute_query(sql, params))

    def create_database(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        name = input_data.get("name") or input_data.get("database")
        if not name:
            return self._result(ExecutionResult.failure("No database name provided."))
        return self._result(adapter.create_database(name))

    def create_table(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        table = input_data.get("table")
        columns = input_data.get("columns", [])
        if_not_exists = input_data.get("if_not_exists", True)
        if not table or not columns:
            return self._result(ExecutionResult.failure("Both 'table' and 'columns' are required."))
        return self._result(adapter.create_table(table, columns, if_not_exists))

    def insert_record(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        table = input_data.get("table")
        data = input_data.get("data") or input_data.get("record", {})
        if not table or not data:
            return self._result(ExecutionResult.failure("Both 'table' and 'data' are required."))
        return self._result(adapter.insert_record(table, data))

    def update_record(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        table = input_data.get("table")
        data = input_data.get("data", {})
        where = input_data.get("where", {})
        if not table:
            return self._result(ExecutionResult.failure("'table' is required."))
        return self._result(adapter.update_record(table, data, where))

    def delete_record(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        table = input_data.get("table")
        where = input_data.get("where", {})
        if not table:
            return self._result(ExecutionResult.failure("'table' is required."))
        return self._result(adapter.delete_record(table, where))

    def select_records(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        table = input_data.get("table")
        if not table:
            return self._result(ExecutionResult.failure("'table' is required."))
        return self._result(adapter.select_records(
            table,
            columns=input_data.get("columns"),
            where=input_data.get("where"),
            order_by=input_data.get("order_by"),
            limit=input_data.get("limit"),
            offset=input_data.get("offset"),
        ))

    def list_databases(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        return self._result(adapter.list_databases())

    def list_tables(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        return self._result(adapter.list_tables())

    def transaction(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        statements = input_data.get("statements", [])
        if not statements:
            return self._result(ExecutionResult.failure("No statements provided for transaction."))
        return self._result(adapter.transaction(statements))

    def backup_database(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        destination = input_data.get("destination") or input_data.get("path")
        if not destination:
            return self._result(ExecutionResult.failure("'destination' path is required."))
        return self._result(adapter.backup(destination))

    def restore_database(self, input_data: dict[str, Any]) -> dict[str, Any]:
        adapter, err = self._get_adapter(input_data)
        if err:
            return err
        source = input_data.get("source") or input_data.get("path")
        if not source:
            return self._result(ExecutionResult.failure("'source' path is required."))
        return self._result(adapter.restore(source))

    # ------------------------------------------------------------------
    # Standardized execute entry point
    # ------------------------------------------------------------------

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        dispatch = {
            "connect_database": self.connect_database,
            "disconnect_database": self.disconnect_database,
            "execute_query": self.execute_query,
            "create_database": self.create_database,
            "create_table": self.create_table,
            "insert_record": self.insert_record,
            "update_record": self.update_record,
            "delete_record": self.delete_record,
            "select_records": self.select_records,
            "list_databases": self.list_databases,
            "list_tables": self.list_tables,
            "transaction": self.transaction,
            "backup_database": self.backup_database,
            "restore_database": self.restore_database,
        }
        if capability not in dispatch:
            raise NotImplementedError(f"Capability '{capability}' not supported by Database Module.")
        return dispatch[capability](context.input)
