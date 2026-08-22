"""Tests for small pure helpers in utils."""

import pytest

from app.utils import (
    parse_listen_port_env,
    get_effective_listen_port,
    resolve_external_ipv4,
    generate_obfuscation_key,
    is_valid_obfuscation_key,
)
from app.exceptions import ConfigError


def test_parse_listen_port_unset(monkeypatch):
    monkeypatch.delenv("LISTEN_PORT", raising=False)
    assert parse_listen_port_env() is None


def test_parse_listen_port_empty(monkeypatch):
    monkeypatch.setenv("LISTEN_PORT", "  ")
    assert parse_listen_port_env() is None


def test_parse_listen_port_valid(monkeypatch):
    monkeypatch.setenv("LISTEN_PORT", "51820")
    assert parse_listen_port_env() == 51820


def test_parse_listen_port_invalid(monkeypatch):
    monkeypatch.setenv("LISTEN_PORT", "99999")
    with pytest.raises(ConfigError):
        parse_listen_port_env()


def test_effective_listen_port_null_falls_back():
    assert get_effective_listen_port({"listen_port": None}, 51820) == 51820


def test_effective_listen_port_explicit():
    assert get_effective_listen_port({"listen_port": 1234}, 51820) == 1234


def test_resolve_external_ipv4_literal():
    assert resolve_external_ipv4("203.0.113.7") == ["203.0.113.7"]


def test_resolve_external_ipv4_rejects_ipv6_literal():
    with pytest.raises(ConfigError):
        resolve_external_ipv4("::1")


def test_generate_obfuscation_key_is_alphanumeric():
    key = generate_obfuscation_key()
    assert len(key) == 64
    assert is_valid_obfuscation_key(key)
    assert "#" not in key


@pytest.mark.parametrize("key,expected", [
    ("", True),
    ("Abc123", True),
    ("key#value", False),
    ("key;value", False),
    ("key value", False),
    ("ключ", False),
])
def test_is_valid_obfuscation_key(key, expected):
    assert is_valid_obfuscation_key(key) is expected
