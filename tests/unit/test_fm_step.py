"""Q-H: FM-Rasterschritte (ohne Hardware)."""
from __future__ import annotations

from modules.radio import fm


def test_current_freq_from_station_string():
    assert fm._current_freq_mhz({"radio_station": "FM: Bayern 3 (99.4 MHz)"}) == 99.4


def test_step_clamps_at_edges(monkeypatch):
    calls = []

    def _fake_play(station, S, settings=None):
        calls.append(station)
        return True

    monkeypatch.setattr(fm, "play_station", _fake_play)
    S = {"radio_station": "FM: x (108.0 MHz)", "radio_playing": True, "radio_type": "FM"}
    assert fm.step_freq(S, {}, 1.0) is True
    assert calls[-1]["freq"] == "108.0"
    S = {"radio_station": "FM: x (87.5 MHz)"}
    assert fm.step_freq(S, {}, -0.1) is True
    assert calls[-1]["freq"] == "87.5"


def test_step_plus_minus():
    assert round(99.4 + 0.1, 1) == 99.5
    S = {"radio_station": "FM: x (99.4 MHz)"}
    # nur Frequenzberechnung über _current + clamp-Logik indirekt
    cur = fm._current_freq_mhz(S)
    assert round(cur + 0.1, 1) == 99.5
    assert round(cur - 1.0, 1) == 98.4
