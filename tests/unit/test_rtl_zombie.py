"""TK-A: Zombie-rtl_fm zählt nicht als Geräte-Belegung."""
from __future__ import annotations

from test_suite import filter_live_rtl_procs


def test_filter_drops_defunct_cmd():
    procs = [
        {"pid": 1, "cmd": "rtl_fm -f 100M", "stat": "S"},
        {"pid": 2, "cmd": "[rtl_fm] <defunct>", "stat": "Z"},
    ]
    live = filter_live_rtl_procs(procs)
    assert len(live) == 1
    assert live[0]["pid"] == 1


def test_filter_drops_stat_z():
    procs = [
        {"pid": 3, "cmd": "rtl_fm", "stat": "Z+"},
        {"pid": 4, "cmd": "welle-cli", "stat": "Rl"},
    ]
    live = filter_live_rtl_procs(procs)
    assert [p["pid"] for p in live] == [4]


def test_filter_empty():
    assert filter_live_rtl_procs([]) == []
    assert filter_live_rtl_procs(None) == []
