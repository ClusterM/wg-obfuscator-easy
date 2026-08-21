"""Tests for install.sh Caddyfile managed-block helpers."""

import os
import subprocess
from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parents[2] / "install.sh"


def run_helpers(script, cwd):
    full = f"source '{INSTALL_SH}'\n{script}"
    result = subprocess.run(
        ["bash", "-c", full],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "LANG_CHOICE": "en"},
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return result


def test_preserves_foreign_site(tmp_path):
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text("other.example {\n    reverse_proxy 10.0.0.5:80\n}\n")
    run_helpers(
        f"""
block=$(render_caddy_managed_block "vpn.example" "8080" "https" "domain" "admin@example.com")
upsert_caddy_managed_block "{caddyfile}" "$block" "vpn.example"
""",
        tmp_path,
    )
    text = caddyfile.read_text()
    assert "other.example" in text
    assert "reverse_proxy 10.0.0.5:80" in text
    assert text.count(">>> wg-obfuscator-easy managed block") == 1
    assert "vpn.example" in text
    assert "tls admin@example.com" in text
    assert "{\n    email " not in text


def test_second_write_does_not_duplicate(tmp_path):
    caddyfile = tmp_path / "Caddyfile"
    run_helpers(
        f"""
block=$(render_caddy_managed_block "vpn.example" "8080" "https" "domain" "")
upsert_caddy_managed_block "{caddyfile}" "$block" "vpn.example"
block=$(render_caddy_managed_block "vpn.example" "9090" "https" "domain" "")
upsert_caddy_managed_block "{caddyfile}" "$block" "vpn.example"
""",
        tmp_path,
    )
    text = caddyfile.read_text()
    assert text.count(">>> wg-obfuscator-easy managed block") == 1
    assert "127.0.0.1:9090" in text
    assert "127.0.0.1:8080" not in text


def test_migrates_legacy_block_and_keeps_other_sites(tmp_path):
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text(
        """{
    email old@example.com
}

vpn.example {
    reverse_proxy 127.0.0.1:8080 {
        header_up Host {host}
    }
    header {
        X-Frame-Options "DENY"
    }
}

blog.example {
    reverse_proxy 192.168.1.10:80
}
"""
    )
    run_helpers(
        f"""
block=$(render_caddy_managed_block "vpn.example" "9090" "https" "domain" "new@example.com")
upsert_caddy_managed_block "{caddyfile}" "$block" "vpn.example"
""",
        tmp_path,
    )
    text = caddyfile.read_text()
    assert "blog.example" in text
    assert "192.168.1.10:80" in text
    assert "email old@example.com" not in text
    assert text.count("vpn.example") == 1
    assert "127.0.0.1:9090" in text
    assert "tls new@example.com" in text
    assert text.count(">>> wg-obfuscator-easy managed block") == 1


def test_is_ipv4_rejects_out_of_range_octets(tmp_path):
    result = subprocess.run(
        ["bash", "-c", f"source '{INSTALL_SH}'\n"
         "is_ipv4 1.2.3.4 && echo ok\n"
         "is_ipv4 999.999.999.999 || echo bad\n"
         "is_ipv4 vpn.example || echo host\n"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["ok", "bad", "host"]


def test_upsert_makes_caddyfile_world_readable(tmp_path):
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text("other.example {\n    reverse_proxy 10.0.0.5:80\n}\n")
    caddyfile.chmod(0o600)
    run_helpers(
        f"""
block=$(render_caddy_managed_block "vpn.example" "8080" "https" "domain" "")
upsert_caddy_managed_block "{caddyfile}" "$block" "vpn.example"
""",
        tmp_path,
    )
    mode = caddyfile.stat().st_mode & 0o777
    assert mode == 0o644


def test_ip_mode_puts_email_inside_issuer(tmp_path):
    result = run_helpers(
        'render_caddy_managed_block "203.0.113.1" "8080" "https" "ip" "admin@example.com"',
        tmp_path,
    )
    assert "profile shortlived" in result.stdout
    assert "email admin@example.com" in result.stdout
    assert "{\n    email admin@example.com\n}" not in result.stdout
