"""Tests for the shared require_auth decorator."""

from flask import Flask

from app.auth.tokens import require_auth, get_bearer_token


def test_get_bearer_token_strips_whitespace():
    app = Flask(__name__)
    with app.test_request_context(headers={"Authorization": "Bearer  abc  "}):
        token, error = get_bearer_token()
    assert error is None
    assert token == "abc"


def test_require_auth_uses_app_token_manager():
    app = Flask(__name__)
    calls = {"n": 0}

    class FakeTokens:
        def is_valid(self, token):
            calls["n"] += 1
            return token == "ok"

    app.token_manager = FakeTokens()

    @require_auth
    def view():
        return "ok"

    with app.app_context():
        with app.test_request_context(headers={"Authorization": "Bearer ok"}):
            assert view() == "ok"
        with app.test_request_context(headers={"Authorization": "Bearer bad"}):
            response, status = view()
            assert status == 401
    assert calls["n"] == 2
