"""
modules/scanner.py - Funkscanner mit RTL-SDR
PiDrive - GPL-v3

PMR446 (8 Kanaele), Freenet (4), LPD433 (69), VHF (136-174 MHz), UHF (400-470 MHz)
Scan-Funktion: Squelch-Erkennung via rtl_fm -l, stoppt bei Signal.
"""

import subprocess
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None
import os
import time
import ipc
import log

# ── Kanaltabellen ────────────────────────────────────────────────────────────

PMR446_CHANNELS = [
    {"ch": i+1, "name": f"PMR Kanal {i+1}",
     "freq": round(446.00625 + i * 0.01250, 5)}
    for i in range(8)
]

FREENET_CHANNELS = [
    {"ch": 1, "name": "Freenet K1", "freq": 149.02500},
    {"ch": 2, "name": "Freenet K2", "freq": 149.03750},
    {"ch": 3, "name": "Freenet K3", "freq": 149.05000},
    {"ch": 4, "name": "Freenet K4", "freq": 149.08750},
]

LPD433_CHANNELS = [
    {"ch": i+1, "name": f"LPD K{i+1:02d}",
     "freq": round(433.075 + i * 0.025, 3)}
    for i in range(69)
]

# CB-Funk DE/EU: Kanäle 41-80 (26.565-26.955 MHz, lineares Raster) + 1-40 (26.965-27.405 MHz)
CB_CHANNELS = (
    # Deutsche Zusatzkanäle 41-80 (lineares 10-kHz-Raster)
    [{"ch": 41+i, "name": f"CB Kanal {41+i:02d}",
      "freq": round(26.565 + i*0.010, 3)} for i in range(40)] +
    # Klassische Kanäle 1-40 (historisches Frequenzraster)
    [
        {"ch":  1, "name": "CB Kanal 01", "freq": 26.965},
        {"ch":  2, "name": "CB Kanal 02", "freq": 26.975},
        {"ch":  3, "name": "CB Kanal 03", "freq": 26.985},
        {"ch":  4, "name": "CB Kanal 04", "freq": 27.005},
        {"ch":  5, "name": "CB Kanal 05", "freq": 27.015},
        {"ch":  6, "name": "CB Kanal 06", "freq": 27.025},
        {"ch":  7, "name": "CB Kanal 07", "freq": 27.035},
        {"ch":  8, "name": "CB Kanal 08", "freq": 27.055},
        {"ch":  9, "name": "CB Kanal 09", "freq": 27.065},
        {"ch": 10, "name": "CB Kanal 10", "freq": 27.075},
        {"ch": 11, "name": "CB Kanal 11", "freq": 27.085},
        {"ch": 12, "name": "CB Kanal 12", "freq": 27.105},
        {"ch": 13, "name": "CB Kanal 13", "freq": 27.115},
        {"ch": 14, "name": "CB Kanal 14", "freq": 27.125},
        {"ch": 15, "name": "CB Kanal 15", "freq": 27.135},
        {"ch": 16, "name": "CB Kanal 16", "freq": 27.155},
        {"ch": 17, "name": "CB Kanal 17", "freq": 27.165},
        {"ch": 18, "name": "CB Kanal 18", "freq": 27.175},
        {"ch": 19, "name": "CB Kanal 19", "freq": 27.185},  # Notfall/Anruf
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

VHF_RANGE = {"min": 136.0, "max": 174.0, "step_fine": 0.025,
             "label": "VHF (136-174 MHz)", "short": "VHF"}

UHF_RANGE = {"min": 400.0, "max": 470.0, "step_fine": 0.025,
             "label": "UHF (400-470 MHz)", "short": "UHF"}

# ── Band-Konfiguration ─────────────────────────────────────────────────────
# Startfrequenz für VHF/UHF Scan-Start; für Kanal-Bänder gilt Index 0 = Kanal 1

BANDS = {
    "pmr446": {
        "channels": PMR446_CHANNELS,
        "bw": 12500,        # 12.5 kHz Bandbreite
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
                 "step_coarse": 1.0, "step_fine": 0.025,
                 "step": 0.025},
        "bw": 25000,
        "label": "VHF",
    },
    "uhf": {
        "band": {**UHF_RANGE, "start": UHF_RANGE["min"],
                 "step_coarse": 1.0, "step_fine": 0.025,
                 "step": 0.025},
        "bw": 25000,
        "label": "UHF",
    },
    "cb": {
        "channels": CB_CHANNELS,
        "bw": 10000,   # 10 kHz — CB-Funk FM
        "label": "CB-Funk",
    },
}

# Aktueller Kanalindex pro Band (PMR/Freenet/LPD: Index 0 = Kanal 1)
_current_ch: dict = {}


# ── Player ───────────────────────────────────────────────────────────────────

_player_proc = None
_scan_running = False
_scan_abort   = False   # v0.8.13: gesetzt von stop(), geprüft in scan-Schleifen
SQUELCH = 25  # 0=immer offen, hoeher=strenger (Standard, überschreibbar via settings)

def _get_squelch(settings=None):
    """Squelch-Schwelle aus settings.json lesen (v0.8.18).
    Niedrigerer Wert = empfindlicher = mehr Aktivität, aber auch mehr Rauschen.
    Empfehlung: 25 (Standard), 15 (empfindlich), 10 (sehr empfindlich).
    """
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            return SQUELCH
    return int(settings.get("scanner_squelch", SQUELCH))


def _get_ppm(settings=None):
    """PPM-Korrektur aus settings.json lesen (v0.9.0)."""
    try:
        if settings is None:
            from settings import load_settings
            settings = load_settings()
        return int(settings.get("ppm_correction", 0))
    except Exception:
        return 0


def _get_gain(settings=None):
    """Scanner HF-Gain aus settings.json lesen (v0.9.0). -1=Auto AGC."""
    try:
        if settings is None:
            from settings import load_settings
            settings = load_settings()
        return int(settings.get("scanner_gain", -1))
    except Exception:
        return -1

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _run(cmd, capture=False, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if capture else r.returncode == 0
    except Exception:
        return "" if capture else False

def is_rtlsdr_available():
    return bool(_run("lsusb 2>/dev/null | grep -iE 'rtl|2832|2838|0bda'", capture=True))

def is_rtlfm_available():
    return _run("which rtl_fm 2>/dev/null")

def check_hardware(screen):
    if not is_rtlsdr_available():
        ipc.write_progress("RTL-SDR", "Kein Stick gefunden!")
        time.sleep(2)
        return False
    if not is_rtlfm_available():
        ipc.write_progress("rtl_fm fehlt", "sudo apt install rtl-sdr")
        time.sleep(3)
        return False
    return True

def play_freq(freq_mhz, name, bandwidth_hz, S, settings=None):
    global _player_proc
    if _rtlsdr and not _rtlsdr.detect_usb()["present"]:
        S["radio_station"] = "RTL-SDR nicht gefunden"
        return
    stop(S)
    _ppm  = _get_ppm(settings)
    _gain = _get_gain(settings)
    _ppm_arg  = f" -p {_ppm}" if _ppm else ""
    _gain_arg = f" -g {_gain}" if _gain != -1 else ""
    freq_hz = int(freq_mhz * 1e6)
    sr = max(48000, bandwidth_hz * 4)
    try:
        cmd = (f"rtl_fm -M fm -f {freq_hz} -s {bandwidth_hz}{_ppm_arg}{_gain_arg} -r {sr} - 2>/dev/null | "
               f"mpv --no-video --really-quiet --title=pidrive_scanner "
               f"--demuxer=rawaudio --demuxer-rawaudio-rate={sr} "
               f"--demuxer-rawaudio-channels=1 --ao=pulse - 2>/dev/null")
        if _rtlsdr:
            usb = _rtlsdr.detect_usb()
            if not usb.get("present"):
                S["radio_station"] = "RTL-SDR nicht gefunden"
                import log as _log; _log.error("Scanner: kein RTL-SDR")
                return
            if _rtlsdr.is_busy():
                S["radio_station"] = "RTL-SDR belegt"
                import log as _log; _log.warn("Scanner: RTL-SDR belegt")
                return
        if _rtlsdr:
            try:
                _player_proc = _rtlsdr.start_process(
                    cmd, owner=f"scanner:{name}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as _e:
                import log as _l; _l.error("Scanner: RTL-SDR Lock: " + str(_e))
                return
        else:
            _player_proc = subprocess.Popen(cmd, shell=True,
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL)
        S["radio_playing"] = True
        S["radio_station"] = f"{name} ({freq_mhz:.5g} MHz)"
        S["radio_type"]    = "SCANNER"
        if _src_state: _src_state.commit_source("scanner")
        log.action("Scanner", f"{name} @ {freq_mhz} MHz")
    except Exception as e:
        log.error(f"Scanner play: {e}")

def stop(S):
    global _player_proc, _scan_abort
    _scan_abort = True   # v0.8.13: bricht laufende scan-Schleifen ab
    log.info("Scanner stop: requested")
    if _rtlsdr:
        _rtlsdr.stop_process()
    _bg("pkill -f pidrive_scanner 2>/dev/null")
    _bg("pkill -f rtl_fm 2>/dev/null")
    _bg("pkill -f 'mpv --no-video --really-quiet --title=pidrive_scanner' 2>/dev/null")
    if _player_proc:
        try:
            _player_proc.terminate()
        except Exception:
            pass
        _player_proc = None
    if S.get("radio_type") == "SCANNER":
        S["radio_playing"] = False
        S["radio_station"] = ""
    time.sleep(0.2)
    log.info("Scanner stop: done")

# ── Signal-Erkennung (v0.8.8: zweistufig Fast-Detect + Confirm) ───────────────

def _detect_signal_fast(freq_mhz, bandwidth_hz, timeout_s=0.22, squelch=None, settings=None):
    """
    Sehr schneller Grobtest — nur Kandidatenerkennung.
    Niedrige Schwelle, kurze Messzeit, breitere Bandbreite.
    """
    freq_hz = int(freq_mhz * 1e6)
    cmd = (f"timeout {timeout_s}s rtl_fm -M fm -f {freq_hz} "
           f"-s {bandwidth_hz} -l {squelch} - 2>/dev/null | wc -c")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout_s + 1.0)
        count = int((r.stdout or "0").strip() or "0")
        log.debug(f"Scanner fast-detect: freq={freq_mhz} bw={bandwidth_hz} bytes={count}")
        return count > 180
    except Exception:
        return False


def _detect_signal_confirm(freq_mhz, bandwidth_hz, timeout_s=0.65, squelch=None, settings=None):
    """
    Bestätigungstest — nur bei Fast-Detect Kandidaten.
    Normale Bandbreite, längere Messung, robustere Schwelle.
    """
    freq_hz = int(freq_mhz * 1e6)
    cmd = (f"timeout {timeout_s}s rtl_fm -M fm -f {freq_hz} "
           f"-s {bandwidth_hz} -l {squelch} - 2>/dev/null | wc -c")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout_s + 1.4)
        count = int((r.stdout or "0").strip() or "0")
        log.debug(f"Scanner confirm: freq={freq_mhz} bw={bandwidth_hz} bytes={count}")
        return count > 450
    except Exception:
        return False


def _detect_signal(freq_mhz, bandwidth_hz, timeout_s=0.55):
    """Standardprüfung (Fallback / Direktprüfung)."""
    return _detect_signal_confirm(freq_mhz, bandwidth_hz,
                                  timeout_s=timeout_s, squelch=20)


def _scan_bw_fast(band_id, default_bw):
    """Schnelle Scan-Bandbreite je Band — nur für Kandidatensuche."""
    if band_id in ("pmr446", "freenet", "lpd433"):
        return 25000
    if band_id == "cb":
        return 20000
    if band_id in ("vhf", "uhf"):
        return max(default_bw, 50000)
    return default_bw


def _range_step_fast(band_id, band_cfg):
    """Grobe Schrittweite für Fast-Scan bei Range-Bändern."""
    if band_id == "vhf":
        return 0.1
    if band_id == "uhf":
        return 0.1
    return band_cfg.get("step_fine", 0.025)


# ── Scan-Screen ───────────────────────────────────────────────────────────────

def _scan_list(S, channels, bw, direction, band_id=""):
    """
    Zweistufiger Suchlauf für Kanalbänder (PMR, CB, LPD, Freenet):
    1. Fast-Detect — schnell, empfindlich
    2. Confirm nur bei Kandidaten — verhindert Fehlalarme
    Merkt sich Startposition (scan_idx) für Fortsetzung.
    """
    n = len(channels)
    if n == 0:
        return None

    start_idx = _current_ch.get("scan_idx", _current_ch.get(band_id, 0))
    idx       = start_idx % n
    fast_bw   = _scan_bw_fast(band_id, bw)

    for _ in range(n):
        # v0.8.13: Scan abbrechen wenn andere Quelle aktiv wurde
        if (_scan_abort
                or (_src_state and _src_state.in_transition())
                or S.get("radio_type") not in ("", "SCANNER")):
            log.info(f"Scanner scan-list: abgebrochen band={band_id} radio_type={S.get('radio_type','')}")
            return None
        ch   = channels[idx]
        freq = ch["freq"]
        name = ch["name"]

        log.info(f"Scanner scan-list: FAST band={band_id} ch={name} freq={freq} bw={fast_bw}")
        if _detect_signal_fast(freq, fast_bw):
            log.info(f"Scanner scan-list: CANDIDATE band={band_id} ch={name} freq={freq}")
            if _detect_signal_confirm(freq, bw):
                log.action("Scanner", f"Signal: {name} @ {freq} MHz")
                _current_ch["scan_idx"] = idx
                if band_id:
                    _current_ch[band_id] = idx
                return ch
            else:
                log.info(f"Scanner scan-list: FALSE_POSITIVE band={band_id} ch={name}")

        idx = (idx + direction) % n

    ipc.write_progress("Scan beendet", "Kein Signal", color="orange")
    time.sleep(0.8)
    ipc.clear_progress()
    return None


def _scan_range(S, band, bw, direction, band_id=""):
    """
    Zweistufiger Range-Scan für VHF/UHF:
    1. Grober Fast-Scan (step_fast)
    2. Confirm auf Kandidaten mit Normalbandbreite
    """
    step_fast = _range_step_fast(band_id, band)
    total     = max(1, round((band["max"] - band["min"]) / step_fast))
    freq      = band.get("start", band["min"])
    fast_bw   = _scan_bw_fast(band_id, bw)

    for _ in range(total):
        # v0.8.13: Scan abbrechen wenn andere Quelle aktiv wurde
        if (_scan_abort
                or (_src_state and _src_state.in_transition())
                or S.get("radio_type") not in ("", "SCANNER")):
            log.info(f"Scanner scan-range: abgebrochen band={band_id} radio_type={S.get('radio_type','')}")
            return None
        log.info(f"Scanner scan-range: FAST band={band_id} freq={freq:.3f} bw={fast_bw}")
        if _detect_signal_fast(freq, fast_bw):
            log.info(f"Scanner scan-range: CANDIDATE band={band_id} freq={freq:.3f}")
            if _detect_signal_confirm(freq, bw):
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

# ── Manuell Frequenz ──────────────────────────────────────────────────────────


def _freq_input(band):
    """Frequenz via headless Trigger-Input (up/down/left/right/enter/back)."""
    freq = band["start"]
    deadline = __import__("time").time() + 60
    while __import__("time").time() < deadline:
        ipc.write_progress(
            f"{band['short']} Frequenz",
            f"{freq:.3f} MHz  (↑↓ fein  ←→ grob  Enter=OK  Back=Abbruch)",
            color="blue"
        )
        if not __import__("os").path.exists(ipc.CMD_FILE):
            __import__("time").sleep(0.15)
            continue
        try:
            cmd = open(ipc.CMD_FILE).read().strip()
            __import__("os").remove(ipc.CMD_FILE)
        except Exception:
            continue
        if   cmd == "up":    freq = min(band["max"], round(freq + band["step_fine"],   3))
        elif cmd == "down":  freq = max(band["min"], round(freq - band["step_fine"],   3))
        elif cmd == "right": freq = min(band["max"], round(freq + band["step_coarse"], 3))
        elif cmd == "left":  freq = max(band["min"], round(freq - band["step_coarse"], 3))
        elif cmd in ("enter",):
            ipc.clear_progress(); return freq
        elif cmd in ("back",):
            ipc.clear_progress(); return None
    ipc.clear_progress()
    return None

# ── Menu ─────────────────────────────────────────────────────────────────────

# build_items entfernt

def _get_channels(band_id):
    b = BANDS.get(band_id, {})
    return b.get("channels", [])

def _play_channel(band_id, idx, S):
    """Kanal abspielen und S-State für Menü aktualisieren."""
    chs = _get_channels(band_id)
    if not chs or idx >= len(chs): return
    ch   = chs[idx]
    name = ch.get("name", f"K{ch.get('ch',idx+1):02d}")
    freq = ch.get("freq","")
    S[f"scanner_{band_id}"] = f"{name}  {freq} MHz"
    play_freq(freq, name, BANDS[band_id]["bw"], S)

def _set_scanner_label(band_id, text, S):
    """Scanner-Statustext in State setzen."""
    S[f"scanner_{band_id}"] = text


def _play_band_freq(band_id, freq, S, settings=None):
    """Frequenz für kontinuierliche Bänder (VHF/UHF) spielen."""
    b = BANDS.get(band_id, {}).get("band", {})
    if not b:
        return
    freq = max(b["min"], min(b["max"], round(freq, 3)))
    b["start"] = freq
    name = f"{b.get('short', band_id.upper())} {freq:.3f} MHz"
    _set_scanner_label(band_id, name, S)
    log.info(f"Scanner: PLAY_FREQ band={band_id} freq={freq}")
    play_freq(freq, name, BANDS[band_id]["bw"], S)


def channel_up(band_id, S):
    chs = _get_channels(band_id)
    if not chs: return
    idx = (_current_ch.get(band_id, -1) + 1) % len(chs)
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S)

def channel_down(band_id, S):
    chs = _get_channels(band_id)
    if not chs: return
    idx = (_current_ch.get(band_id, 1) - 1) % len(chs)
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S)

def channel_jump(band_id, delta, S):
    """Kanal-Sprung um N Schritte (positiv/negativ). Für AVRCP fast_forward/rewind."""
    chs = _get_channels(band_id)
    if not chs: return
    cur = _current_ch.get(band_id, 0)
    idx = (cur + delta) % len(chs)
    _current_ch[band_id] = idx
    _play_channel(band_id, idx, S)
    log.info(f"Scanner channel_jump band={band_id} delta={delta} idx={idx}")

def freq_step(band_id, delta_mhz, S, settings=None):
    """Frequenzschritt für VHF/UHF um delta_mhz (±0.025 oder ±1.0 MHz)."""
    b = BANDS.get(band_id, {})
    if "band" not in b:
        return  # nur für kontinuierliche Bänder (VHF/UHF)
    band = b["band"]
    cur  = band.get("start", band["min"])
    new_freq = round(cur + delta_mhz, 3)
    if new_freq > band["max"]: new_freq = band["min"]
    if new_freq < band["min"]: new_freq = band["max"]
    log.info(f"Scanner: STEP band={band_id} delta={delta_mhz:+.3f} -> {new_freq:.3f}")
    _play_band_freq(band_id, new_freq, S, settings)

def set_freq(band_id, freq_mhz, S, settings=None):
    """Direkte Frequenz für VHF/UHF setzen."""
    b = BANDS.get(band_id, {}).get("band", {})
    if not b:
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
    _play_band_freq(band_id, freq, S, settings)


def freq_input_screen(band_id, settings=None):
    """Manuelle Frequenzeingabe via File-Trigger (up=1 down=0 right=. left=del enter=ok back=abbruch)."""
    b = BANDS.get(band_id, {}).get("band", {})
    if not b:
        return None
    freq   = b.get("start", b["min"])
    text   = f"{freq:.3f}"
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
        if   cmd == "up":     text += "1"
        elif cmd == "down":   text += "0"
        elif cmd == "right":  text = text + "." if "." not in text else text
        elif cmd == "left":   text = text[:-1] if text else ""
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


def scan_next(band_id, S, settings=None):
    """Squelch-Scan vorwärts — erstes Signal spielen (zweistufig Fast+Confirm)."""
    global _scan_abort
    _scan_abort = False   # v0.8.13: neuer Scan beginnt, altes Abort-Flag zurücksetzen
    b = BANDS.get(band_id, {})
    log.info(f"Scanner: SCAN_NEXT band={band_id}")
    if "channels" in b:
        ch = _scan_list(S, b["channels"], b["bw"], 1, band_id=band_id)
    else:
        ch = _scan_range(S, b["band"], b["bw"], 1, band_id=band_id)
    if ch:
        if ch.get("freq") and "MHz" not in ch["name"]:
            _set_scanner_label(band_id, f"{ch['name']}  {ch['freq']} MHz", S)
        else:
            _set_scanner_label(band_id, ch["name"], S)
        play_freq(ch["freq"], ch["name"], b["bw"], S)

def scan_prev(band_id, S, settings=None):
    """Squelch-Scan rückwärts — erstes Signal spielen (zweistufig Fast+Confirm)."""
    global _scan_abort
    _scan_abort = False   # v0.8.13: neuer Scan beginnt, altes Abort-Flag zurücksetzen
    b = BANDS.get(band_id, {})
    log.info(f"Scanner: SCAN_PREV band={band_id}")
    if "channels" in b:
        ch = _scan_list(S, b["channels"], b["bw"], -1, band_id=band_id)
    else:
        ch = _scan_range(S, b["band"], b["bw"], -1, band_id=band_id)
    if ch:
        if ch.get("freq") and "MHz" not in ch["name"]:
            _set_scanner_label(band_id, f"{ch['name']}  {ch['freq']} MHz", S)
        else:
            _set_scanner_label(band_id, ch["name"], S)
        play_freq(ch["freq"], ch["name"], b["bw"], S)
