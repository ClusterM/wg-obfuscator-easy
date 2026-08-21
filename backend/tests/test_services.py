"""Tests for ServiceManager config apply and rollback."""

import pytest

from app.exceptions import ServiceError
from app.services import ServiceManager


class FakeConfig:
    def __init__(self):
        self.main = {
            "wg_interface": "wg0",
            "enabled": True,
            "obfuscation": True,
            "obfuscation_key": "k",
        }
        self.clients = {}


class FakeWG:
    def __init__(self, fail_first=False):
        self.starts = 0
        self.stops = 0
        self.fail_first = fail_first

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1
        if self.fail_first and self.starts == 1:
            raise ServiceError("wg-quick failed")


class FakeObf:
    def __init__(self):
        self.starts = 0
        self.stops = 0

    def stop(self):
        self.stops += 1

    def start(self):
        self.starts += 1


def _manager(tmp_path, fail_first=False):
    wg_path = tmp_path / "wg0.conf"
    obf_path = tmp_path / "obf.conf"
    wg_path.write_text("OLD_WG")
    obf_path.write_text("OLD_OBF")

    manager = ServiceManager(FakeConfig(), None, FakeWG(fail_first), FakeObf(), "1.2.3.4", 51820)
    manager._config_paths = lambda: [str(wg_path), str(obf_path)]

    def generate():
        wg_path.write_text("NEW_WG")
        obf_path.write_text("NEW_OBF")

    manager.generate_configs = generate
    return manager, wg_path, obf_path


def test_apply_config_changes_rolls_back_files(tmp_path):
    manager, wg_path, obf_path = _manager(tmp_path, fail_first=True)

    with pytest.raises(ServiceError, match="previous configuration was restored"):
        manager.apply_config_changes()

    assert wg_path.read_text() == "OLD_WG"
    assert obf_path.read_text() == "OLD_OBF"
    assert manager.wg_manager.starts == 2
    assert manager.obfuscator_manager.starts == 2


def test_apply_config_changes_keeps_new_files_on_success(tmp_path):
    manager, wg_path, obf_path = _manager(tmp_path, fail_first=False)
    manager.apply_config_changes()
    assert wg_path.read_text() == "NEW_WG"
    assert obf_path.read_text() == "NEW_OBF"
    assert manager.wg_manager.starts == 1


def test_apply_config_changes_removes_new_file_if_none_existed(tmp_path):
    wg_path = tmp_path / "wg0.conf"
    obf_path = tmp_path / "obf.conf"
    manager = ServiceManager(FakeConfig(), None, FakeWG(fail_first=True), FakeObf(), "1.2.3.4", 51820)
    manager._config_paths = lambda: [str(wg_path), str(obf_path)]

    def generate():
        wg_path.write_text("NEW_WG")
        obf_path.write_text("NEW_OBF")

    manager.generate_configs = generate

    with pytest.raises(ServiceError, match="previous configuration was restored"):
        manager.apply_config_changes()

    assert not wg_path.exists()
    assert not obf_path.exists()
