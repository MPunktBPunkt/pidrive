"""State-Machine vs Spektrum-Capture und PMR-Dauerdetektor."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import modules.source_state as ss
from modules.radio import scanner


def _reset(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "STATE_FILE", str(tmp_path / "src.json"))
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
            "play_gen": 0,
        })


# ── Spektrum-Gate ────────────────────────────────────────────────────────────

def test_spectrum_gate_ok_when_idle(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "is_pmr_monitor_running", lambda: False)
    ok, why = ss.rtl_capture_gate()
    assert ok is True
    assert why == ""


def test_spectrum_gate_blocks_active_transition(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    assert ss.begin_transition("webui:play_fm", "fm") is True
    ok, why = ss.rtl_capture_gate(check_monitor=False)
    assert ok is False
    assert "wechselt" in why


def test_spectrum_gate_blocks_rtl_source(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    ss.commit_source("dab")
    ok, why = ss.rtl_capture_gate(check_monitor=False)
    assert ok is False
    assert "dab" in why


def test_spectrum_gate_blocks_pmr_monitor(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "is_pmr_monitor_running", lambda: True)
    ok, why = ss.rtl_capture_gate()
    assert ok is False
    assert "PMR-Monitor" in why


def test_spectrum_gate_blocks_monitor_via_status_file(tmp_path, monkeypatch):
    """CLI/Web: kein Core-Thread — Gate liest /tmp/pidrive_pmr_monitor.json."""
    _reset(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "is_pmr_monitor_running", lambda: False)
    mon = tmp_path / "pmr.json"
    mon.write_text('{"running": true, "last_event": "scan"}')
    # Gate hardcodes /tmp/... — patch open path via monkeypatch on json path check
    real_open = open

    def fake_open(path, *a, **k):
        if str(path) == "/tmp/pidrive_pmr_monitor.json":
            return real_open(mon, *a, **k)
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open)
    ok, why = ss.rtl_capture_gate()
    assert ok is False
    assert "PMR-Monitor" in why


def test_spectrum_does_not_mutate_source_on_gate(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    ss.commit_source("webradio")
    before = ss.snapshot()
    ss.rtl_capture_gate(check_monitor=False)
    after = ss.snapshot()
    assert after["source_current"] == before["source_current"]
    assert after["transition"] == before["transition"]


# ── PMR-Monitor Transitionen ─────────────────────────────────────────────────

def test_refresh_keeps_hold_alive_past_stale(tmp_path, monkeypatch):
    """Hold 15s > STALE 12s: ohne refresh würde der Watchdog abbrechen."""
    _reset(tmp_path, monkeypatch)
    owner = "pmr_monitor:pmr446"
    assert ss.begin_transition(owner, "scanner") is True
    ss.commit_source("scanner")
    assert ss.snapshot()["transition"] is True

    # Simuliere Hold länger als STALE, mit periodischem refresh
    with ss._LOCK:
        ss.STATE["since"] = time.time() - (ss.STALE_TIMEOUT_S - 1)
    assert ss.refresh_transition(owner) is True
    # Nach refresh: trotz „Alter“ vor dem refresh noch aktiv
    assert ss.in_transition() is True
    assert ss.check_stale_transition() is False


def test_without_refresh_stale_clears_during_long_hold(tmp_path, monkeypatch):
    """Regression-Nachweis: ohne refresh löscht der Watchdog die Transition."""
    _reset(tmp_path, monkeypatch)
    assert ss.begin_transition("pmr_monitor:pmr446", "scanner") is True
    ss.commit_source("scanner")
    with ss._LOCK:
        ss.STATE["since"] = time.time() - (ss.STALE_TIMEOUT_S + 1)
    assert ss.check_stale_transition() is True
    assert ss.snapshot()["transition"] is False


def test_tune_blocked_when_other_transition_active(tmp_path, monkeypatch):
    _reset(tmp_path, monkeypatch)
    assert ss.begin_transition("webui:play_dab", "dab") is True
    # Monitor darf nicht überschreiben
    assert ss.begin_transition("pmr_monitor:pmr446", "scanner") is False
    assert ss.snapshot()["owner"] == "webui:play_dab"


def test_monitor_pauses_logic_when_in_transition(tmp_path, monkeypatch):
    """Schleifen-Guard: bei Transition keine Capture-Runde."""
    _reset(tmp_path, monkeypatch)
    assert ss.begin_transition("webui:play_fm", "fm") is True
    # Entspricht _pmr_monitor_loop: if in_transition: continue
    assert ss.in_transition() is True


def test_preempt_commit_idle_after_foreign_source(tmp_path, monkeypatch):
    """Monitor verdrängt DAB → idle (ohne hängende Transition)."""
    _reset(tmp_path, monkeypatch)
    ss.begin_transition("webui:play_dab", "dab")
    ss.commit_source("dab", auto_end=True)
    assert ss.current_source() == "dab"
    ss.commit_source("idle")
    assert ss.current_source() == "idle"
    assert ss.snapshot()["transition"] is False


def test_autotune_happy_path_transition_cycle(tmp_path, monkeypatch):
    """begin → commit scanner → refresh → end → idle-ready."""
    _reset(tmp_path, monkeypatch)
    owner = "pmr_monitor:pmr446"
    assert ss.begin_transition(owner, "scanner") is True
    ss.commit_source("scanner")
    assert ss.current_source() == "scanner"
    assert ss.refresh_transition(owner) is True
    ss.end_transition()
    assert ss.snapshot()["transition"] is False
    # Nach Listen-Ende: Capture wieder erlaubt (Monitor-Check aus)
    ok, _ = ss.rtl_capture_gate(check_monitor=False)
    assert ok is False  # source noch scanner
    ss.commit_source("idle")
    ok, _ = ss.rtl_capture_gate(check_monitor=False)
    assert ok is True


# ── Spektrum / klassischer Scan (Review-Regressionen) ─────────────────────────

def test_watch_channels_uses_profile_fft_size(monkeypatch):
    """Profil-FFT (PMR 2048) darf nicht am Default-FFTProcessor (512) hängenbleiben."""
    from modules.radio import spectrum as sp
    import dataclasses as dc

    class FakeBackend:
        def capture_iq(self, center_hz, sample_rate, sample_count):
            # U8 IQ: 2 Bytes pro Sample — genug für FFT 2048
            n = max(int(sample_count), 4096) * 2
            return bytes([128] * n)

    watcher = sp.SpectrumWatcher(
        FakeBackend(),
        sp.FFTProcessor(fft_size=512, smoothing_alpha=0.35),
        sp.NoiseEstimator(quantile=0.20),
    )
    profile = dc.replace(
        sp.PMR446_PROFILE,
        channels=list(sp.PMR446_PROFILE.channels[:2]),
        watch_seconds=0.05,
        min_active_frames=1,
    )
    result = watcher.watch_channels(profile, debug=True)
    assert result.debug["fft_size"] == 2048
    assert result.debug["effective_fft_size"] == 2048
    assert result.frames_processed >= 1


def test_scan_next_returns_channel_on_hit(monkeypatch):
    """td_scanner erwartet truthy Return — früher fehlte return ch."""
    S = {}
    hit = {"name": "PMR 1", "freq": 446.00625}
    monkeypatch.setattr(scanner, "_get_spectrum_enabled", lambda s: False)
    monkeypatch.setattr(scanner, "_scan_list", lambda *a, **k: hit)
    monkeypatch.setattr(scanner, "play_freq", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "_set_scanner_label", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "_write_scan_result", lambda *a, **k: None)
    found = scanner.scan_next("pmr446", S, settings={})
    assert found == hit


def test_scan_prev_returns_none_without_hit(monkeypatch):
    S = {}
    monkeypatch.setattr(scanner, "_get_spectrum_enabled", lambda s: False)
    monkeypatch.setattr(scanner, "_scan_list", lambda *a, **k: None)
    monkeypatch.setattr(scanner, "_write_scan_result", lambda *a, **k: None)
    assert scanner.scan_prev("pmr446", S, settings={}) is None
