"""Tests for database helpers."""

from app.config.manager import ConfigManager


def test_get_client_does_not_nest_get_db(temp_db, monkeypatch):
    config = ConfigManager()
    config.set("subnet", "10.6.13", save=True)
    from app.database import save_client, get_client, get_all_clients

    save_client("alice", {
        "ip": 2,
        "private_key": "priv",
        "public_key": "pub",
        "allowed_ips": ["0.0.0.0/0"],
        "enabled": True,
    })

    calls = {"n": 0}
    original = temp_db.get_config_value

    def tracked(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(temp_db, "get_config_value", tracked)

    client = get_client("alice")
    all_clients = get_all_clients()

    assert client["ip_full"] == "10.6.13.2"
    assert all_clients["alice"]["ip_full"] == "10.6.13.2"
    assert calls["n"] == 0
