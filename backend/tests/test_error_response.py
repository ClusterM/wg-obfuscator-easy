"""Tests for API error sanitization."""

import pytest
from flask import Flask

from app.api.errors import INTERNAL_ERROR_MESSAGE, error_response
from app.exceptions import ClientNotFoundError, ServiceError


@pytest.fixture
def app_ctx():
    app = Flask(__name__)
    with app.app_context():
        yield


def test_domain_exception_keeps_message(app_ctx):
    response, status = error_response(ClientNotFoundError("Client missing"), status=404)
    assert status == 404
    assert response.get_json() == {"error": "Client missing"}


def test_service_error_keeps_message(app_ctx):
    response, status = error_response(ServiceError("wg-quick failed"))
    assert status == 500
    assert response.get_json() == {"error": "wg-quick failed"}


def test_unexpected_exception_is_hidden(app_ctx):
    response, status = error_response(RuntimeError("secret path /etc/shadow"))
    assert status == 500
    assert response.get_json() == {"error": INTERNAL_ERROR_MESSAGE}
    assert "shadow" not in response.get_data(as_text=True)


def test_clients_list_does_not_leak_internal_error(monkeypatch):
    from app.api import create_app
    from app import database
    from app.wireguard import stats as wg_stats

    def boom():
        raise RuntimeError("secret path /etc/shadow")

    monkeypatch.setattr(database, "get_all_clients", boom)

    class FakeStats:
        def __init__(self, *a, **k):
            pass

        def get_stats(self, clients):
            return {"peers": []}

    monkeypatch.setattr(wg_stats, "WireGuardStats", FakeStats)

    class FakeTokens:
        def is_valid(self, token):
            return True

    class FakeConfig:
        main = {}
        clients = {}

        def set_client(self, *a, **k):
            pass

        def update_client_handshake(self, *a, **k):
            pass

    class FakeWG:
        wg_interface = "wg0"

    app = create_app(FakeConfig(), None, FakeWG(), object(), FakeTokens(), "1.2.3.4", 51820)
    resp = app.test_client().get("/api/clients", headers={"Authorization": "Bearer t"})
    assert resp.status_code == 500
    assert resp.get_json() == {"error": INTERNAL_ERROR_MESSAGE}
    assert "shadow" not in resp.get_data(as_text=True)
