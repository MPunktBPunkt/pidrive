"""
modules/scanner.py — VHF/UHF/CB-Scanner via rtl_fm (ALSA-direkt)
Aufrufer: main_core.py
Abhängig von: modules/audio.py, modules/source_state.py, ipc.py

Kompatibilität:
- API-kompatibel zu main_core.py
- Bestehende Funktionen bleiben erhalten:
  play_freq, stop, scan_next, scan_prev,
  channel_up, channel_down, channel_jump,
  freq_step, set_freq, freq_input_screen

Erweiterungen:
- robusteres Logging
- optionale spectrum-basierte Kandidatensuche für PMR446/Freenet
- Fallback auf bisherigen Fast/Confirm-Scanner
"""

import json
import os
import threading
import time
import subprocess
from datetime import datetime, timezone

try:
    from modules.radio import rtlsdr as _rtlsdr
except Exception as _e:
    _rtlsdr = None
    try:
        from modules import degraded_imports as _deg
        _deg.report("modules.radio.rtlsdr", str(_e))
    except Exception:
        pass

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

try:
    from modules.radio import spectrum as _spectrum
except Exception as _e:
    _spectrum = None
    try:
        from modules import degraded_imports as _deg
        _deg.report("modules.radio.spectrum", str(_e))
    except Exception:
        pass

import ipc
import log


# ── Kanaltabellen ────────────────────────────────────────────────────────────

# PMR446d: 16 Kanäle · 446.00625–446.19375 MHz · 12.5 kHz (EU seit Erweiterung;
# klassische 8-Kanal-Geräte wie TLKR T40 nutzen K1–K8 derselben Tabelle)
PMR446_CHANNELS = [
    {"ch": i + 1, "name": f"PMR Kanal {i+1}",
     "freq": round(446.00625 + i * 0.01250, 5)}
    for i in range(16)
]

FREENET_CHANNELS = [
    {"ch": 1, "name": "Freenet K1", "freq": 149.02500},
    {"ch": 2, "name": "Freenet K2", "freq": 149.03750},
    {"ch": 3, "name": "Freenet K3", "freq": 149.05000},
    {"ch": 4, "name": "Freenet K4", "freq": 149.08750},
    {"ch": 5, "name": "Freenet K5", "freq": 149.10000},
    {"ch": 6, "name": "Freenet K6", "freq": 149.11250},
]

LPD433_CHANNELS = [
    {"ch": i + 1, "name": f"LPD K{i+1:02d}",
     "freq": round(433.075 + i * 0.025, 3)}
    for i in range(69)
]

CB_CHANNELS = (
    [{"ch": 41 + i, "name": f"CB Kanal {41+i:02d}",
      "freq": round(26.565 + i * 0.010, 3)} for i in range(40)] +
    [
        {"ch": 1, "name": "CB Kanal 01", "freq": 26.965},
        {"ch": 2, "name": "CB Kanal 02", "freq": 26.975},
        {"ch": 3, "name": "CB Kanal 03", "freq": 26.985},
        {"ch": 4, "name": "CB Kanal 04", "freq": 27.005},
        {"ch": 5, "name": "CB Kanal 05", "freq": 27.015},
        {"ch": 6, "name": "CB Kanal 06", "freq": 27.025},
        {"ch": 7, "name": "CB Kanal 07", "freq": 27.035},
        {"ch": 8, "name": "CB Kanal 08", "freq": 27.055},
        {"ch": 9, "name": "CB Kanal 09", "freq": 27.065},
        {"ch": 10, "name": "CB Kanal 10", "freq": 27.075},
        {"ch": 11, "name": "CB Kanal 11", "freq": 27.085},
        {"ch": 12, "name": "CB Kanal 12", "freq": 27.105},
        {"ch": 13, "name": "CB Kanal 13", "freq": 27.115},
        {"ch": 14, "name": "CB Kanal 14", "freq": 27.125},
        {"ch": 15, "name": "CB Kanal 15", "freq": 27.135},
        {"ch": 16, "name": "CB Kanal 16", "freq": 27.155},
        {"ch": 17, "name": "CB Kanal 17", "freq": 27.165},
        {"ch": 18, "name": "CB Kanal 18", "freq": 27.175},
        {"ch": 19, "name": "CB Kanal 19", "freq": 27.185},
        {"ch": 20, "name": "CB Kanal 20", "freq": 27.205},
        {"ch": 21, "name": "CB Kanal 21", "freq": 27.215},
        {"ch": 22, "name": "CB Kanal 22", "freq": 27.225},
        {"ch": 23, "name": "CB Kanal 23", "freq": 27.255},
        {"ch": 24, "name": "CB Kanal 24", "freq": 27.235},
        {"ch": 25, "name": "CB Kanal 25", "freq": 27.245},
        {"ch": 26, "name": "CB Kanal 26", "freq": 27.265},
        {"ch": 27, "name": "CB Kanal 27", "freq": 27.275},
        {"ch": 28, "name": "CB Kanal 28", "freq": 27.285},
        {"ch": 29, "name": "CB Kanal 29", "freq": 27.295},
        {"ch": 30, "name": "CB Kanal 30", "freq": 27.305},
        {"ch": 31, "name": "CB Kanal 31", "freq": 27.315},
        {"ch": 32, "name": "CB Kanal 32", "freq": 27.325},
        {"ch": 33, "name": "CB Kanal 33", "freq": 27.335},
        {"ch": 34, "name": "CB Kanal 34", "freq": 27.345},
        {"ch": 35, "name": "CB Kanal 35", "freq": 27.355},
        {"ch": 36, "name": "CB Kanal 36", "freq": 27.365},
        {"ch": 37, "name": "CB Kanal 37", "freq": 27.375},
        {"ch": 38, "name": "CB Kanal 38", "freq": 27.385},
        {"ch": 39, "name": "CB Kanal 39", "freq": 27.395},
        {"ch": 40, "name": "CB Kanal 40", "freq": 27.405},
    ]
)

VHF_RANGE = {
    "min": 136.0,
    "max": 174.0,
    "step_fine": 0.025,
    "label": "VHF (136-174 MHz)",
    "short": "VHF",
}

UHF_RANGE = {
    "min": 400.0,
    "max": 470.0,
    "step_fine": 0.025,
    "label": "UHF (400-470 MHz)",
    "short": "UHF",
}


# ── Band-Konfiguration ───────────────────────────────────────────────────────

BANDS = {
    "pmr446": {
        "channels": PMR446_CHANNELS,
        "bw": 12500,
        "label": "PMR446",
    },
    "freenet": {
        "channels": FREENET_CHANNELS,
        "bw": 12500,
        "label": "Freenet",
    },
    "lpd433": {
        "channels": LPD433_CHANNELS,
        "bw": 12500,
        "label": "LPD433",
    },
    "vhf": {
        "band": {**VHF_RANGE, "start": VHF_RANGE["min"],
                 "step_coarse": 1.0, "step_fine": 0.025, "step": 0.025},
        "bw": 25000,
        "label": "VHF",
    },
    "uhf": {
        "band": {**UHF_RANGE, "start": UHF_RANGE["min"],
                 "step_coarse": 1.0, "step_fine": 0.025, "step": 0.025},
        "bw": 25000,
        "label": "UHF",
    },
    "cb": {
        "channels": CB_CHANNELS,
        "bw": 10000,
        "label": "CB-Funk",
    },
    "fm": {
        "band": {
            "min": 87.5, "max": 108.0, "start": 87.5,
            "step_fine": 0.1, "step_coarse": 1.0, "step": 0.1,
            "label": "FM/UKW (87.5-108 MHz)", "short": "FM",
        },
        "bw": 200000,
        "label": "FM/UKW",
    },
}

_current_ch: dict = {}


# ── Player / Zustand ─────────────────────────────────────────────────────────

_player_proc = None
_scan_abort = False
SQUELCH = 50  # UHF/PMR: 25 ließ Dauerrauschen durch; 50 mute bis Träger

# Ergebnis eines Suchlaufs (für CLI/WebUI-Rückmeldung)
SCAN_RESULT_FILE = "/tmp/pidrive_scan_result.json"


def _write_scan_result(band_id, found, name="", freq=None):
    """Suchlauf-Ergebnis in eine kleine JSON-Datei schreiben.
    Wird von `pidrivectl scanner BAND scan` gepollt, um zurückzumelden
    ob/wohin gewechselt wurde."""
    try:
        import json as _j
        with open(SCAN_RESULT_FILE, "w", encoding="utf-8") as f:
            _j.dump({
                "band":  band_id,
                "found": bool(found),
                "name":  name,
                "freq":  freq,
                "ts":    time.time(),
            }, f)
    except Exception:
        pass


# ── Settings Helper ──────────────────────────────────────────────────────────

def _get_squelch(settings=None):
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            return SQUELCH
    return int(settings.get("scanner_squelch", SQUELCH))


def _get_ppm(settings=None):
    try:
        if settings is None:
            from settings import load_settings
            settings = load_settings()
        return int(settings.get("ppm_correction", 0))
    except Exception:
        return 0


def _get_gain(settings=None):
    try:
        if settings is None:
            from settings import load_settings
            settings = load_settings()
        return int(settings.get("scanner_gain", -1))
    except Exception:
        return -1


def _get_pmr_monitor_gain(settings=None):
    """PMR-Monitor: Auto(-1) durch festen Gain ersetzen (Nahfeld-Walkie)."""
    g = _get_gain(settings)
    if g < 0:
        return PMR_MONITOR_DEFAULT_GAIN
    return g


def _get_spectrum_enabled(settings=None):
    """
    Optionales Flag für experimentellen Spectrum-Scanner.
    Default: False, damit bestehendes Verhalten unverändert bleibt.
    """
    try:
        if settings is None:
            from settings import load_settings
            settings = load_settings()
        return bool(settings.get("scanner_use_spectrum", False))
    except Exception:
        return False


def _get_spectrum_debug(settings=None):
    try:
        if settings is None:
            from settings import load_settings
            settings = load_settings()
        return bool(settings.get("scanner_spectrum_debug", False))
    except Exception:
        return False


# ── Shell Helper ─────────────────────────────────────────────────────────────

def _bg(cmd):
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def _run(cmd, capture=False, timeout=5):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return r.stdout.strip() if capture else (r.returncode == 0)
    except Exception:
        return "" if capture else False


def is_rtlsdr_available():
    return bool(_run("lsusb 2>/dev/null | grep -iE 'rtl|2832|2838|0bda'", capture=True))


def is_rtlfm_available():
    return _run("which rtl_fm 2>/dev/null")


def check_hardware(screen=None):
    if not is_rtlsdr_available():
        ipc.write_progress("RTL-SDR", "Kein Stick gefunden!")
        time.sleep(2)
        return False
    if not is_rtlfm_available():
        ipc.write_progress("rtl_fm fehlt", "sudo apt install rtl-sdr")
        time.sleep(3)
        return False
    return True


# ── Audio / Playback ─────────────────────────────────────────────────────────

def play_freq(freq_mhz, name, bandwidth_hz, S, settings=None):
    global _player_proc

    if not check_hardware():
        S["radio_station"] = "Scanner-Hardware fehlt"
        S["scanner"] = {"active": False, "error": "hardware"}
        return

    if _rtlsdr and not _rtlsdr.detect_usb()["present"]:
        S["radio_station"] = "RTL-SDR nicht gefunden"
        return

    # Transition nur durch Aufrufer (td_scanner) — play_freq öffnet keine eigene.
    # Früher: begin_transition(..., reason=) → TypeError, verschluckt (C7).

    stop(S)

    if _rtlsdr and hasattr(_rtlsdr, "request_owner"):
        try:
            if not _rtlsdr.request_owner(
                "scanner_audio", mode="scanner_audio", timeout_s=3.0
            ):
                log.warn("Scanner: RTL-Owner belegt — Audio startet trotzdem")
        except Exception:
            pass

    _ppm = _get_ppm(settings)
    _gain = _get_gain(settings)
    _ppm_arg = f" -p {_ppm}" if _ppm else ""
    _gain_arg = f" -g {_gain}" if _gain != -1 else ""

    freq_hz = int(float(freq_mhz) * 1e6)
    sr = max(48000, int(bandwidth_hz) * 4)

    try:
        from modules.audio import _get_headphone_card as _ghc2
        _sc = _ghc2()

        # BT-Sink ermitteln (wie FM-Radio)
        _bt_sink = ""
        try:
            from modules.bluetooth.bt_audio import get_bt_sink as _gbs_sc
            _bt_sink = _gbs_sc() or ""
        except Exception:
            pass
        _device_arg = f"--audio-device=pulse/{_bt_sink}" if _bt_sink else ""
        _sc_mpv_env    = "PULSE_SERVER=unix:/var/run/pulse/native XDG_RUNTIME_DIR=/tmp"
        _sc_mpv_prefix = _sc_mpv_env + " "
        # Squelch aus Settings
        _sq = _get_squelch(settings)
        _sq_arg = f" -l {_sq}" if _sq and _sq > 0 else ""

        # FM-Broadcast (wbfm): andere Parameter als Schmalband-FM
        _rtl_extra: list = []
        _mpv_af = None
        if bandwidth_hz >= 150000:
            # Wideband FM — wie fm.py: -M wbfm, fixed rates
            _rtl_sr = 250000
            _out_sr = 32000
            _modulation = "wbfm"
            _sq_eff = _sq
            _gain_eff = _gain
        else:
            # Schmalband (PMR etc.): 24 kHz ohne Resample, FIR, fester Gain
            # Schwach/dünn kam von AGC + -A fast + zu niedrigem Squelch-Rauschen.
            _rtl_sr = 24000
            _out_sr = 24000
            _modulation = "fm"
            _sq_eff = max(int(_sq or 0), 50) if bandwidth_hz <= 25000 else max(int(_sq or 0), 35)
            # AGC (−1) auf UHF oft dünn/rauschig — feste Verstärkung
            _gain_eff = 36 if int(_gain) < 0 else int(_gain)
            _rtl_extra = ["-F", "9", "-A", "std", "-t", "1"]
            # Sprachband + Pegel für Monitor/Klinke
            _mpv_af = "lavfi=[highpass=f=250,lowpass=f=3700,volume=10dB]"

        # Prio C: shell=True → Popen-Pipe
        import os as _sc_os
        rtl_cmd = [
            "rtl_fm", "-M", _modulation,
            "-f", str(freq_hz), "-s", str(_rtl_sr),
        ]
        # -r nur wenn Resample nötig (sonst Qualitätsverlust)
        if _out_sr != _rtl_sr:
            rtl_cmd += ["-r", str(_out_sr)]
        rtl_cmd += _rtl_extra + ["-"]
        if _ppm:
            rtl_cmd += ["-p", str(_ppm)]
        if _gain_eff != -1:
            rtl_cmd += ["-g", str(_gain_eff)]
        if _sq_eff and _sq_eff > 0:
            rtl_cmd += ["-l", str(_sq_eff)]

        mpv_cmd = [
            "mpv", "--no-video", "--no-terminal",
            "--title=pidrive_scanner",
            f"--demuxer=rawaudio",
            f"--demuxer-rawaudio-rate={_out_sr}",
            "--demuxer-rawaudio-channels=1",
            "--audio-channels=mono",
            "--ao=pulse",
            # niedrige Latenz — sonst wirkt Squelch-Öffnen + Monitor träge
            "--cache=no",
            "--demuxer-readahead-secs=0",
            "--untimed=no",
            "--audio-buffer=0.05",
        ]
        if _mpv_af:
            mpv_cmd.append(f"--af={_mpv_af}")
        if _device_arg:
            mpv_cmd.append(_device_arg)
        mpv_cmd.append("-")
        mpv_env = dict(_sc_os.environ,
                       PULSE_SERVER="unix:/var/run/pulse/native",
                       XDG_RUNTIME_DIR="/tmp")

        if _rtlsdr:
            usb = _rtlsdr.detect_usb()
            if not usb.get("present"):
                S["radio_station"] = "RTL-SDR nicht gefunden"
                log.error("Scanner: kein RTL-SDR")
                return
            if _rtlsdr.is_busy():
                S["radio_type"]   = "SCANNER"
                S["source_error"] = "RTL-SDR belegt"
                log.warn("Scanner: RTL-SDR belegt")
                return

        _rtl_proc_sc = subprocess.Popen(
            rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        _mpv_proc_sc = subprocess.Popen(
            mpv_cmd, stdin=_rtl_proc_sc.stdout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=mpv_env
        )
        _rtl_proc_sc.stdout.close()
        _player_proc = _mpv_proc_sc
        if _rtlsdr:
            try: _rtlsdr._proc = _rtl_proc_sc
            except Exception: pass

        S["radio_playing"] = True
        S["radio_station"] = f"{name} ({float(freq_mhz):.5g} MHz)"
        S["radio_type"] = "SCANNER"
        S["scanner"] = {
            "active": True,
            "band": S.get("scanner_band", ""),
            "freq": float(freq_mhz),
            "name": name,
            "squelch": _get_squelch(settings) if settings is not None else S.get("scanner_squelch"),
            "bandwidth_hz": int(bandwidth_hz),
            "sample_rate": int(_rtl_sr),
        }

        if _src_state:
            try:
                _src_state.commit_source("scanner")
            except Exception:
                pass

        log.action("Scanner", f"{name} @ {freq_mhz} MHz")

    except Exception as e:
        log.error(f"Scanner play: {e}")


def stop(S):
    global _player_proc, _scan_abort

    _scan_abort = True
    # PMR-Monitor nur von außen stoppen — nicht aus dem Monitor-Thread selbst
    # (sonst beendet play→stop nach Hold die Überwachung)
    try:
        if (is_pmr_monitor_running()
                and threading.current_thread() is not _monitor_thread):
            stop_pmr_monitor(S, join=False)
    except Exception:
        pass
    log.info("Scanner stop: requested")

    if _rtlsdr:
        try:
            _rtlsdr.stop_process()
        except Exception:
            pass

    _bg("pkill -f pidrive_scanner 2>/dev/null")
    _bg("pkill -f rtl_fm 2>/dev/null")
    # C12: Muster an tatsächliche mpv-Kommandozeile anpassen (--no-terminal, nicht --really-quiet)
    _bg("pkill -f 'mpv --no-video --no-terminal --title=pidrive_scanner' 2>/dev/null")

    if _player_proc:
        try:
            _player_proc.terminate()
            _player_proc.wait(timeout=2.0)   # verhindert Zombie-Prozess
        except Exception:
            try: _player_proc.kill()
            except Exception: pass
        _player_proc = None

    if S.get("radio_type") == "SCANNER":
        S["radio_playing"] = False
        S["radio_station"] = ""
        S["scanner"] = {"active": False}

    if _rtlsdr and hasattr(_rtlsdr, "release_owner"):
        try:
            _rtlsdr.release_owner("scanner_audio")
        except Exception:
            pass

    # end_transition() gehört dem Aufrufer (td_scanner), nicht stop() —
    # sonst beendet jedes Tunen (play_freq→stop) die äußere Transition (C7).

    time.sleep(0.2)
    log.info("Scanner stop: done")


# ── Fast/Confirm Detection ───────────────────────────────────────────────────

def _detect_signal_fast(freq_mhz, bandwidth_hz, timeout_s=1.5, squelch=None, settings=None):
    freq_hz = int(float(freq_mhz) * 1e6)
    if squelch is None:
        squelch = max(5, _get_squelch(settings) // 2)

    _ppm = _get_ppm(settings)
    _gain = _get_gain(settings)
    _ppm_arg = f" -p {_ppm}" if _ppm else ""
    _gain_arg = f" -g {_gain}" if _gain != -1 else ""

    cmd = (
        f"timeout {timeout_s}s rtl_fm -M fm -f {freq_hz} -s {int(bandwidth_hz)} "
        f"-l {int(squelch)}{_ppm_arg}{_gain_arg} - 2>/dev/null | wc -c"
    )

    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s + 1.0
        )
        count = int((r.stdout or "0").strip() or "0")
        log.debug(f"Scanner fast-detect: freq={freq_mhz} bw={bandwidth_hz} bytes={count}")
        return count > 180
    except Exception:
        return False


def _detect_signal_confirm(freq_mhz, bandwidth_hz, timeout_s=1.20, squelch=None, settings=None):
    freq_hz = int(float(freq_mhz) * 1e6)
    if squelch is None:
        squelch = _get_squelch(settings)

    _ppm = _get_ppm(settings)
    _gain = _get_gain(settings)
    _ppm_arg = f" -p {_ppm}" if _ppm else ""
    _gain_arg = f" -g {_gain}" if _gain != -1 else ""

    cmd = (
        f"timeout {timeout_s}s rtl_fm -M fm -f {freq_hz} -s {int(bandwidth_hz)} "
        f"-l {int(squelch)}{_ppm_arg}{_gain_arg} - 2>/dev/null | wc -c"
    )

    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_s + 1.4
        )
        count = int((r.stdout or "0").strip() or "0")
        log.debug(f"Scanner confirm: freq={freq_mhz} bw={bandwidth_hz} bytes={count}")
        return count > 450
    except Exception:
        return False


def _detect_signal(freq_mhz, bandwidth_hz, timeout_s=0.55, settings=None):
    return _detect_signal_confirm(
        freq_mhz,
        bandwidth_hz,
        timeout_s=timeout_s,
        squelch=_get_squelch(settings),
        settings=settings
    )


def _scan_bw_fast(band_id, default_bw):
    if band_id in ("pmr446", "freenet", "lpd433"):
        return 25000
    if band_id == "cb":
        return 20000
    if band_id in ("vhf", "uhf"):
        # C5: Schritt 0.1 MHz → fast_bw muss ≥ 100 kHz sein (sonst Abtastlücken)
        return max(default_bw, 100000)
    return default_bw


def _range_step_fast(band_id, band_cfg):
    if band_id in ("vhf", "uhf"):
        return 0.1
    return band_cfg.get("step_fine", 0.025)


# ── Spectrum-Integration ─────────────────────────────────────────────────────

def _get_spectrum_profile_for_band(band_id):
    if not _spectrum:
        return None
    if band_id == "pmr446" and hasattr(_spectrum, "PMR446_PROFILE"):
        return _spectrum.PMR446_PROFILE
    if band_id == "freenet" and hasattr(_spectrum, "FREENET_PROFILE"):
        return _spectrum.FREENET_PROFILE
    return None


def _scan_list_spectrum(S, band_id, settings=None):
    """
    Optionaler scanner-orientierter Spectrum-Scan.
    Aktuell nur für PMR446/Freenet vorgesehen.
    Gibt kompatibel ein channel-dict wie _scan_list() zurück oder None.
    """
    if not _spectrum:
        return None

    profile = _get_spectrum_profile_for_band(band_id)
    if profile is None:
        return None

    try:
        debug = _get_spectrum_debug(settings)
        watcher = _spectrum.build_default_watcher(
            ppm=_get_ppm(settings),
            gain=_get_gain(settings)
        )
        result = watcher.watch_channels(profile, debug=debug)

        if not result or not result.found or not result.best_candidate:
            log.info(f"Scanner spectrum: kein Kandidat band={band_id}")
            return None

        cand = result.best_candidate
        log.info(
            "Scanner spectrum: candidate "
            f"band={band_id} ch={cand.channel_name} freq={cand.freq_hz/1e6:.6f} "
            f"score={cand.score:.2f} conf={cand.confidence:.2f}"
        )

        freq_mhz = round(float(cand.freq_hz) / 1e6, 6)

        for ch in BANDS.get(band_id, {}).get("channels", []):
            if abs(float(ch["freq"]) - freq_mhz) < 0.00002:
                return ch

        return {
            "name": cand.note or cand.channel_name or f"{band_id.upper()} Kandidat",
            "freq": freq_mhz,
        }

    except Exception as e:
        log.warn(f"Scanner spectrum failed band={band_id}: {e}")
        return None


# ── Scan-Funktionen ──────────────────────────────────────────────────────────

def _scan_list(S, channels, bw, direction, band_id="", settings=None):
    n = len(channels)
    if n == 0:
        return None

    start_idx = _current_ch.get(f"scan_idx:{band_id}" if band_id else "scan_idx",
                                _current_ch.get(band_id, 0))
    idx = start_idx % n
    fast_bw = _scan_bw_fast(band_id, bw)

    for _ in range(n):
        if (_scan_abort
                or (_src_state and _src_state.in_transition())
                or S.get("radio_type") not in ("", "SCANNER")):
            log.info(f"Scanner scan-list: abgebrochen band={band_id} radio_type={S.get('radio_type', '')}")
            return None

        ch = channels[idx]
        freq = ch["freq"]
        name = ch["name"]

        log.info(f"Scanner scan-list: FAST band={band_id} ch={name} freq={freq} bw={fast_bw}")
        if _detect_signal_fast(freq, fast_bw, settings=settings):
            log.info(f"Scanner scan-list: CANDIDATE band={band_id} ch={name} freq={freq}")
            if _detect_signal_confirm(freq, bw, settings=settings):
                log.action("Scanner", f"Signal: {name} @ {freq} MHz")
                if band_id:
                    _current_ch[f"scan_idx:{band_id}"] = idx
                    _current_ch[band_id] = idx
                else:
                    _current_ch["scan_idx"] = idx
                return ch
            else:
                log.info(f"Scanner scan-list: FALSE_POSITIVE band={band_id} ch={name}")

        idx = (idx + direction) % n

    ipc.write_progress("Scan beendet", "Kein Signal", color="orange")
    time.sleep(0.8)
    ipc.clear_progress()
    return None


def _scan_range(S, band, bw, direction, band_id="", settings=None):
    step_fast = _range_step_fast(band_id, band)
    total = max(1, round((band["max"] - band["min"]) / step_fast))
    freq = band.get("start", band["min"])
    fast_bw = _scan_bw_fast(band_id, bw)

    for _ in range(total):
        if (_scan_abort
                or (_src_state and _src_state.in_transition())
                or S.get("radio_type") not in ("", "SCANNER")):
            log.info(f"Scanner scan-range: abgebrochen band={band_id} radio_type={S.get('radio_type', '')}")
            return None

        log.info(f"Scanner scan-range: FAST band={band_id} freq={freq:.3f} bw={fast_bw}")
        if _detect_signal_fast(freq, fast_bw, settings=settings):
            log.info(f"Scanner scan-range: CANDIDATE band={band_id} freq={freq:.3f}")
            if _detect_signal_confirm(freq, bw, settings=settings):
                name = f"{band['short']} {freq:.3f} MHz"
                log.action("Scanner", f"Signal @ {freq:.3f} MHz")
                band["start"] = freq
                return {"name": name, "freq": freq}
            else:
                log.info(f"Scanner scan-range: FALSE_POSITIVE band={band_id} freq={freq:.3f}")

        freq = round(freq + direction * step_fast, 3)
        if freq > band["max"]:
            freq = band["min"]
        elif freq < band["min"]:
            freq = band["max"]

    ipc.write_progress("Scan beendet", "Kein Signal", color="orange")
    time.sleep(0.8)
    ipc.clear_progress()
    return None


# ── UI / Frequenzeingabe ─────────────────────────────────────────────────────

def _freq_input(band):
    freq = band["start"]
    deadline = time.time() + 60
    while time.time() < deadline:
        ipc.write_progress(
            f"{band['short']} Frequenz",
            f"{freq:.3f} MHz  (↑↓ fein  ←→ grob  Enter=OK  Back=Abbruch)",
            color="blue"
        )
        if not os.path.exists(ipc.CMD_FILE):
            time.sleep(0.15)
            continue
        try:
            cmd = open(ipc.CMD_FILE).read().strip()
            os.remove(ipc.CMD_FILE)
        except Exception:
            continue

        if cmd == "up":
            freq = min(band["max"], round(freq + band["step_fine"], 3))
        elif cmd == "down":
            freq = max(band["min"], round(freq - band["step_fine"], 3))
        elif cmd == "right":
            freq = min(band["max"], round(freq + band["step_coarse"], 3))
        elif cmd == "left":
            freq = max(band["min"], round(freq - band["step_coarse"], 3))
        elif cmd == "enter":
            ipc.clear_progress()
            return freq
        elif cmd == "back":
            ipc.clear_progress()
            return None

    ipc.clear_progress()
    return None


def freq_input_screen(band_id, settings=None):
    b = BANDS.get(band_id, {}).get("band", {})
    if not b:
        return None

    freq = b.get("start", b["min"])
    text = f"{freq:.3f}"
    deadline = time.time() + 90

    while time.time() < deadline:
        ipc.write_progress(
            f"{b.get('short', band_id.upper())} Frequenz",
            f"{text} MHz  (↑=1  ↓=0  →=.  ←=Löschen  Enter=OK  Back=Abbruch)",
            color="blue"
        )
        if not os.path.exists(ipc.CMD_FILE):
            time.sleep(0.15)
            continue

        try:
            cmd = open(ipc.CMD_FILE).read().strip()
            os.remove(ipc.CMD_FILE)
        except Exception:
            continue

        if cmd == "up":
            text += "1"
        elif cmd == "down":
            text += "0"
        elif cmd == "right":
            text = text + "." if "." not in text else text
        elif cmd == "left":
            text = text[:-1] if text else ""
        elif cmd == "enter":
            ipc.clear_progress()
            try:
                val = float(text)
                if b["min"] <= val <= b["max"]:
                    return round(val, 3)
            except Exception:
                pass
            ipc.write_progress("Scanner", "Ungültige Frequenz", color="red")
            time.sleep(1.2)
            ipc.clear_progress()
            return None
        elif cmd == "back":
            ipc.clear_progress()
            return None

    ipc.clear_progress()
    return None


# ── Kanal / Frequenz-Steuerung ───────────────────────────────────────────────

def _get_channels(band_id):
    return BANDS.get(band_id, {}).get("channels", [])


def _set_scanner_label(band_id, text, S):
    S[f"scanner_{band_id}"] = text


def _play_channel(band_id, idx, S, settings=None):
    chs = _get_channels(band_id)
    if not chs or idx >= len(chs):
        return
    ch = chs[idx]
    name = ch.get("name", f"K{ch.get('ch', idx+1):02d}")
    freq = ch.get("freq", "")
    S["scanner_band"] = band_id
    S[f"scanner_{band_id}"] = f"{name}  {freq} MHz"
    play_freq(freq, name, BANDS[band_id]["bw"], S, settings=settings)


def _play_band_freq(band_id, freq, S, settings=None):
    b = BANDS.get(band_id, {}).get("band", {})
    if not b:
        return

    freq = max(b["min"], min(b["max"], round(freq, 3)))
    b["start"] = freq
    name = f"{b.get('short', band_id.upper())} {freq:.3f} MHz"
    _set_scanner_label(band_id, name, S)
    log.info(f"Scanner: PLAY_FREQ band={band_id} freq={freq}")
    play_freq(freq, name, BANDS[band_id]["bw"], S, settings=settings)


def set_channel(band_id: str, ch_num: int, S: dict, settings=None):
    """Direkt zu Kanal ch_num springen (1-basiert, nach Feld 'ch')."""
    chs = _get_channels(band_id)
    if not chs:
        log.warn(f"Scanner: set_channel — kein Kanal-Band: {band_id}")
        return
    idx = None
    for i, ch in enumerate(chs):
        if int(ch.get("ch", -1)) == int(ch_num):
            idx = i
            break
    if idx is None:
        # Fallback: Listenindex (ältere Annahme)
        idx = max(0, min(ch_num - 1, len(chs) - 1))
        log.warn(f"Scanner set_channel: ch={ch_num} nicht gefunden, Fallback idx={idx}")
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S, settings=settings)
    log.info(f"Scanner set_channel band={band_id} ch={ch_num} idx={idx}")


def channel_up(band_id, S, settings=None):
    chs = _get_channels(band_id)
    if not chs:
        return
    idx = (_current_ch.get(band_id, -1) + 1) % len(chs)
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S, settings=settings)


def channel_down(band_id, S, settings=None):
    chs = _get_channels(band_id)
    if not chs:
        return
    idx = (_current_ch.get(band_id, 1) - 1) % len(chs)
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S, settings=settings)


def channel_jump(band_id, delta, S, settings=None):
    chs = _get_channels(band_id)
    if not chs:
        return
    cur = _current_ch.get(band_id, 0)
    idx = (cur + delta) % len(chs)
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S, settings=settings)
    log.info(f"Scanner channel_jump band={band_id} delta={delta} idx={idx}")


def freq_step(band_id, delta_mhz, S, settings=None):
    b = BANDS.get(band_id, {})
    if "band" not in b:
        return
    band = b["band"]
    cur = band.get("start", band["min"])
    new_freq = round(cur + delta_mhz, 3)
    if new_freq > band["max"]:
        new_freq = band["min"]
    if new_freq < band["min"]:
        new_freq = band["max"]
    log.info(f"Scanner: STEP band={band_id} delta={delta_mhz:+.3f} -> {new_freq:.3f}")
    _play_band_freq(band_id, new_freq, S, settings=settings)


def set_freq(band_id, freq_mhz, S, settings=None):
    entry = BANDS.get(band_id, {})
    b = entry.get("band", {})
    if not b:
        # C9: Kanalbänder (pmr446/freenet/lpd433/cb) haben kein band-Dict —
        # Frequenz trotzdem mit Bandbreite des Kanals abspielen (Squelch-Reload)
        if entry.get("channels") is not None or band_id in ("pmr446", "freenet", "lpd433", "cb"):
            try:
                freq = float(freq_mhz)
            except Exception:
                log.warn(f"Scanner: SET_FREQ ungueltig band={band_id} value={freq_mhz}")
                return
            bw = entry.get("bw", 12500)
            name = f"{band_id.upper()} {freq:.5f} MHz"
            _set_scanner_label(band_id, name, S)
            play_freq(freq, name, bw, S, settings=settings)
            return
        log.warn(f"Scanner: SET_FREQ kein Band-Range: {band_id}")
        return

    try:
        freq = float(freq_mhz)
    except Exception:
        log.warn(f"Scanner: SET_FREQ ungueltig band={band_id} value={freq_mhz}")
        return

    if not (b["min"] <= freq <= b["max"]):
        log.warn(f"Scanner: SET_FREQ ausserhalb band={band_id} freq={freq}")
        ipc.write_progress("Scanner", f"{freq:.3f} MHz ausserhalb Bereich", color="orange")
        time.sleep(1.5)
        ipc.clear_progress()
        return

    log.info(f"Scanner: SET_FREQ band={band_id} freq={freq}")
    _play_band_freq(band_id, freq, S, settings=settings)


# ── Scan öffentlich ──────────────────────────────────────────────────────────

def scan_next(band_id, S, settings=None, autoplay=True):
    global _scan_abort
    _scan_abort = False

    b = BANDS.get(band_id, {})
    log.info(f"Scanner: SCAN_NEXT band={band_id}")

    ch = None

    # optionaler spectrum-Pfad nur für kleine Kanalbänder
    if _get_spectrum_enabled(settings) and band_id in ("pmr446", "freenet"):
        ch = _scan_list_spectrum(S, band_id=band_id, settings=settings)
        if ch:
            log.info(f"Scanner: spectrum-hit band={band_id} freq={ch.get('freq')}")

    # Fallback auf klassischen Scanner
    if ch is None:
        if "channels" in b:
            ch = _scan_list(S, b["channels"], b["bw"], 1, band_id=band_id, settings=settings)
        else:
            ch = _scan_range(S, b["band"], b["bw"], 1, band_id=band_id, settings=settings)

    if ch:
        if ch.get("freq") and "MHz" not in ch["name"]:
            _set_scanner_label(band_id, f"{ch['name']}  {ch['freq']} MHz", S)
        else:
            _set_scanner_label(band_id, ch["name"], S)
        if autoplay:
            play_freq(ch["freq"], ch["name"], b["bw"], S, settings=settings)
        _write_scan_result(band_id, True, ch["name"], ch.get("freq"))
        return ch
    _write_scan_result(band_id, False)
    return None


def scan_prev(band_id, S, settings=None, autoplay=True):
    global _scan_abort
    _scan_abort = False

    b = BANDS.get(band_id, {})
    log.info(f"Scanner: SCAN_PREV band={band_id}")

    ch = None

    # spectrum-basierter Scan ist aktuell richtungsneutral,
    # daher nur als Kandidatenfinder auch für prev nutzbar
    if _get_spectrum_enabled(settings) and band_id in ("pmr446", "freenet"):
        ch = _scan_list_spectrum(S, band_id=band_id, settings=settings)
        if ch:
            log.info(f"Scanner: spectrum-hit-prev band={band_id} freq={ch.get('freq')}")

    if ch is None:
        if "channels" in b:
            ch = _scan_list(S, b["channels"], b["bw"], -1, band_id=band_id, settings=settings)
        else:
            ch = _scan_range(S, b["band"], b["bw"], -1, band_id=band_id, settings=settings)

    if ch:
        if ch.get("freq") and "MHz" not in ch["name"]:
            _set_scanner_label(band_id, f"{ch['name']}  {ch['freq']} MHz", S)
        else:
            _set_scanner_label(band_id, ch["name"], S)
        if autoplay:
            play_freq(ch["freq"], ch["name"], b["bw"], S, settings=settings)
        _write_scan_result(band_id, True, ch["name"], ch.get("freq"))
        return ch
    _write_scan_result(band_id, False)
    return None
# ── PMR446 Dauer-Überwachung (Backend, ohne offene WebUI) ─────────────────────

PMR_MONITOR_STATUS = "/tmp/pidrive_pmr_monitor.json"
PMR_MONITOR_LOG = "/var/log/pidrive/pmr_monitor.jsonl"
PMR_MONITOR_HOLD_S = 15.0
PMR_MONITOR_WATCH_S = 1.0
PMR_MONITOR_WATCH_S_MIN = 0.5
PMR_MONITOR_WATCH_S_MAX = 2.5
PMR_MONITOR_IDLE_GAP_S = 0.25
PMR_MONITOR_HEARTBEAT_S = 120.0
PMR_MONITOR_TRIGGER_ON_DB = 25.0   # Nahfeld-Walkie ~60dB; 9–20dB = Dauer-Falsch (K8/K9)
PMR_MONITOR_TRIGGER_OFF_DB = 14.0
PMR_MONITOR_MIN_FRAMES = 1
PMR_MONITOR_DEFAULT_GAIN = 36  # Auto(-1) zu taub für PMR-Nahfeld
PMR_MONITOR_PEEK_MIN_DB = 6.0
PMR_MONITOR_START_SETTLE_S = 0.35
PMR_MONITOR_PREEMPT_SETTLE_S = 0.35
PMR_MONITOR_LISTEN_END_SETTLE_S = 0.25

_monitor_thread = None
_monitor_stop = threading.Event()
_monitor_lock = threading.Lock()
_monitor_meta = {
    "running": False,
    "band": "",
    "autotune": False,
    "started_ts": 0.0,
    "cycles": 0,
    "hits": 0,
    "peek_count": 0,
    "activity_count": 0,
    "tune_blocked_count": 0,
    "capture_error_count": 0,
    "capture_error_streak": 0,
    "force_free_rtl_count": 0,
    "usb_reset_count": 0,
    "preempt_source_count": 0,
    "blocked_transition_count": 0,
    "productive_scan_count": 0,
    "trigger_on_db": PMR_MONITOR_TRIGGER_ON_DB,
    "trigger_off_db": PMR_MONITOR_TRIGGER_OFF_DB,
    "watch_s": PMR_MONITOR_WATCH_S,
    "last_event": "",
    "last_error_class": "",
    "last_ch": None,
    "last_relative_db": None,
    "last_peek_ch": None,
    "last_peek_relative_db": None,
    "watch_started_ts": None,
    "watch_finished_ts": None,
    "activity_ts": None,
    "tuned_ts": None,
    "audio_started_ts": None,
    "listen_end_ts": None,
    "last_productive_scan_ts": None,
    "last_usb_reset_ts": None,
    "last_detect_latency_ms": None,
    "last_tune_latency_ms": None,
    "last_audio_latency_ms": None,
    "last_end_to_end_latency_ms": None,
    "log_path": PMR_MONITOR_LOG,
}


def _pmr_iso_now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _pmr_ch_num(channel_name):
    digits = "".join(ch for ch in str(channel_name or "") if ch.isdigit())
    try:
        return int(digits) if digits else None
    except Exception:
        return None


def _pmr_error_class(err_s: str) -> str:
    e = (err_s or "").lower()
    if "authorized" in e:
        return "usb_authorized_0"
    if "belegt" in e or "busy" in e:
        return "busy_timeout"
    if "timeout" in e or "hängt" in e or "hang" in e:
        return "rtl_timeout"
    if "iq" in e or "leer" in e or "keine daten" in e:
        return "rtl_no_iq"
    if "spectrum_unavailable" in e:
        return "spectrum_unavailable"
    return "capture_error"


def _pmr_effective_state(st: dict) -> str:
    if not st.get("running"):
        return "stopped"
    err_streak = int(st.get("capture_error_streak") or 0)
    if err_streak >= 2 or st.get("last_event") == "capture_error":
        return "erroring"
    last = str(st.get("last_event") or "")
    if last.startswith("listening"):
        return "listening"
    if int(st.get("blocked_transition_count") or 0) and last == "scan":
        # nur Hinweis — nicht dominant
        pass
    peek_c = int(st.get("peek_count") or 0)
    act_c = int(st.get("activity_count") or 0)
    if peek_c > 0 and act_c == 0:
        return "running_peek_only"
    age = st.get("productive_scan_age_s")
    if age is not None and float(age) > 15.0:
        return "running_stale"
    return "running_productive"


def _pmr_enrich_status(st: dict) -> dict:
    """Abgeleitete Felder für API/CLI/WebUI."""
    out = dict(st)
    now = time.time()
    pts = out.get("last_productive_scan_ts")
    try:
        out["productive_scan_age_s"] = (
            round(now - float(pts), 2) if pts else None
        )
    except Exception:
        out["productive_scan_age_s"] = None
    out["monitor_effective_state"] = _pmr_effective_state(out)
    return out


def _pmr_append_log(entry: dict):
    """Eine JSONL-Zeile: Kanal + Stärke (relative_db / score / power_db)."""
    row = dict(entry)
    row.setdefault("ts", _pmr_iso_now())
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    try:
        os.makedirs(os.path.dirname(PMR_MONITOR_LOG), exist_ok=True)
        with open(PMR_MONITOR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        log.warn(f"PMR-Monitor Log: {e}")


def _pmr_write_status(**extra):
    data = dict(_monitor_meta)
    data.update(extra)
    data["ts"] = _pmr_iso_now()
    data = _pmr_enrich_status(data)
    try:
        import errno
        tmp = PMR_MONITOR_STATUS + ".tmp"
        payload = json.dumps(data, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        try:
            os.replace(tmp, PMR_MONITOR_STATUS)
        except OSError as e:
            if e.errno not in (errno.EPERM, errno.EACCES):
                raise
            with open(PMR_MONITOR_STATUS, "w", encoding="utf-8") as f:
                f.write(payload)
            try:
                os.remove(tmp)
            except OSError:
                pass
    except Exception as e:
        log.warn(f"PMR-Monitor Status: {e}")


def is_pmr_monitor_running():
    t = _monitor_thread
    return bool(t and t.is_alive())


def get_pmr_monitor_status():
    st = dict(_monitor_meta)
    st["running"] = is_pmr_monitor_running()
    try:
        if os.path.exists(PMR_MONITOR_STATUS):
            with open(PMR_MONITOR_STATUS, "r", encoding="utf-8") as f:
                disk = json.load(f)
            if isinstance(disk, dict):
                st.update(disk)
                st["running"] = is_pmr_monitor_running()
    except Exception:
        pass
    return _pmr_enrich_status(st)


def _pmr_top_peek(result) -> tuple:
    """(name, relative_db) stärkster Kanal aus Debug-Scores, sonst (None, None)."""
    try:
        scores_dbg = ((result.debug or {}).get("scores") or []) if result else []
        mx = {}
        for fr in scores_dbg:
            for k, v in (fr.get("channels") or {}).items():
                mx[k] = max(mx.get(k, -999.0), float(v))
        if not mx:
            return None, None
        top_name, top_db = max(mx.items(), key=lambda kv: kv[1])
        return top_name, float(top_db)
    except Exception:
        return None, None


def _pmr_monitor_loop(S, settings, band_id, autotune, hold_s, watch_s,
                      trigger_on_db, trigger_off_db):
    global _monitor_meta
    log.action(
        "PMR-Monitor",
        f"start band={band_id} autotune={autotune} hold={hold_s}s "
        f"trigger_on={trigger_on_db}dB"
    )
    _pmr_append_log({
        "event": "start",
        "band": band_id,
        "autotune": bool(autotune),
        "hold_s": float(hold_s),
        "watch_s": float(watch_s),
        "trigger_on_db": float(trigger_on_db),
        "trigger_off_db": float(trigger_off_db),
    })
    _monitor_meta.update({
        "running": True,
        "band": band_id,
        "autotune": bool(autotune),
        "started_ts": time.time(),
        "cycles": 0,
        "hits": 0,
        "peek_count": 0,
        "activity_count": 0,
        "tune_blocked_count": 0,
        "capture_error_count": 0,
        "capture_error_streak": 0,
        "force_free_rtl_count": 0,
        "usb_reset_count": 0,
        "preempt_source_count": 0,
        "blocked_transition_count": 0,
        "productive_scan_count": 0,
        "trigger_on_db": float(trigger_on_db),
        "trigger_off_db": float(trigger_off_db),
        "watch_s": float(watch_s),
        "last_event": "start",
        "last_error_class": "",
        "last_ch": None,
        "last_relative_db": None,
        "last_peek_ch": None,
        "last_peek_relative_db": None,
        "watch_started_ts": None,
        "watch_finished_ts": None,
        "activity_ts": None,
        "tuned_ts": None,
        "audio_started_ts": None,
        "listen_end_ts": None,
        "last_productive_scan_ts": None,
        "last_usb_reset_ts": None,
        "last_detect_latency_ms": None,
        "last_tune_latency_ms": None,
        "last_audio_latency_ms": None,
        "last_end_to_end_latency_ms": None,
        "log_path": PMR_MONITOR_LOG,
        "error": "",
    })
    _pmr_write_status()

    last_heartbeat = time.time()
    idle_since_hb = 0
    consecutive_errors = 0

    try:
        while not _monitor_stop.is_set():
            if (_src_state and _src_state.in_transition()):
                # Zähler nur einmal pro Blockade-Episode erhöhen
                if _monitor_meta.get("last_event") != "blocked_transition":
                    _monitor_meta["blocked_transition_count"] = (
                        int(_monitor_meta.get("blocked_transition_count") or 0) + 1
                    )
                    _monitor_meta["last_event"] = "blocked_transition"
                time.sleep(0.3)
                continue
            rt = str(S.get("radio_type") or "").upper()
            if rt and rt not in ("", "SCANNER"):
                # Andere RTL-Quellen (z.B. DAB-Boot-Resume) aktiv beenden —
                # sonst hängt die Überwachung dauerhaft in Pause.
                log.warn(f"PMR-Monitor: verdränge Quelle {rt}")
                _monitor_meta["preempt_source_count"] = (
                    int(_monitor_meta.get("preempt_source_count") or 0) + 1
                )
                _pmr_append_log({"event": "preempt_source", "radio_type": rt})
                try:
                    from modules import dab as _dab, fm as _fm, webradio as _wr
                    try:
                        _wr.stop(S)
                    except Exception:
                        pass
                    try:
                        _dab.stop(S)
                    except Exception:
                        pass
                    try:
                        _fm.stop(S)
                    except Exception:
                        pass
                except Exception as e:
                    log.warn(f"PMR-Monitor preempt: {e}")
                S["radio_playing"] = False
                S["radio_type"] = ""
                S["radio_name"] = ""
                if _src_state:
                    try:
                        _src_state.commit_source("idle")
                    except Exception:
                        pass
                time.sleep(PMR_MONITOR_PREEMPT_SETTLE_S)
                continue

            if not _spectrum:
                _monitor_meta["error"] = "spectrum_unavailable"
                _monitor_meta["last_error_class"] = "spectrum_unavailable"
                _pmr_write_status()
                _pmr_append_log({"event": "error", "error": "spectrum_unavailable",
                                 "error_class": "spectrum_unavailable"})
                break

            profile = _get_spectrum_profile_for_band(band_id)
            if profile is None:
                _monitor_meta["error"] = f"no_profile:{band_id}"
                _pmr_write_status()
                break

            watch_t0 = time.time()
            _monitor_meta["watch_started_ts"] = watch_t0
            try:
                import dataclasses as _dc
                profile = _dc.replace(
                    profile,
                    watch_seconds=float(watch_s),
                    trigger_on_db=float(trigger_on_db),
                    trigger_off_db=float(trigger_off_db),
                    min_active_frames=int(PMR_MONITOR_MIN_FRAMES),
                )
                mon_gain = _get_pmr_monitor_gain(settings)
                watcher = _spectrum.build_default_watcher(
                    ppm=_get_ppm(settings),
                    gain=mon_gain,
                )
                result = watcher.watch_channels(profile, debug=True)
            except Exception as e:
                log.warn(f"PMR-Monitor capture: {e}")
                err_s = str(e)
                err_cls = _pmr_error_class(err_s)
                consecutive_errors += 1
                _monitor_meta["capture_error_count"] = (
                    int(_monitor_meta.get("capture_error_count") or 0) + 1
                )
                _monitor_meta["capture_error_streak"] = consecutive_errors
                _monitor_meta["last_error_class"] = err_cls
                _pmr_append_log({
                    "event": "error",
                    "error": err_s[:200],
                    "error_class": err_cls,
                    "streak": consecutive_errors,
                })
                _monitor_meta["last_event"] = "capture_error"
                _pmr_write_status(error=err_s[:120])
                if ("belegt" in err_s.lower() or "busy" in err_s.lower()
                        or "Timeout" in err_s or "hängt" in err_s):
                    try:
                        from modules import dab as _dab, fm as _fm
                        try:
                            _dab.stop(S)
                        except Exception:
                            pass
                        try:
                            _fm.stop(S)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Gestufte Recovery über zentrale RTL-API
                    try:
                        if _rtlsdr and hasattr(_rtlsdr, "recover_busy_device"):
                            level = "reset" if consecutive_errors >= 3 else "hard"
                            rr = _rtlsdr.recover_busy_device(
                                reason=f"monitor:{err_cls}",
                                level=level,
                            )
                            _monitor_meta["force_free_rtl_count"] = (
                                int(_monitor_meta.get("force_free_rtl_count") or 0) + 1
                            )
                            _pmr_append_log({
                                "event": "force_free_rtl",
                                "streak": consecutive_errors,
                                "error_class": err_cls,
                                "level": level,
                                "steps": (rr or {}).get("steps"),
                            })
                            if level == "reset":
                                if (rr or {}).get("skipped_reset_cooldown"):
                                    _pmr_append_log({
                                        "event": "usb_reset_skipped",
                                        "reason": "cooldown",
                                        "steps": (rr or {}).get("steps"),
                                    })
                                else:
                                    reset_ok = bool((rr or {}).get("ok"))
                                    _monitor_meta["usb_reset_count"] = (
                                        int(_monitor_meta.get("usb_reset_count") or 0) + 1
                                    )
                                    _monitor_meta["last_usb_reset_ts"] = time.time()
                                    _pmr_append_log({
                                        "event": "usb_reset",
                                        "ok": reset_ok,
                                        "steps": (rr or {}).get("steps"),
                                    })
                                    log.warn(
                                        f"PMR-Monitor usb_reset → {reset_ok}"
                                    )
                                    consecutive_errors = 0
                                    _monitor_meta["capture_error_streak"] = 0
                                    time.sleep(1.5)
                        else:
                            raise RuntimeError("no recover_busy_device")
                    except Exception as re:
                        log.warn(f"PMR-Monitor recover: {re}")
                        # Fallback: alter Direkt-Kill
                        try:
                            subprocess.run(["pkill", "-9", "-x", "welle-cli"],
                                           capture_output=True, timeout=3)
                            subprocess.run(["pkill", "-9", "-x", "rtl_sdr"],
                                           capture_output=True, timeout=3)
                            subprocess.run(["pkill", "-9", "-x", "rtl_fm"],
                                           capture_output=True, timeout=3)
                        except Exception:
                            pass
                    time.sleep(0.35)
                if _monitor_stop.wait(1.5):
                    break
                continue

            consecutive_errors = 0
            _monitor_meta["capture_error_streak"] = 0
            _monitor_meta["last_error_class"] = ""
            _monitor_meta["error"] = ""
            watch_t1 = time.time()
            if result is not None:
                try:
                    watch_t0 = float(result.watch_started_ts or watch_t0)
                    watch_t1 = float(result.watch_ended_ts or watch_t1)
                except Exception:
                    pass
            _monitor_meta["watch_started_ts"] = watch_t0
            _monitor_meta["watch_finished_ts"] = watch_t1
            _monitor_meta["last_productive_scan_ts"] = watch_t1
            _monitor_meta["productive_scan_count"] = (
                int(_monitor_meta.get("productive_scan_count") or 0) + 1
            )
            _monitor_meta["cycles"] = int(_monitor_meta.get("cycles") or 0) + 1
            idle_since_hb += 1

            best = result.best_candidate if result else None
            found = bool(result and result.found and best)

            if found:
                ch_num = _pmr_ch_num(best.channel_name)
                freq_mhz = round(float(best.freq_hz) / 1e6, 6)
                rel = round(float(best.relative_db), 2)
                score = round(float(best.score), 3)
                power = round(float(best.power_db), 2)
                conf = round(float(best.confidence), 3)
                activity_ts = time.time()
                detect_ms = max(0.0, (activity_ts - watch_t0) * 1000.0)

                cands_log = []
                for c in (result.candidates or []):
                    if c is None:
                        continue
                    cands_log.append({
                        "ch": _pmr_ch_num(c.channel_name),
                        "name": c.channel_name,
                        "freq_mhz": round(float(c.freq_hz) / 1e6, 6),
                        "relative_db": round(float(c.relative_db), 2),
                        "score": round(float(c.score), 3),
                        "power_db": round(float(c.power_db), 2),
                        "confidence": round(float(c.confidence), 3),
                    })

                _monitor_meta["hits"] = int(_monitor_meta.get("hits") or 0) + 1
                _monitor_meta["activity_count"] = (
                    int(_monitor_meta.get("activity_count") or 0) + 1
                )
                _monitor_meta["last_ch"] = ch_num
                _monitor_meta["last_relative_db"] = rel
                _monitor_meta["activity_ts"] = activity_ts
                _monitor_meta["last_detect_latency_ms"] = round(detect_ms, 1)
                _monitor_meta["last_event"] = "activity"
                _pmr_write_status()

                action = "tune" if (autotune and ch_num) else "observe"
                _pmr_append_log({
                    "event": "activity",
                    "band": band_id,
                    "ch": ch_num,
                    "name": best.channel_name,
                    "freq_mhz": freq_mhz,
                    "relative_db": rel,
                    "score": score,
                    "power_db": power,
                    "confidence": conf,
                    "action": action,
                    "detect_latency_ms": round(detect_ms, 1),
                    "trigger_on_db": float(trigger_on_db),
                    "candidates": cands_log,
                })
                log.action(
                    "PMR-Monitor",
                    f"Aktiv K{ch_num or '?'} {freq_mhz} MHz  "
                    f"+{rel} dB  score={score}  → {action}"
                )

                if autotune and ch_num and not _monitor_stop.is_set():
                    owner = f"pmr_monitor:{band_id}"
                    got_tr = False
                    try:
                        begin_ts = time.time()
                        if _src_state:
                            got_tr = bool(_src_state.begin_transition(
                                owner, "scanner"
                            ))
                            if not got_tr:
                                _monitor_meta["tune_blocked_count"] = (
                                    int(_monitor_meta.get("tune_blocked_count") or 0) + 1
                                )
                                _monitor_meta["last_event"] = "tune_blocked"
                                _pmr_write_status()
                                _pmr_append_log({
                                    "event": "tune_blocked",
                                    "ch": ch_num,
                                    "reason": "transition_busy",
                                })
                                log.warn(
                                    f"PMR-Monitor Tune blockiert "
                                    f"(Transition aktiv) K{ch_num}"
                                )
                                continue
                        S["scanner_band"] = band_id
                        set_channel(band_id, int(ch_num), S, settings=settings)
                        audio_ts = time.time()
                        if _src_state:
                            try:
                                _src_state.commit_source("scanner")
                            except Exception:
                                pass
                        tuned_ts = time.time()
                        tune_ms = max(0.0, (tuned_ts - begin_ts) * 1000.0)
                        audio_ms = max(0.0, (audio_ts - begin_ts) * 1000.0)
                        e2e_ms = max(0.0, (audio_ts - watch_t0) * 1000.0)
                        _monitor_meta["tuned_ts"] = tuned_ts
                        _monitor_meta["audio_started_ts"] = audio_ts
                        _monitor_meta["last_tune_latency_ms"] = round(tune_ms, 1)
                        _monitor_meta["last_audio_latency_ms"] = round(audio_ms, 1)
                        _monitor_meta["last_end_to_end_latency_ms"] = round(e2e_ms, 1)
                        _pmr_append_log({
                            "event": "tuned",
                            "band": band_id,
                            "ch": ch_num,
                            "freq_mhz": freq_mhz,
                            "relative_db": rel,
                            "hold_s": float(hold_s),
                            "tune_latency_ms": round(tune_ms, 1),
                            "audio_latency_ms": round(audio_ms, 1),
                            "end_to_end_latency_ms": round(e2e_ms, 1),
                        })
                        _monitor_meta["last_event"] = f"listening:K{ch_num}"
                        _pmr_write_status()
                        end = time.time() + float(hold_s)
                        while time.time() < end and not _monitor_stop.is_set():
                            # Hold kann > STALE_TIMEOUT_S sein — Watchdog füttern
                            if _src_state and got_tr:
                                try:
                                    _src_state.refresh_transition(owner)
                                except Exception:
                                    pass
                            time.sleep(0.4)
                    except Exception as e:
                        log.warn(f"PMR-Monitor tune: {e}")
                        _pmr_append_log({
                            "event": "tune_error",
                            "ch": ch_num,
                            "error": str(e)[:200],
                        })
                    finally:
                        if _src_state and got_tr:
                            try:
                                _src_state.end_transition()
                            except Exception:
                                pass
                        if not _monitor_stop.is_set():
                            try:
                                stop(S)
                            except Exception:
                                pass
                            _monitor_meta["listen_end_ts"] = time.time()
                            _pmr_append_log({
                                "event": "listen_end",
                                "ch": ch_num,
                                "hold_s": float(hold_s),
                            })
                            time.sleep(PMR_MONITOR_LISTEN_END_SETTLE_S)
                idle_since_hb = 0
                last_heartbeat = time.time()
            else:
                _monitor_meta["last_event"] = "scan"
                top_name, top_db = _pmr_top_peek(result)
                if top_name is not None and top_db >= PMR_MONITOR_PEEK_MIN_DB:
                    peek_ch = _pmr_ch_num(top_name)
                    _monitor_meta["peek_count"] = (
                        int(_monitor_meta.get("peek_count") or 0) + 1
                    )
                    _monitor_meta["last_peek_ch"] = peek_ch
                    _monitor_meta["last_peek_relative_db"] = round(top_db, 2)
                    _pmr_append_log({
                        "event": "peek",
                        "ch": peek_ch,
                        "name": top_name,
                        "relative_db": round(top_db, 2),
                        "triggered": False,
                        "trigger_on_db": float(trigger_on_db),
                    })
                _pmr_write_status()
                if time.time() - last_heartbeat >= PMR_MONITOR_HEARTBEAT_S:
                    _pmr_append_log({
                        "event": "heartbeat",
                        "band": band_id,
                        "cycles": _monitor_meta.get("cycles"),
                        "hits": _monitor_meta.get("hits"),
                        "peek_count": _monitor_meta.get("peek_count"),
                        "activity_count": _monitor_meta.get("activity_count"),
                        "idle_cycles": idle_since_hb,
                        "trigger_on_db": float(trigger_on_db),
                    })
                    last_heartbeat = time.time()
                    idle_since_hb = 0
                    _pmr_write_status()

            if _monitor_stop.wait(PMR_MONITOR_IDLE_GAP_S):
                break
    finally:
        _monitor_meta["running"] = False
        _monitor_meta["last_event"] = "stopped"
        _pmr_write_status()
        _pmr_append_log({
            "event": "stop",
            "band": band_id,
            "cycles": _monitor_meta.get("cycles"),
            "hits": _monitor_meta.get("hits"),
            "peek_count": _monitor_meta.get("peek_count"),
            "activity_count": _monitor_meta.get("activity_count"),
            "capture_error_count": _monitor_meta.get("capture_error_count"),
            "usb_reset_count": _monitor_meta.get("usb_reset_count"),
        })
        log.action("PMR-Monitor", "gestoppt")


def _pmr_read_trigger_settings(settings):
    on_db = PMR_MONITOR_TRIGGER_ON_DB
    off_db = PMR_MONITOR_TRIGGER_OFF_DB
    try:
        on_db = float(settings.get(
            "scanner_pmr_trigger_on_db", PMR_MONITOR_TRIGGER_ON_DB
        ))
    except Exception:
        pass
    try:
        off_db = float(settings.get(
            "scanner_pmr_trigger_off_db", PMR_MONITOR_TRIGGER_OFF_DB
        ))
    except Exception:
        pass
    on_db = max(6.0, min(60.0, on_db))
    off_db = max(0.0, min(on_db - 1.0, off_db))
    return on_db, off_db


def start_pmr_monitor(S, settings=None, band_id="pmr446",
                      autotune=None, hold_s=None, watch_s=None,
                      trigger_on_db=None, trigger_off_db=None):
    """
    Dauerhafte PMR-Überwachung im Core-Thread:
    Spektrum scannen → Aktivität loggen (Kanal+dB) → optional umschalten.
    """
    global _monitor_thread
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}

    if autotune is None:
        autotune = bool(settings.get("scanner_pmr_autotune", True))
    if hold_s is None:
        try:
            hold_s = float(settings.get("scanner_pmr_hold_s", PMR_MONITOR_HOLD_S))
        except Exception:
            hold_s = PMR_MONITOR_HOLD_S
    if watch_s is None:
        try:
            watch_s = float(settings.get("scanner_pmr_watch_s", PMR_MONITOR_WATCH_S))
        except Exception:
            watch_s = PMR_MONITOR_WATCH_S
    watch_s = max(PMR_MONITOR_WATCH_S_MIN, min(PMR_MONITOR_WATCH_S_MAX, float(watch_s)))
    def_on, def_off = _pmr_read_trigger_settings(settings)
    if trigger_on_db is None:
        trigger_on_db = def_on
    if trigger_off_db is None:
        trigger_off_db = def_off
    trigger_on_db = max(6.0, min(60.0, float(trigger_on_db)))
    trigger_off_db = max(0.0, min(trigger_on_db - 1.0, float(trigger_off_db)))

    band_id = (band_id or "pmr446").lower()
    if band_id not in ("pmr446", "freenet"):
        raise ValueError(f"PMR-Monitor: Band nicht unterstützt: {band_id}")

    with _monitor_lock:
        if is_pmr_monitor_running():
            log.info("PMR-Monitor: läuft bereits")
            return False
        _monitor_stop.clear()
        # RTL freimachen: DAB/FM/Scanner + Lock
        try:
            from modules import dab as _dab, fm as _fm, webradio as _wr
            try:
                _wr.stop(S)
            except Exception:
                pass
            try:
                _dab.stop(S)
            except Exception:
                pass
            try:
                _fm.stop(S)
            except Exception:
                pass
        except Exception:
            pass
        try:
            stop(S)
        except Exception:
            pass
        # Synchron freigeben — bevorzugt zentrale Recovery
        try:
            if _rtlsdr and hasattr(_rtlsdr, "recover_busy_device"):
                _rtlsdr.recover_busy_device(reason="pmr_monitor_start", level="hard")
            else:
                raise RuntimeError("no recover")
        except Exception:
            try:
                subprocess.run(["pkill", "-x", "welle-cli"],
                               capture_output=True, timeout=3)
            except Exception:
                pass
            try:
                subprocess.run(["pkill", "-x", "rtl_sdr"],
                               capture_output=True, timeout=3)
            except Exception:
                pass
            try:
                subprocess.run(["pkill", "-x", "rtl_fm"],
                               capture_output=True, timeout=3)
            except Exception:
                pass
            for _p in (
                "/tmp/pidrive_rtlsdr.lock",
                "/tmp/pidrive_rtlsdr_state.json",
                "/tmp/pidrive_rtlsdr_owner.json",
            ):
                try:
                    if os.path.exists(_p):
                        os.remove(_p)
                except Exception:
                    pass
        # Soft-Owner-Marker (Diagnose); Capture-Lease hält Spectrum/Audio selbst.
        if _rtlsdr and hasattr(_rtlsdr, "announce_owner"):
            try:
                _rtlsdr.announce_owner("pmr_monitor", mode="pmr_monitor")
            except Exception:
                pass
        time.sleep(PMR_MONITOR_START_SETTLE_S)
        if _src_state:
            try:
                _src_state.force_end_transition("pmr_monitor_start")
            except Exception:
                pass
            try:
                _src_state.commit_source("idle")
            except Exception:
                pass
        t = threading.Thread(
            target=_pmr_monitor_loop,
            args=(
                S, settings, band_id, bool(autotune), float(hold_s),
                float(watch_s), float(trigger_on_db), float(trigger_off_db),
            ),
            daemon=True,
            name="pmr-monitor",
        )
        _monitor_thread = t
        t.start()
    return True


def stop_pmr_monitor(S=None, join=True):
    global _monitor_thread
    _monitor_stop.set()
    t = _monitor_thread
    if join and t and t.is_alive() and t is not threading.current_thread():
        t.join(timeout=8.0)
    _monitor_meta["running"] = False
    _pmr_write_status()
    # Streaming-Watch kann rtl_sdr hinterlassen wenn Thread hängt —
    # gezielt freigeben, sonst Spektrum/WebUI: usb_claim_interface -6.
    if _rtlsdr and hasattr(_rtlsdr, "recover_busy_device"):
        try:
            _rtlsdr.recover_busy_device(reason="pmr_monitor_stop", level="hard")
        except Exception:
            pass
    elif _rtlsdr and hasattr(_rtlsdr, "release_owner"):
        try:
            _rtlsdr.release_owner("pmr_monitor")
        except Exception:
            pass
    return True
