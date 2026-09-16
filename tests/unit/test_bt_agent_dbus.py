"""BF-A: bt_agent_dbus Entscheidungslogik (ohne BlueZ)."""
from __future__ import annotations

import runpy
from pathlib import Path


def test_bt_agent_dbus_selftest():
    script = Path(__file__).resolve().parents[2] / "pidrive" / "modules" / "bluetooth" / "bt_agent_dbus.py"
    # --selftest exits 0 on success
    ns = runpy.run_path(str(script), run_name="not_main")
    assert ns["decide_confirm"]("always", 0, False)[0] is True
    assert ns["decide_confirm"]("never", 99, False)[0] is False
    assert ns["decide_confirm"]("window", 0, False)[0] is False
    assert ns["decide_confirm"]("window", 10, False)[0] is True


def test_selftest_cli_exit_zero(monkeypatch, capsys):
    import sys
    from modules.bluetooth import bt_agent_dbus as m
    monkeypatch.setattr(sys, "argv", ["bt_agent_dbus.py", "--selftest"])
    # call selbsttest directly
    assert m.selbsttest() == 0
