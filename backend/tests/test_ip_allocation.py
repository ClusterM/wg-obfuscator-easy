"""Tests for unique client IP allocation."""

import sqlite3
import threading

from app.clients.manager import ClientManager
from app.config.manager import ConfigManager


class DummyWG:
    wg_interface = "wg0"


class DummyObf:
    pass


def _manager(temp_db):
    config = ConfigManager()
    config.main["own_ip"] = 1
    manager = ClientManager(config, DummyWG(), DummyObf())
    manager.generate_key_pair = lambda: ("priv", "pub")
    return manager


def test_schema_version_and_unique_index(temp_db):
    conn = temp_db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_version")
    assert cursor.fetchone()[0] == temp_db.CURRENT_SCHEMA_VERSION
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_clients_ip'")
    assert cursor.fetchone() is not None


def test_duplicate_ips_skip_unique_index(temp_db, caplog):
    conn = temp_db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DROP INDEX IF EXISTS idx_clients_ip")
    now = "2020-01-01T00:00:00"
    for name in ("a", "b"):
        cursor.execute(
            """
            INSERT INTO clients (
                username, ip, private_key, public_key, allowed_ips,
                keep_server_in_allowed_ips, enabled, created_at, updated_at
            ) VALUES (?, 7, 'k', 'k', '[]', 0, 1, ?, ?)
            """,
            (name, now, now),
        )
    conn.commit()
    cursor.execute("DELETE FROM schema_version")
    conn.commit()
    if hasattr(temp_db._local, "connection"):
        temp_db._local.connection.close()
        temp_db._local.connection = None

    temp_db.init_database()
    conn = temp_db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_clients_ip'")
    assert cursor.fetchone() is None
    assert "duplicates exist" in caplog.text


def test_sequential_clients_get_distinct_ips(temp_db):
    manager = _manager(temp_db)
    first = manager.add_client("alice")
    second = manager.add_client("bob")
    assert first["ip"] != second["ip"]
    assert {first["ip"], second["ip"]} == {2, 3}


def test_parallel_clients_get_distinct_ips(temp_db):
    manager = _manager(temp_db)
    results = {}
    errors = []

    def create(name):
        try:
            results[name] = manager.add_client(name)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=create, args=(f"user{i}",)) for i in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    ips = [client["ip"] for client in results.values()]
    assert len(ips) == 12
    assert len(set(ips)) == 12
    assert 1 not in ips


def test_integrity_error_retries_next_ip(temp_db, monkeypatch):
    manager = _manager(temp_db)
    calls = {"n": 0}

    original = manager.config_manager.set_client

    def flaky(username, client_data, save=True):
        calls["n"] += 1
        if calls["n"] == 1:
            # Another writer claimed this IP between lookup and insert
            original("occupied", dict(client_data), save=True)
            raise sqlite3.IntegrityError("UNIQUE constraint failed: clients.ip")
        return original(username, client_data, save=save)

    monkeypatch.setattr(manager.config_manager, "set_client", flaky)
    client = manager.add_client("carol")
    assert client["ip"] == 3
    assert calls["n"] == 2
