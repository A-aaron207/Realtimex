"""
SQLite backend adapter for the Database Module.

Uses the Python stdlib ``sqlite3`` module — no external dependencies.
All queries are fully parameterized.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from typing import Any

from modules.database.adapters.base import BaseAdapter
from modules.database.result import ExecutionResult


class SQLiteAdapter(BaseAdapter):
    """Full SQLite implementation of the database adapter interface."""

    backend_name = "sqlite"

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._db_path: str = ""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cursor(self) -> sqlite3.Cursor:
        if not self._conn:
            raise RuntimeError("Not connected. Call connect_database first.")
        return self._conn.cursor()

    def _rows_to_dicts(self, cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        if cursor.description is None:
            return []
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def _build_where(
        self, where: dict[str, Any]
    ) -> tuple[str, list[Any]]:
        """Build a parameterized WHERE clause from a dict."""
        if not where:
            return "", []
        clause = " AND ".join(f"{k} = ?" for k in where)
        return f"WHERE {clause}", list(where.values())

    def _build_set(
        self, data: dict[str, Any]
    ) -> tuple[str, list[Any]]:
        """Build a parameterized SET clause from a dict."""
        clause = ", ".join(f"{k} = ?" for k in data)
        return clause, list(data.values())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    def connect(self, config: dict[str, Any]) -> ExecutionResult:
        path = config.get("database") or config.get("path", ":memory:")
        try:
            if path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._db_path = path
            return ExecutionResult.success(backend="sqlite", path=path)
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="sqlite")

    def disconnect(self) -> ExecutionResult:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        return ExecutionResult.success(backend="sqlite")

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def create_database(self, name: str) -> ExecutionResult:
        """For SQLite, 'creating a database' means opening a new file."""
        try:
            path = os.path.abspath(f"{name}.db")
            conn = sqlite3.connect(path)
            conn.close()
            return ExecutionResult.success(
                database=name, path=path, backend="sqlite"
            )
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="sqlite")

    def create_table(
        self,
        table: str,
        columns: list[dict[str, str]],
        if_not_exists: bool = True,
    ) -> ExecutionResult:
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
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        return self.execute_query(sql, list(data.values()))

    def update_record(
        self, table: str, data: dict[str, Any], where: dict[str, Any]
    ) -> ExecutionResult:
        if not where:
            return ExecutionResult.failure(
                "update_record requires a non-empty where clause to prevent full-table overwrites.",
                backend="sqlite",
            )
        set_clause, set_params = self._build_set(data)
        where_clause, where_params = self._build_where(where)
        sql = f"UPDATE {table} SET {set_clause} {where_clause}"
        return self.execute_query(sql, set_params + where_params)

    def delete_record(self, table: str, where: dict[str, Any]) -> ExecutionResult:
        if not where:
            return ExecutionResult.failure(
                "delete_record requires a non-empty where clause to prevent full-table deletes.",
                backend="sqlite",
            )
        where_clause, where_params = self._build_where(where)
        sql = f"DELETE FROM {table} {where_clause}"
        return self.execute_query(sql, where_params)

    def select_records(
        self,
        table: str,
        columns: list[str] | None = None,
        where: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ExecutionResult:
        col_str = ", ".join(columns) if columns else "*"
        sql = f"SELECT {col_str} FROM {table}"
        params: list[Any] = []

        if where:
            where_clause, where_params = self._build_where(where)
            sql += f" {where_clause}"
            params.extend(where_params)
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

    def execute_query(
        self,
        sql: str,
        params: list[Any] | tuple[Any, ...] | None = None,
    ) -> ExecutionResult:
        t0 = time.monotonic()
        try:
            cur = self._cursor()
            cur.execute(sql, params or [])
            self._conn.commit()  # type: ignore[union-attr]
            rows = self._rows_to_dicts(cur)
            return ExecutionResult.success(
                rows=rows,
                row_count=cur.rowcount if cur.rowcount >= 0 else len(rows),
                last_insert_id=cur.lastrowid,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                backend="sqlite",
            )
        except Exception as exc:
            return ExecutionResult.failure(
                str(exc),
                backend="sqlite",
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def transaction(self, statements: list[dict[str, Any]]) -> ExecutionResult:
        t0 = time.monotonic()
        if not self._conn:
            return ExecutionResult.failure("Not connected.", backend="sqlite")
        try:
            self._conn.execute("BEGIN")
            total_affected = 0
            for stmt in statements:
                sql = stmt.get("sql", "")
                params = stmt.get("params") or []
                cur = self._conn.execute(sql, params)
                if cur.rowcount > 0:
                    total_affected += cur.rowcount
            self._conn.commit()
            return ExecutionResult.success(
                row_count=total_affected,
                statements_executed=len(statements),
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                backend="sqlite",
            )
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return ExecutionResult.failure(
                str(exc),
                backend="sqlite",
                rolled_back=True,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_databases(self) -> ExecutionResult:
        """SQLite: return the current database file path."""
        if not self._conn:
            return ExecutionResult.failure("Not connected.", backend="sqlite")
        return ExecutionResult.success(
            rows=[{"database": self._db_path}],
            row_count=1,
            backend="sqlite",
        )

    def list_tables(self) -> ExecutionResult:
        sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        return self.execute_query(sql)

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------

    def backup(self, destination: str) -> ExecutionResult:
        if not self._conn:
            return ExecutionResult.failure("Not connected.", backend="sqlite")
        try:
            destination = os.path.abspath(destination)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            dest_conn = sqlite3.connect(destination)
            self._conn.backup(dest_conn)
            dest_conn.close()
            return ExecutionResult.success(
                destination=destination, backend="sqlite"
            )
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="sqlite")

    def restore(self, source: str) -> ExecutionResult:
        if not self._conn:
            return ExecutionResult.failure("Not connected.", backend="sqlite")
        source = os.path.abspath(source)
        if not os.path.isfile(source):
            return ExecutionResult.failure(
                f"Backup file not found: {source}", backend="sqlite"
            )
        try:
            src_conn = sqlite3.connect(source)
            src_conn.backup(self._conn)
            src_conn.close()
            self._conn.commit()
            return ExecutionResult.success(source=source, backend="sqlite")
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="sqlite")
