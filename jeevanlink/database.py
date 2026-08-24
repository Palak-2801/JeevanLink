"""Database access for JeevanLink.

Two backends are supported from the same code:

* **SQLite** — the default. Zero setup, one file, perfect for local
  development and for running the test suite.
* **PostgreSQL** — used when the ``DATABASE_URL`` environment variable
  is set. Cloud hosts give you this variable, and a shared Postgres is
  what lets several devices see the same donors.

The rest of the project keeps writing plain SQLite-flavoured SQL with
``?`` placeholders. The wrappers below translate that to Postgres when
needed, so no other module has to care which database is in use.
"""

import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------
# WHICH BACKEND?
# ---------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Some providers still hand out the old "postgres://" prefix.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

IS_POSTGRES = DATABASE_URL.startswith("postgresql://")

BASE_DIR = Path(__file__).resolve().parent

# Only meaningful for SQLite. Kept at module level because the test
# suite monkeypatches it to point at a temporary file.
DATABASE_NAME = BASE_DIR / "jeevanlink.db"

SQLITE_SCHEMA = BASE_DIR / "schema.sql"
POSTGRES_SCHEMA = BASE_DIR / "schema_postgres.sql"


def schema_path() -> Path:
    return POSTGRES_SCHEMA if IS_POSTGRES else SQLITE_SCHEMA


def backend_name() -> str:
    return "postgresql" if IS_POSTGRES else "sqlite"


def describe_database() -> str:
    """Human readable location, used by the health endpoint."""
    if IS_POSTGRES:
        # Never leak the password.
        return re.sub(r"://[^@]+@", "://***@", DATABASE_URL)
    return str(DATABASE_NAME)


# ---------------------------------------------------------------------
# SQL TRANSLATION
# ---------------------------------------------------------------------

_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")


def _to_postgres(sql: str) -> str:
    """Rewrite SQLite-flavoured SQL so PostgreSQL accepts it."""

    # Protect string literals so placeholders inside them are untouched.
    literals: list = []

    def stash(match):
        literals.append(match.group(0))
        return f"\x00{len(literals) - 1}\x00"

    sql = _STRING_LITERAL.sub(stash, sql)

    # ? -> %s
    sql = sql.replace("?", "%s")

    # INSERT OR IGNORE -> ON CONFLICT DO NOTHING
    ignore = re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", sql, re.IGNORECASE)
    if ignore:
        sql = re.sub(
            r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
            "INSERT INTO",
            sql,
            flags=re.IGNORECASE,
        )
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # SQLite date helpers used in seed data.
    sql = re.sub(
        r"datetime\(\s*\x00\d+\x00\s*,\s*\x00\d+\x00\s*\)",
        "NOW()",
        sql,
        flags=re.IGNORECASE,
    )

    # Restore literals.
    def restore(match):
        return literals[int(match.group(1))]

    sql = re.sub(r"\x00(\d+)\x00", restore, sql)
    return sql


_INSERT_START = re.compile(r"^\s*INSERT\s+", re.IGNORECASE)
_HAS_RETURNING = re.compile(r"\bRETURNING\b", re.IGNORECASE)


# ---------------------------------------------------------------------
# ROW: works with row["name"] and row[0]
# ---------------------------------------------------------------------

class Row:
    """A result row that supports both name and index access.

    ``sqlite3.Row`` already does this. Postgres rows come back as plain
    dicts, so this class restores the same behaviour and keeps calls
    like ``row["name"]`` and ``row[0]`` working unchanged.
    """

    __slots__ = ("_data", "_order")

    def __init__(self, data: dict):
        self._data = data
        self._order = list(data.keys())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._order[key]]
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._order

    def values(self):
        return [self._data[k] for k in self._order]

    def items(self):
        return [(k, self._data[k]) for k in self._order]

    def __iter__(self):
        return iter(self.values())

    def __len__(self):
        return len(self._order)

    def __repr__(self):
        return f"Row({self._data!r})"


# ---------------------------------------------------------------------
# POSTGRES WRAPPERS
# ---------------------------------------------------------------------

class _PgCursor:
    """Mimics the small part of the sqlite3 cursor API this app uses."""

    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def fetchone(self):
        row = self._cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self):
        return [Row(r) for r in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _PgConnection:
    """Adapter that lets Postgres be used through the sqlite3 API."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, params=()):
        from psycopg.rows import dict_row

        statement = _to_postgres(sql)
        wants_id = False

        # sqlite exposes cursor.lastrowid after an INSERT. Postgres needs
        # an explicit RETURNING clause to give the same information.
        if _INSERT_START.match(statement) and not _HAS_RETURNING.search(statement):
            statement = statement.rstrip().rstrip(";") + " RETURNING id"
            wants_id = True

        cursor = self._connection.cursor(row_factory=dict_row)
        cursor.execute(statement, tuple(params))

        lastrowid = None
        if wants_id:
            try:
                row = cursor.fetchone()
                if row is not None:
                    lastrowid = row.get("id")
            except Exception:
                # ON CONFLICT DO NOTHING can return no row at all.
                lastrowid = None

        return _PgCursor(cursor, lastrowid)

    def executemany(self, sql: str, seq):
        statement = _to_postgres(sql)
        cursor = self._connection.cursor()
        rows = list(seq)
        cursor.executemany(statement, [tuple(r) for r in rows])
        return _PgCursor(cursor)

    def executescript(self, script: str):
        cursor = self._connection.cursor()
        cursor.execute(script)
        return _PgCursor(cursor)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# ---------------------------------------------------------------------
# SHARED INTEGRITY ERROR
# ---------------------------------------------------------------------

def _integrity_errors():
    errors = [sqlite3.IntegrityError]
    if IS_POSTGRES:
        try:
            import psycopg
            errors.append(psycopg.errors.IntegrityError)
        except Exception:
            pass
    return tuple(errors)


IntegrityError = _integrity_errors()


# ---------------------------------------------------------------------
# CONNECTION FACTORY
# ---------------------------------------------------------------------

def get_db_connection(db_path: Optional[Any] = None):
    """Return a connection that behaves like ``sqlite3.Connection``.

    ``db_path`` only applies to SQLite and lets tests point at a
    temporary file.
    """
    if IS_POSTGRES and db_path is None:
        import psycopg

        # client_encoding is forced because a server created with the
        # SQL_ASCII encoding otherwise hands back bytes instead of str,
        # which then fails to serialise to JSON.
        connection = psycopg.connect(
            DATABASE_URL,
            autocommit=False,
            client_encoding="UTF8",
        )
        return _PgConnection(connection)

    path = Path(db_path) if db_path is not None else DATABASE_NAME
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
