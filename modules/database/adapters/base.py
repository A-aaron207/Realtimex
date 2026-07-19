"""
Abstract base class for Database Module backend adapters.

Every backend (SQLite, PostgreSQL, MySQL, …) must implement this interface.
The module routes all capability calls through these methods, keeping the
public API stable across backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from modules.database.result import ExecutionResult


class BaseAdapter(ABC):
    """
    Abstract database adapter interface.

    Subclasses are responsible for:
    - Opening and closing physical connections / pools.
    - Translating the universal capability arguments into backend-specific SQL.
    - Returning structured ExecutionResult objects.
    - Parameterizing all queries (never use string formatting for user data).
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> ExecutionResult:
        """Open a connection using the supplied config dict."""

    @abstractmethod
    def disconnect(self) -> ExecutionResult:
        """Close the connection and release resources."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the adapter currently holds an open connection."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier, e.g. 'sqlite', 'postgresql'."""

    # ------------------------------------------------------------------
    # DDL
    # ------------------------------------------------------------------

    @abstractmethod
    def create_database(self, name: str) -> ExecutionResult:
        """Create a new database (semantics vary by backend)."""

    @abstractmethod
    def create_table(
        self,
        table: str,
        columns: list[dict[str, str]],
        if_not_exists: bool = True,
    ) -> ExecutionResult:
        """
        Create a table with the given column definitions.

        Each column dict must contain at least ``name`` and ``type``.
        Optional keys: ``primary_key`` (bool), ``nullable`` (bool),
        ``unique`` (bool), ``default`` (str).
        """

    # ------------------------------------------------------------------
    # DML
    # ------------------------------------------------------------------

    @abstractmethod
    def insert_record(
        self,
        table: str,
        data: dict[str, Any],
    ) -> ExecutionResult:
        """Insert a single row into *table*."""

    @abstractmethod
    def update_record(
        self,
        table: str,
        data: dict[str, Any],
        where: dict[str, Any],
    ) -> ExecutionResult:
        """Update rows in *table* matching *where* with *data* values."""

    @abstractmethod
    def delete_record(
        self,
        table: str,
        where: dict[str, Any],
    ) -> ExecutionResult:
        """Delete rows from *table* matching *where*."""

    @abstractmethod
    def select_records(
        self,
        table: str,
        columns: list[str] | None = None,
        where: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ExecutionResult:
        """Select rows from *table* with optional filtering and pagination."""

    # ------------------------------------------------------------------
    # Raw query
    # ------------------------------------------------------------------

    @abstractmethod
    def execute_query(
        self,
        sql: str,
        params: list[Any] | tuple[Any, ...] | None = None,
    ) -> ExecutionResult:
        """Execute an arbitrary parameterized SQL statement."""

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    @abstractmethod
    def transaction(self, statements: list[dict[str, Any]]) -> ExecutionResult:
        """
        Execute multiple statements atomically.

        Each statement dict contains ``sql`` and optionally ``params``.
        Rolls back on any error.
        """

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @abstractmethod
    def list_databases(self) -> ExecutionResult:
        """List all databases accessible by this connection."""

    @abstractmethod
    def list_tables(self) -> ExecutionResult:
        """List all tables in the current database / schema."""

    # ------------------------------------------------------------------
    # Backup / Restore
    # ------------------------------------------------------------------

    @abstractmethod
    def backup(self, destination: str) -> ExecutionResult:
        """Back up the current database to *destination* path."""

    @abstractmethod
    def restore(self, source: str) -> ExecutionResult:
        """Restore the current database from the *source* backup path."""
