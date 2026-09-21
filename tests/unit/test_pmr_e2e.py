"""PMR/Scanner E2E-Regressionen mit Mock-RTL (ohne Hardware)."""
from __future__ import annotations

import dataclasses as dc
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import modules.source_state as ss
from modules.radio import rtlsdr, scanner


pytest.importorskip("numpy")
from modules.radio import spectrum as sp  # noqa: E402


def _reset_source(tmp_path, monkeypatch):
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


def _iq_noise(n_complex: int) -> bytes:
    # ruhiges U8-IQ (Mittelwert 128)
    return bytes([128] * (max(int(n_complex), 64) * 2))


# ── Nachbarkanal / Best-Channel ──────────────────────────────────────────────

def test_neighbor_bleed_keeps_only_stronger_channel():
    profile = dc.replace(
        sp.PMR446_PROFILE,
        channels=list(sp.PMR446_PROFILE.channels[7:10]),  # PMR8/9/10
        trigger_on_db=14.0,
        min_active_frames=1,
    )
    tracker = sp.ActivityTracker(profile)
    now = time.time()
    # PMR9 stark, PMR8 etwas schwächer (Nachbar)
    ch8, ch9 = profile.channels[0], profile.channels[1]
    tracker.update_channel(now, ch8, -10.0, 20.0)
    tracker.update_channel(now, ch9, -5.0, 28.0)
    cands = tracker.build_candidates(now)
    assert cands
    assert cands[0].channel_name == "PMR9"
    names = {c.channel_name for c in cands}
    assert "PMR8" not in names  # schwächerer Nachbar unterdrückt


# ── Capture-Lease / Recovery ─────────────────────────────────────────────────

def test_capture_lease_blocks_second_owner(monkeypatch):
    rtlsdr.release_capture()
    assert rtlsdr.claim_capture("a", timeout_s=0.2) is True
    assert rtlsdr.claim_capture("b", timeout_s=0.15) is False
    rtlsdr.release_capture("a")
    assert rtlsdr.claim_capture("b", timeout_s=0.2) is True
    rtlsdr.release_capture("b")


def test_owner_file_cross_process_and_same_pid(tmp_path, monkeypatch):
    owner_path = str(tmp_path / "owner.json")
    monkeypatch.setattr(rtlsdr, "OWNER_FILE", owner_path)
    rtlsdr.release_owner()
    assert rtlsdr.request_owner("core", mode="spectrum_capture", timeout_s=0.2)
    snap = rtlsdr.get_owner()
    assert snap["disk_owner"] == "core"
    assert snap["mem_owner"] == "core"
    # gleicher PID darf Datei-Owner umlabeln, In-Prozess-Lease blockiert anderen Owner
    rtlsdr.release_owner("core")
    rtlsdr.announce_owner("pmr_monitor", mode="pmr_monitor")
    assert rtlsdr.get_owner()["disk_owner"] == "pmr_monitor"
    assert rtlsdr.request_owner("spectrum:x", mode="spectrum_capture", timeout_s=0.3)
    assert rtlsdr.get_owner()["disk_owner"] == "spectrum:x"
    rtlsdr.release_owner("spectrum:x")


def test_recover_hard_clears_owner_file(tmp_path, monkeypatch):
    owner_path = str(tmp_path / "owner.json")
    lock_path = str(tmp_path / "lock")
    state_path = str(tmp_path / "state.json")
    monkeypatch.setattr(rtlsdr, "OWNER_FILE", owner_path)
    monkeypatch.setattr(rtlsdr, "LOCK_FILE", lock_path)
    monkeypatch.setattr(rtlsdr, "STATE_FILE", state_path)
    monkeypatch.setattr(rtlsdr, "wait_until_free", lambda **k: False)
    monkeypatch.setattr(rtlsdr, "is_busy", lambda: False)
    monkeypatch.setattr(rtlsdr, "_run", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(rtlsdr, "clear_stale_lock", lambda: None)
    rtlsdr.announce_owner("stale", mode="recover")
    assert (tmp_path / "owner.json").exists()
    out = rtlsdr.recover_busy_device(reason="t", level="hard")
    assert out.get("ok") is True
    assert not (tmp_path / "owner.json").exists()
    assert rtlsdr.get_owner()["mem_owner"] == ""


def test_recover_reset_respects_cooldown(monkeypatch):
    monkeypatch.setattr(rtlsdr, "wait_until_free", lambda **k: False)
    monkeypatch.setattr(rtlsdr, "is_busy", lambda: True)
    monkeypatch.setattr(rtlsdr, "_run", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(rtlsdr, "clear_stale_lock", lambda: None)
    called = {"n": 0}

    def fake_reset():
        called["n"] += 1
        return {"ok": True, "steps": ["fake"]}

    monkeypatch.setattr(rtlsdr, "usb_reset", fake_reset)
    monkeypatch.setattr(rtlsdr, "_LAST_USB_RESET_TS", time.time())
    r1 = rtlsdr.recover_busy_device(reason="t", level="reset", force_reset=False)
    assert r1.get("skipped_reset_cooldown") is True
    assert called["n"] == 0
    r2 = rtlsdr.recover_busy_device(reason="t", level="reset", force_reset=True)
    assert called["n"] == 1
    assert r2.get("ok") is True


# ── watch_channels Block-Capture / FFT ───────────────────────────────────────

def test_watch_channels_block_capture_one_rtl_call():
    calls = {"n": 0}

    class FakeBackend:
        def capture_iq(self, center_hz, sample_rate, sample_count):
            calls["n"] += 1
            return _iq_noise(sample_count)

    watcher = sp.SpectrumWatcher(
        FakeBackend(),
        sp.FFTProcessor(fft_size=512, smoothing_alpha=0.35),
        sp.NoiseEstimator(quantile=0.20),
    )
    profile = dc.replace(
        sp.PMR446_PROFILE,
        channels=list(sp.PMR446_PROFILE.channels[:4]),
        watch_seconds=0.25,
        min_active_frames=1,
        trigger_on_db=40.0,  # nur Noise → kein Hit
    )
    result = watcher.watch_channels(profile, debug=True)
    assert calls["n"] == 1  # Pro-Watch, nicht Pro-Frame
    assert result.debug.get("capture_mode") == "block"
    assert result.debug.get("effective_fft_size") == 2048
    assert result.frames_processed >= 1
    assert result.found is False


def test_watch_channels_stream_mode_with_mock_reader(monkeypatch):
    reads = {"n": 0}

    class FakeStream:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read_u8_iq(self, sample_count):
            reads["n"] += 1
            return _iq_noise(sample_count)

    monkeypatch.setattr(sp, "StreamingRtlReader", FakeStream)
    monkeypatch.setenv("PIDRIVE_SPECTRUM_STREAM", "1")

    class BlockBackend(sp.RTLSDRBackend):
        def capture_iq(self, center_hz, sample_rate, sample_count):
            raise AssertionError("block fallback should not run")

    watcher = sp.SpectrumWatcher(
        BlockBackend(),
        sp.FFTProcessor(fft_size=512, smoothing_alpha=0.35),
        sp.NoiseEstimator(quantile=0.20),
    )
    profile = dc.replace(
        sp.PMR446_PROFILE,
        channels=list(sp.PMR446_PROFILE.channels[:4]),
        watch_seconds=0.12,
        frame_ms=40,
        min_active_frames=1,
        trigger_on_db=40.0,
    )
    result = watcher.watch_channels(profile, debug=True)
    assert result.debug.get("capture_mode") == "stream"
    assert reads["n"] >= 1
    assert result.frames_processed >= 1

def test_pmr_monitor_loop_records_activity_without_tune(tmp_path, monkeypatch):
    _reset_source(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "PMR_MONITOR_STATUS", str(tmp_path / "pmr.json"))
    monkeypatch.setattr(scanner, "PMR_MONITOR_LOG", str(tmp_path / "pmr.jsonl"))
    monkeypatch.setattr(scanner, "PMR_MONITOR_IDLE_GAP_S", 0.01)
    monkeypatch.setattr(scanner, "PMR_MONITOR_START_SETTLE_S", 0.01)

    hit = sp.PeakCandidate(
        freq_hz=446.10625e6,
        score=30.0,
        confidence=0.9,
        power_db=-5.0,
        relative_db=30.0,
        timestamp=time.time(),
        source="channel",
        channel_name="PMR9",
        bandwidth_hz=12500,
        active_frames=2,
    )
    det = sp.DetectionResult(
        found=True,
        best_candidate=hit,
        candidates=[hit],
        frames_processed=3,
        watch_started_ts=time.time() - 0.5,
        watch_ended_ts=time.time(),
        debug={"scores": [{"channels": {"PMR9": 30.0}}], "effective_fft_size": 2048},
    )

    class FakeWatcher:
        def watch_channels(self, profile, debug=False):
            scanner._monitor_stop.set()  # nach einem Zyklus stoppen
            return det

    class FakeSpectrum:
        PMR446_PROFILE = sp.PMR446_PROFILE

        @staticmethod
        def build_default_watcher(ppm=0, gain=-1):
            return FakeWatcher()

    monkeypatch.setattr(scanner, "_spectrum", FakeSpectrum)
    monkeypatch.setattr(scanner, "_get_spectrum_profile_for_band",
                        lambda b: sp.PMR446_PROFILE)
    monkeypatch.setattr(scanner, "_get_pmr_monitor_gain", lambda s: 36)
    monkeypatch.setattr(scanner, "_get_ppm", lambda s: 0)
    monkeypatch.setattr(scanner, "_src_state", ss)
    monkeypatch.setattr(scanner, "_rtlsdr", None)

    S = {"radio_type": "", "radio_playing": False}
    scanner._monitor_stop.clear()
    scanner._pmr_monitor_loop(
        S, {}, "pmr446",
        autotune=False, hold_s=1.0, watch_s=0.2,
        trigger_on_db=18.0, trigger_off_db=12.0,
    )
    st = scanner.get_pmr_monitor_status()
    assert int(st.get("activity_count") or 0) >= 1
    assert st.get("last_ch") == 9
    assert float(st.get("last_relative_db") or 0) >= 18.0
    log = (tmp_path / "pmr.jsonl").read_text()
    assert '"event":"activity"' in log


def test_pmr_monitor_autotune_sets_channel(tmp_path, monkeypatch):
    _reset_source(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "PMR_MONITOR_STATUS", str(tmp_path / "pmr.json"))
    monkeypatch.setattr(scanner, "PMR_MONITOR_LOG", str(tmp_path / "pmr.jsonl"))
    monkeypatch.setattr(scanner, "PMR_MONITOR_IDLE_GAP_S", 0.01)
    monkeypatch.setattr(scanner, "PMR_MONITOR_LISTEN_END_SETTLE_S", 0.01)

    hit = sp.PeakCandidate(
        freq_hz=446.04375e6,
        score=40.0,
        confidence=1.0,
        power_db=-2.0,
        relative_db=40.0,
        timestamp=time.time(),
        source="channel",
        channel_name="PMR4",
        bandwidth_hz=12500,
        active_frames=2,
    )
    det = sp.DetectionResult(
        found=True,
        best_candidate=hit,
        candidates=[hit],
        frames_processed=2,
        watch_started_ts=time.time() - 0.4,
        watch_ended_ts=time.time(),
        debug={"scores": []},
    )

    class FakeWatcher:
        def watch_channels(self, profile, debug=False):
            return det

    class FakeSpectrum:
        @staticmethod
        def build_default_watcher(ppm=0, gain=-1):
            return FakeWatcher()

    tuned = []

    def fake_set_channel(band, ch, S, settings=None):
        tuned.append(ch)
        scanner._monitor_stop.set()

    monkeypatch.setattr(scanner, "_spectrum", FakeSpectrum)
    monkeypatch.setattr(scanner, "_get_spectrum_profile_for_band",
                        lambda b: sp.PMR446_PROFILE)
    monkeypatch.setattr(scanner, "_get_pmr_monitor_gain", lambda s: 36)
    monkeypatch.setattr(scanner, "_get_ppm", lambda s: 0)
    monkeypatch.setattr(scanner, "set_channel", fake_set_channel)
    monkeypatch.setattr(scanner, "stop", lambda S: None)
    monkeypatch.setattr(scanner, "_src_state", ss)
    monkeypatch.setattr(scanner, "_rtlsdr", None)

    S = {"radio_type": "", "radio_playing": False}
    scanner._monitor_stop.clear()
    scanner._pmr_monitor_loop(
        S, {}, "pmr446",
        autotune=True, hold_s=0.05, watch_s=0.2,
        trigger_on_db=18.0, trigger_off_db=12.0,
    )
    assert tuned == [4]
    assert ss.current_source() in ("scanner", "idle")  # nach listen_end oft idle via stop path


# ── Gate / Preempt ───────────────────────────────────────────────────────────

def test_rtl_capture_gate_blocks_running_monitor(tmp_path, monkeypatch):
    _reset_source(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "is_pmr_monitor_running", lambda: True)
    ok, why = ss.rtl_capture_gate()
    assert ok is False
    assert "PMR" in why


def test_preempt_monitor_logic_stops_when_requested(tmp_path, monkeypatch):
    """Spiegel der Web-API: bei Monitor-Block und preempt=1 → Stop-Trigger."""
    _reset_source(tmp_path, monkeypatch)
    monkeypatch.setattr(scanner, "is_pmr_monitor_running", lambda: True)
    ok, why = ss.rtl_capture_gate()
    assert not ok and "PMR" in why
    triggers = []

    def fake_append(cmd):
        triggers.append(cmd)
        monkeypatch.setattr(scanner, "is_pmr_monitor_running", lambda: False)

    # nach Stop ist Gate wieder frei
    fake_append("pmr_monitor_stop")
    ok2, _ = ss.rtl_capture_gate()
    assert ok2 is True
    assert triggers == ["pmr_monitor_stop"]


# ── scan_setch Source-Commit ─────────────────────────────────────────────────

def test_scan_setch_commits_scanner_source(tmp_path, monkeypatch):
    _reset_source(tmp_path, monkeypatch)
    from trigger import td_scanner

    S = {"radio_type": "", "radio_playing": False, "radio_station": ""}
    settings = {}
    ran = []

    def immediate_bg(fn):
        fn()
        ran.append(True)

    monkeypatch.setattr(td_scanner, "_stop_other_sources", lambda S: None)
    monkeypatch.setattr(td_scanner, "_clear_scanner_metadata", lambda S: None)
    monkeypatch.setattr(scanner, "set_channel", lambda *a, **k: None)

    td_scanner.handle(
        "scan_setch:pmr446:7",
        menu_state=None,
        store=None,
        S=S,
        settings=settings,
        bg=immediate_bg,
    )
    assert ran
    assert ss.current_source() == "scanner"
    assert S.get("scanner_band") == "pmr446"
