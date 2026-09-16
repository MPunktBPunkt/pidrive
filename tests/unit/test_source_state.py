"""source_state Transitionen (W7 / Zustandsmaschine)."""
from __future__ import annotations

import time

import modules.source_state as ss


def _reset_state():
    with ss._LOCK:
        ss.STATE.update({
            "source_current": "idle",
            "source_previous": "idle",
            "source_target": "",
            "transition": False,
            "owner": "",
            "since": 0.0,
            "transition_count": 0,
            "stale_cleared": 0,
            "history": [],
            "playback_epoch": 0,
        })


def test_begin_commit_end_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "STATE_FILE", str(tmp_path / "src.json"))
    _reset_state()

    assert ss.begin_transition("test", "webradio") is True
    assert ss.snapshot()["transition"] is True
    assert ss.begin_transition("other", "fm") is False  # blocked

    ss.commit_source("webradio", auto_end=True)
    snap = ss.snapshot()
    assert snap["source_current"] == "webradio"
    assert snap["source_previous"] == "idle"
    assert snap["transition"] is False


def test_stale_watchdog_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "STATE_FILE", str(tmp_path / "src.json"))
    _reset_state()
    assert ss.begin_transition("hang", "dab") is True
    with ss._LOCK:
        ss.STATE["since"] = time.time() - (ss.STALE_TIMEOUT_S + 1)
    assert ss.check_stale_transition() is True
    snap = ss.snapshot()
    assert snap["transition"] is False
    assert snap["stale_cleared"] >= 1


def test_commit_without_auto_end_keeps_transition(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "STATE_FILE", str(tmp_path / "src.json"))
    _reset_state()
    ss.begin_transition("t", "fm")
    ss.commit_source("fm", auto_end=False)
    assert ss.snapshot()["source_current"] == "fm"
    assert ss.snapshot()["transition"] is True
    ss.end_transition()
    assert ss.snapshot()["transition"] is False
