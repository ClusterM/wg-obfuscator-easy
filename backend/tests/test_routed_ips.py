"""Tests for subnets routed to a client on the server side (routed_ips)."""

from types import SimpleNamespace

from app.api.clients import validate_routed_ips
from app.wireguard.config import WireGuardConfigGenerator


BASE_CONFIG = {
    "server_private_key": "SERVER_PRIV",
    "server_public_key": "SERVER_PUB",
    "subnet": "10.6.13",
    "own_ip": 1,
    "wg_interface": "wg0",
    "wan_interface": "eth0",
}


def _manager(clients=None):
    return SimpleNamespace(main={"subnet": "10.6.13"}, clients=clients or {})


def test_server_config_appends_routed_ips():
    clients = {
        "router": {"ip": 4, "public_key": "PUB_R", "enabled": True,
                   "routed_ips": ["192.168.88.0/24", "34.160.111.145/32"]},
        "phone": {"ip": 3, "public_key": "PUB_P", "enabled": True},
    }
    out = WireGuardConfigGenerator.generate_server_config(
        BASE_CONFIG, clients, external_port=51820, obfuscation=True
    )
    assert "AllowedIPs = 10.6.13.4/32, 192.168.88.0/24, 34.160.111.145/32" in out
    assert "AllowedIPs = 10.6.13.3/32\n" in out


def test_validate_accepts_and_normalizes():
    result, err = validate_routed_ips([" 192.168.88.0/24 ", "", "34.160.111.145/32"], "r", _manager())
    assert err is None
    assert result == ["192.168.88.0/24", "34.160.111.145/32"]


def test_validate_empty_list_clears():
    assert validate_routed_ips([], "r", _manager()) == ([], None)


def test_validate_rejects_bad_input():
    m = _manager()
    assert validate_routed_ips("192.168.88.0/24", "r", m)[1]          # not a list
    assert validate_routed_ips([123], "r", m)[1]                     # not a string
    assert validate_routed_ips(["192.168.88.1/24"], "r", m)[1]        # host bits set
    assert validate_routed_ips(["garbage"], "r", m)[1]
    assert validate_routed_ips(["fd00::/64"], "r", m)[1]              # IPv6
    assert validate_routed_ips(["0.0.0.0/0"], "r", m)[1]              # hijacks server
    assert validate_routed_ips(["0.0.0.0/1"], "r", m)[1]
    assert validate_routed_ips(["10.6.0.0/16"], "r", m)[1]            # overlaps VPN subnet
    assert validate_routed_ips(["192.168.0.0/16", "192.168.88.0/24"], "r", m)[1]  # self-overlap


def test_validate_rejects_overlap_with_other_client():
    m = _manager({"other": {"routed_ips": ["192.168.88.0/24"]}, "r": {"routed_ips": ["10.1.0.0/16"]}})
    _, err = validate_routed_ips(["192.168.88.0/25"], "r", m)
    assert err and "other" in err
    # the client's own current subnets do not count as a conflict
    assert validate_routed_ips(["10.1.0.0/16"], "r", m) == (["10.1.0.0/16"], None)


def test_database_roundtrip(temp_db):
    from app.config.manager import ConfigManager
    ConfigManager()
    from app.database import save_client, get_client, get_all_clients

    base = {"ip": 4, "private_key": "priv", "public_key": "pub",
            "allowed_ips": ["0.0.0.0/0"], "enabled": True}
    save_client("router", dict(base))
    assert get_client("router")["routed_ips"] == []

    save_client("router", dict(base, routed_ips=["192.168.88.0/24"]))
    assert get_client("router")["routed_ips"] == ["192.168.88.0/24"]
    assert get_all_clients()["router"]["routed_ips"] == ["192.168.88.0/24"]

    # saving without the key keeps the stored value
    save_client("router", dict(base))
    assert get_client("router")["routed_ips"] == ["192.168.88.0/24"]


def test_patch_api_end_to_end(temp_db, monkeypatch):
    """PATCH /api/clients/<name> stores routed_ips and the server config uses them."""
    from app.api import create_app
    from app.api import clients as clients_api
    from app.config.manager import ConfigManager
    from app.database import save_client

    class FakeTokenManager:
        def is_valid(self, token):
            return token == "t"

    class FakeWG:
        wg_interface = "wg0"

        def status(self):
            return {"running": True}

    class FakeObf:
        def status(self, *a):
            return {"running": False}

    monkeypatch.setattr(clients_api, "apply_config_changes", lambda app: None)

    cm = ConfigManager()
    cm.main["subnet"] = "10.6.13"
    base = {"ip": 4, "private_key": "priv", "public_key": "PUB_R",
            "allowed_ips": ["0.0.0.0/0"], "enabled": True}
    save_client("router", dict(base))
    save_client("router2", dict(base, ip=6, public_key="PUB_R2", routed_ips=["192.168.89.0/24"]))
    cm._load_clients()

    app = create_app(cm, None, FakeWG(), FakeObf(), FakeTokenManager(), "vpn.example.com", 51820)
    http = app.test_client()
    auth = {"Authorization": "Bearer t"}

    resp = http.patch("/api/clients/router", json={"routed_ips": ["192.168.88.0/24"]}, headers=auth)
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["routed_ips"] == ["192.168.88.0/24"]

    # conflict with router2 is rejected
    resp = http.patch("/api/clients/router", json={"routed_ips": ["192.168.89.0/24"]}, headers=auth)
    assert resp.status_code == 400
    assert "router2" in resp.get_json()["error"]

    # GET returns the stored value
    assert http.get("/api/clients/router", headers=auth).get_json()["routed_ips"] == ["192.168.88.0/24"]

    cfg = dict(BASE_CONFIG)
    out = WireGuardConfigGenerator.generate_server_config(cfg, cm.clients, 51820, True)
    assert "AllowedIPs = 10.6.13.4/32, 192.168.88.0/24" in out
    assert "AllowedIPs = 10.6.13.6/32, 192.168.89.0/24" in out
