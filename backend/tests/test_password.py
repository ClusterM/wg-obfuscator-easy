"""Tests for password hashing utilities."""

import hashlib

from app.auth.password import hash_password, verify_password, is_legacy_hash


def test_hash_password_format():
    h = hash_password("secret")
    parts = h.split("$")
    assert parts[0] == "pbkdf2_sha256"
    assert int(parts[1]) > 0
    assert len(parts) == 4


def test_hash_password_is_salted():
    assert hash_password("secret") != hash_password("secret")


def test_verify_password_roundtrip():
    h = hash_password("correct horse")
    assert verify_password("correct horse", h) is True
    assert verify_password("wrong", h) is False


def test_verify_empty_hash():
    assert verify_password("anything", "") is False


def test_verify_malformed_hash():
    assert verify_password("x", "not$a$valid$hash") is False


def test_legacy_sha256_detected_and_verified():
    legacy = hashlib.sha256("secret".encode()).hexdigest()
    assert is_legacy_hash(legacy) is True
    assert verify_password("secret", legacy) is True
    assert verify_password("wrong", legacy) is False


def test_new_hash_not_flagged_legacy():
    assert is_legacy_hash(hash_password("secret")) is False
