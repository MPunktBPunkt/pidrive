"""VERSION-Dateien und install.sh müssen synchron sein."""
from __future__ import annotations

import re
from pathlib import Path


def test_version_files_match(repo_root: Path):
    root_v = (repo_root / "VERSION").read_text().strip()
    pkg_v = (repo_root / "pidrive" / "VERSION").read_text().strip()
    install = (repo_root / "install.sh").read_text()
    m = re.search(r'^PIDRIVE_VERSION="([^"]+)"', install, re.M)
    assert m, "PIDRIVE_VERSION fehlt in install.sh"
    assert root_v == pkg_v == m.group(1)
    assert re.match(r"^\d+\.\d+\.\d+", root_v), root_v


def test_wifi_recover_script_present(repo_root: Path):
    script = repo_root / "scripts" / "wifi-recover.sh"
    unit = repo_root / "systemd" / "pidrive-wifi-recover.service"
    timer = repo_root / "systemd" / "pidrive-wifi-recover.timer"
    assert script.is_file()
    assert unit.is_file()
    assert timer.is_file()
    text = script.read_text()
    assert "wlan0" in text
    assert "rfkill" in text
