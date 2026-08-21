"""Shared pytest fixtures.

Tests must never touch the production database at /config/wg-easy.db, so the
DB path is redirected to a temporary file before the database module opens any
connection.
"""

import os

import pytest

# Ensure auth is on by default for API tests; individual tests can override.
os.environ.setdefault("AUTH_ENABLED", "true")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the database module at an isolated temporary SQLite file."""
    from app import database

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_FILE", str(db_path))
    # Drop any thread-local connection opened by a previous test.
    if hasattr(database._local, "connection"):
        try:
            database._local.connection.close()
        except Exception:
            pass
        database._local.connection = None

    database.init_database()
    yield database

    conn = getattr(database._local, "connection", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        database._local.connection = None
