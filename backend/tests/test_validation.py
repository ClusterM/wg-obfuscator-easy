"""Tests for client name validation and filename sanitisation."""

import pytest

from app.api.clients import validate_username, safe_filename
from app.clients.manager import ClientManager


@pytest.mark.parametrize("name", ["alice", "Клиент-1", "my phone.2", "a" * 64])
def test_valid_usernames(name):
    assert validate_username(name) is None


@pytest.mark.parametrize("name", [
    "",
    "  ",
    "bob ",
    "a" * 65,
    "evil\n[Peer]\nPublicKey = x",
    "tab\there",
    "name#with",
    'na"me',
    "pa/th",
    42,
])
def test_invalid_usernames(name):
    assert validate_username(name) is not None


def test_safe_filename_strips_dangerous_chars():
    assert safe_filename('legacy"na\nme/x') == "legacynamex"


@pytest.mark.parametrize("key,expected", [
    ("cOTGfq3o2upkUVFsyGAx/WoFlcpSlNQnUYyww9HF+Vs=", True),  # 32 bytes
    ("short", False),
    ("", False),
    (None, False),
])
def test_is_valid_wireguard_key(key, expected):
    assert ClientManager.is_valid_wireguard_key(key) is expected
