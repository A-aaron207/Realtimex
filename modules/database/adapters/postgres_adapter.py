"""
PostgreSQL backend adapter for the Database Module.

Requires: psycopg2-binary  (pip install psycopg2-binary)

If psycopg2 is not installed the adapter degrades gracefully — all methods
return a FAILED result with a clear installation message instead of raising
an ImportError at module load time.
"""

from __future__ import annotations

import time
from typing import Any

from modules.database.adapters.base import BaseAdapter
from modules.database.result import ExecutionResult

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False

_INSTALL_MSG = (
    "psycopg2 is not installed. "
    "Run: pip install psycopg2-binary"
)


class PostgreSQLAdapter(BaseAdapter):
    """PostgreSQL implementation using psycopg2."""

    backend_name = "postgresql"

    def __init__(self) -> None:
        self._conn: Any = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.closed

    def _unavailable(self) -> ExecutionResult:
        return ExecutionResult.failure(_INSTALL_MSG, backend="postgresql")

    def _cursor(self) -> Any:
        if not self._conn:
            raise RuntimeError("Not connected.")
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self, config: dict[str, Any]) -> ExecutionResult:
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        try:
            self._conn = psycopg2.connect(
                host=config.get("host", "localhost"),
                port=int(config.get("port", 5432)),
                dbname=config.get("database", "postgres"),
                user=config.get("user", "postgres"),
                password=config.get("password", ""),
            )
            self._conn.autocommit = False
            return ExecutionResult.success(
                backend="postgresql",
                host=config.get("host"),
                database=config.get("database"),
            )
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="postgresql")

    def disconnect(self) -> ExecutionResult:
        if self._conn and not self._conn.closed:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        return ExecutionResult.success(backend="postgresql")

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    def create_database(self, name: str) -> ExecutionResult:
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        try:
            old_autocommit = self._conn.autocommit
            self._conn.autocommit = True
            cur = self._conn.cursor()
            cur.execute(f"CREATE DATABASE {name}")
            self._conn.autocommit = old_autocommit
            return ExecutionResult.success(database=name, backend="postgresql")
        except Exception as exc:
            return ExecutionResult.failure(str(exc), backend="postgresql")

    def create_table(
        self,
        table: str,
        columns: list[dict[str, str]],
        if_not_exists: bool = True,
    ) -> ExecutionResult:
        if not _PSYCOPG2_AVAILABLE:
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
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING *"
        return self.execute_query(sql, list(data.values()))

    def update_record(self, table: str, data: dict[str, Any], where: dict[str, Any]) -> ExecutionResult:
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        if not where:
            return ExecutionResult.failure("update_record requires a non-empty where clause.", backend="postgresql")
        set_clause = ", ".join(f"{k} = %s" for k in data)
        where_clause = " AND ".join(f"{k} = %s" for k in where)
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        return self.execute_query(sql, list(data.values()) + list(where.values()))

    def delete_record(self, table: str, where: dict[str, Any]) -> ExecutionResult:
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        if not where:
            return ExecutionResult.failure("delete_record requires a non-empty where clause.", backend="postgresql")
        where_clause = " AND ".join(f"{k} = %s" for k in where)
        sql = f"DELETE FROM {table} WHERE {where_clause}"
        return self.execute_query(sql, list(where.values()))

    def select_records(self, table, columns=None, where=None, order_by=None, limit=None, offset=None):
        if not _PSYCOPG2_AVAILABLE:
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
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        t0 = time.monotonic()
        try:
            cur = self._cursor()
            cur.execute(sql, params or [])
            self._conn.commit()
            rows = [dict(r) for r in (cur.fetchall() or [])]
            return ExecutionResult.success(
                rows=rows,
                row_count=cur.rowcount if cur.rowcount >= 0 else len(rows),
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                backend="postgresql",
            )
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return ExecutionResult.failure(
                str(exc),
                backend="postgresql",
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def transaction(self, statements: list[dict[str, Any]]) -> ExecutionResult:
        if not _PSYCOPG2_AVAILABLE:
            return self._unavailable()
        t0 = time.monotonic()
        try:
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
                backend="postgresql",
            )
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception:
                pass
            return ExecutionResult.failure(str(exc), backend="postgresql", rolled_back=True)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_databases(self) -> ExecutionResult:
        return self.execute_query("SELECT datname AS database FROM pg_database WHERE datistemplate = false")

    def list_tables(self) -> ExecutionResult:
        return self.execute_query(
            "SELECT tablename AS name FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )

    # ------------------------------------------------------------------
    # Backup / Restore  (delegate to pg_dump / pg_restore via subprocess)
    # ------------------------------------------------------------------

    def backup(self, destination: str) -> ExecutionResult:
        return ExecutionResult.failure(
            "PostgreSQL backup via pg_dump is not yet implemented in this adapter version.",
            backend="postgresql",
        )

    def restore(self, source: str) -> ExecutionResult:
        return ExecutionResult.failure(
            "PostgreSQL restore via pg_restore is not yet implemented in this adapter version.",
            backend="postgresql",
        )
