"""Integration tests for the clients API using mocked managers."""

import pytest


class FakeTokenManager:
    def is_valid(self, token):
        return token == "valid-token"


class FakeWG:
    wg_interface = "wg0"

    def status(self):
        return {"running": True}


class FakeObf:
    def status(self, *a):
        return {"running": False}


class FakeConfigManager:
    def __init__(self):
        self.main = {"obfuscation": True}
        self.clients = {}
        self.set_client_calls = 0
        self.handshake_updates = []

    def set_client(self, *a, **k):
        self.set_client_calls += 1

    def update_client_handshake(self, username, handshake):
        self.handshake_updates.append((username, handshake))


@pytest.fixture
def client(monkeypatch):
    from app.api import create_app
    from app import database
    from app.wireguard import stats as wg_stats

    sample = {
        "alice": {
            "ip": 2,
            "private_key": "PRIV_SECRET",
            "public_key": "PUB",
            "preshared_key": "PSK_SECRET",
            "enabled": True,
            "latest_handshake": 0,
        }
    }
    monkeypatch.setattr(database, "get_all_clients", lambda: {k: dict(v) for k, v in sample.items()})

    class FakeStats:
        def __init__(self, *a, **k):
            pass

        def get_stats(self, clients):
            return {"peers": []}

    monkeypatch.setattr(wg_stats, "WireGuardStats", FakeStats)

    app = create_app(
        FakeConfigManager(), None, FakeWG(), FakeObf(),
        FakeTokenManager(), "vpn.example.com", 51820,
    )
    return app.test_client()


AUTH = {"Authorization": "Bearer valid-token"}


def test_health_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_clients_list_omits_secrets(client):
    resp = client.get("/api/clients", headers=AUTH)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "private_key" not in body["alice"]
    assert "preshared_key" not in body["alice"]
    assert "PRIV_SECRET" not in resp.get_data(as_text=True)


def test_clients_list_requires_auth(client):
    resp = client.get("/api/clients")
    assert resp.status_code == 401


def test_clients_list_updates_handshake_without_full_save(monkeypatch):
    from app.api import create_app
    from app import database
    from app.wireguard import stats as wg_stats

    sample = {
        "alice": {
            "ip": 2,
            "private_key": "PRIV_SECRET",
            "public_key": "PUB",
            "preshared_key": None,
            "enabled": True,
            "latest_handshake": 1,
        }
    }
    monkeypatch.setattr(database, "get_all_clients", lambda: {k: dict(v) for k, v in sample.items()})

    class FakeStats:
        def __init__(self, *a, **k):
            pass

        def get_stats(self, clients):
            return {
                "peers": [{
                    "public_key": "PUB",
                    "is_connected": True,
                    "transfer_rx_bytes": 10,
                    "transfer_tx_bytes": 20,
                    "latest_handshake": 99,
                }]
            }

    monkeypatch.setattr(wg_stats, "WireGuardStats", FakeStats)
    config = FakeConfigManager()
    app = create_app(config, None, FakeWG(), FakeObf(), FakeTokenManager(), "1.2.3.4", 51820)
    resp = app.test_client().get("/api/clients", headers=AUTH)
    assert resp.status_code == 200
    assert config.set_client_calls == 0
    assert config.handshake_updates == [("alice", 99)]
    assert resp.get_json()["alice"]["latest_handshake"] == 99
