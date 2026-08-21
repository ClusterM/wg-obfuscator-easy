"""Tests for AllowedIPs exclusion logic."""

import ipaddress

from app.clients.manager import ClientManager


def _calc(allowed, exclude):
    # calculate_allowed_ips does not use instance state.
    return ClientManager.calculate_allowed_ips(None, allowed, exclude)


def _covers(subnets, ip):
    return any(
        ipaddress.ip_address(ip) in ipaddress.ip_network(s) for s in subnets
    )


def test_single_exclude_removes_address():
    result = _calc(["0.0.0.0/0"], ["1.2.3.4/32"])
    assert not _covers(result, "1.2.3.4")
    assert _covers(result, "8.8.8.8")


def test_multiple_excludes_all_removed():
    # Regression: several A-records must all be excluded, not just one.
    result = _calc(["0.0.0.0/0"], ["1.2.3.4/32", "5.6.7.8/32"])
    assert not _covers(result, "1.2.3.4")
    assert not _covers(result, "5.6.7.8")
    assert _covers(result, "8.8.8.8")


def test_no_exclude_returns_input():
    assert _calc(["0.0.0.0/0"], []) == ["0.0.0.0/0"]


def test_multiple_allowed_non_overlapping_exclude():
    result = _calc(["10.0.0.0/8", "192.168.0.0/16"], ["1.2.3.4/32"])
    assert set(result) == {"10.0.0.0/8", "192.168.0.0/16"}


def test_full_removal():
    assert _calc(["10.0.0.0/8"], ["10.0.0.0/8"]) == []
