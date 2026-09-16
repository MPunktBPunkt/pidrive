"""Menü-Vertrag und iDrive-Offline-Skripte."""
from __future__ import annotations

from pathlib import Path

from menu import idrive_sim, menu_golden


def test_menu_verify_no_losses():
    assert menu_golden.cmd_verify() == 0


def test_menu_lint_no_errors():
    # Warnungen (doppelte Config-IDs) sind bekannt; Exit 0 = keine harten Fehler
    assert menu_golden.cmd_lint() == 0


def test_menu_rebuild_keeps_cursor():
    assert menu_golden.cmd_rebuild_test() == 0


def test_idrive_rockfm_offline(repo_root: Path):
    script = repo_root / "tests" / "idrive" / "rockfm.txt"
    assert script.is_file()
    assert idrive_sim.run_script(str(script), offline=True) == 0
