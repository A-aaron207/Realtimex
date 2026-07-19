"""
MySQL backend adapter for the Database Module.

Requires: mysql-connector-python  (pip install mysql-connector-python)

Degrades gracefully when the driver is not installed.
"""

from __future__ import annotations

import time
from typing import Any

from modules.database.adapters.base import BaseAdapter
from modules.database.result import ExecutionResult

try:
    import mysql.connector
    import mysql.connector.cursor
    _MYSQL_AVAILABLE = True
except ImportError:
    _MYSQL_AVAILABLE = False

_INSTALL_MSG = (
    "mysql-connector-python is not installed. "
    "Run: pip install mysql-connector-python"
)


class MySQLAdapter(BaseAdapter):
    """MySQL implementation using mysql-connector-python."""

    backend_name = "mysql"

    def __init__(self) -> None:
        self._conn: Any = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and self._conn.is_connected()

    def _unavailable(self) -> ExecutionResult:
        return ExecutionResult.failure(_INSTALL_MSG, backend="mysql")

    def _cursor(self) -> Any:
        if not self._conn:
            raise RuntimeError("Not connected.")
        return self._conn.cursor(dictionary=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self, config: dict[str, Any]) -> ExecutionResult:
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        try:
            self._conn = mysql.connector.connect(
                host=config.get("host", "localhost"),
                port=int(config.get("port", 3306)),
                database=config.get("database"),
                user=config.get("user", "root"),
                password=config.get("password", ""),
            )
            return ExecutionResult.success(
                backend="mysql",
                host=config.get("host"),
                database=config.get("database"),
            )
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="mysql")

    def disconnect(self) -> ExecutionResult:
        if self._conn and self._conn.is_connected():
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        return ExecutionResult.success(backend="mysql")

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def create_database(self, name: str) -> ExecutionResult:
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        return self.execute_query(f"CREATE DATABASE IF NOT EXISTS {name}")

    def create_table(self, table, columns, if_not_exists=True):
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        parts = []
        for col in columns:
            col_def = f"{col['name']} {col['type'].upper()}"
            if col.get("primary_key"):
                col_def += " PRIMARY KEY"
            if col.get("unique"):
                col_def += " UNIQUE"
            if not col.get("nullable", True):
                col_def += " NOT NULL"
            if "default" in col:
                col_def += f" DEFAULT {col['default']}"
            parts.append(col_def)
        exists = "IF NOT EXISTS" if if_not_exists else ""
        sql = f"CREATE TABLE {exists} {table} ({', '.join(parts)})"
        return self.execute_query(sql)

    # ------------------------------------------------------------------
    # DML
    # ------------------------------------------------------------------

    def insert_record(self, table: str, data: dict[str, Any]) -> ExecutionResult:
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        return self.execute_query(sql, list(data.values()))

    def update_record(self, table, data, where):
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        if not where:
            return ExecutionResult.failure("update_record requires a non-empty where clause.", backend="mysql")
        set_clause = ", ".join(f"{k} = %s" for k in data)
        where_clause = " AND ".join(f"{k} = %s" for k in where)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        return self.execute_query(sql, list(data.values()) + list(where.values()))

    def delete_record(self, table, where):
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        if not where:
            return ExecutionResult.failure("delete_record requires a non-empty where clause.", backend="mysql")
        where_clause = " AND ".join(f"{k} = %s" for k in where)
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        return self.execute_query(sql, list(where.values()))

    def select_records(self, table, columns=None, where=None, order_by=None, limit=None, offset=None):
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        col_str = ", ".join(columns) if columns else "*"
        sql = f"SELECT {col_str} FROM {table}"
        params: list[Any] = []
        if where:
            where_clause = " AND ".join(f"{k} = %s" for k in where)
            sql += f" WHERE {where_clause}"
            params.extend(where.values())
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset is not None:
            sql += f" OFFSET {int(offset)}"
        return self.execute_query(sql, params)

    # ------------------------------------------------------------------
    # Raw query
    # ------------------------------------------------------------------

    def execute_query(self, sql: str, params=None) -> ExecutionResult:
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        t0 = time.monotonic()
        try:
            cur = self._cursor()
            cur.execute(sql, params or [])
            self._conn.commit()
            rows = cur.fetchall() or []
            return ExecutionResult.success(
                rows=list(rows),
                row_count=cur.rowcount if cur.rowcount >= 0 else len(rows),
                last_insert_id=cur.lastrowid,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                backend="mysql",
            )
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return ExecutionResult.failure(
                str(exc),
                backend="mysql",
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def transaction(self, statements: list[dict[str, Any]]) -> ExecutionResult:
        if not _MYSQL_AVAILABLE:
            return self._unavailable()
        t0 = time.monotonic()
        try:
            self._conn.start_transaction()
            total = 0
            for stmt in statements:
                cur = self._cursor()
                cur.execute(stmt.get("sql", ""), stmt.get("params") or [])
                if cur.rowcount > 0:
                    total += cur.rowcount
            self._conn.commit()
            return ExecutionResult.success(
                row_count=total,
                statements_executed=len(statements),
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                backend="mysql",
            )
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return ExecutionResult.failure(str(exc), backend="mysql", rolled_back=True)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_databases(self) -> ExecutionResult:
        return self.execute_query("SHOW DATABASES")

    def list_tables(self) -> ExecutionResult:
        return self.execute_query("SHOW TABLES")

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------

    def backup(self, destination: str) -> ExecutionResult:
        return ExecutionResult.failure(
            "MySQL backup via mysqldump is not yet implemented in this adapter version.",
            backend="mysql",
        )

    def restore(self, source: str) -> ExecutionResult:
        return ExecutionResult.failure(
            "MySQL restore is not yet implemented in this adapter version.",
            backend="mysql",
        )
