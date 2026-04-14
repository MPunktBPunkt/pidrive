"""
modules/fm.py - FM Radio mit RTL-SDR
PiDrive - GPL-v3

Hardware: RTL-SDR Stick
Software: rtl-sdr Paket (rtl_fm) + sox oder mpv

Installation:
  sudo apt install rtl-sdr sox

Frequenzen werden in config/fm_stations.json gespeichert.
Format: [{"name": "Bayern 3", "freq": "99.4"}]
"""

import subprocess
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
import os
import json
import time
import ipc
import log

STATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "../config/fm_stations.json")

_player_proc = None

# Voreingestellte FM-Stationen (deutschlandweit)
DEFAULT_STATIONS = [
    {"name": "Bayern 3",     "freq": "99.4"},
    {"name": "Lokal FM",     "freq": "104.4"},
    {"name": "Bayern 1",     "freq": "95.8"},
    {"name": "Antenne Bayern","freq": "102.2"},
    {"name": "Radio BOB",    "freq": "89.0"},
    {"name": "DLF",          "freq": "91.3"},
    {"name": "DLF Nova",     "freq": "98.7"},
    {"name": "SWR3",         "freq": "96.9"},
    {"name": "NDR 2",        "freq": "87.9"},
]

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
    out = _run("lsusb 2>/dev/null | grep -i 'RTL\\|2832\\|2838'", capture=True)
    return bool(out)

def is_rtlfm_available():
    out = _run("which rtl_fm 2>/dev/null", capture=True)
    return bool(out)

def load_stations():
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return list(DEFAULT_STATIONS)

def save_stations(stations):
    try:
        os.makedirs(os.path.dirname(STATIONS_FILE), exist_ok=True)
        with open(STATIONS_FILE, "w") as f:
            json.dump(stations, f, indent=2, ensure_ascii=False)
        log.info(f"FM: {len(stations)} Stationen gespeichert")
    except Exception as e:
        log.error(f"FM Stationen speichern: {e}")

def play_station(station, S, settings=None):
    """FM Station abspielen via rtl_fm | mpv."""
    global _player_proc
    stop(S)

    freq = station.get("freq", "")
    name = station.get("name", "")
    if settings is not None:
        settings["last_fm_station"] = station
        try:
            import json as _j
            with open("/home/pi/pidrive/pidrive/config/settings.json","w") as _f:
                _j.dump(settings, _f, indent=2)
        except Exception:
            pass

    if not freq:
        log.error("FM play: keine Frequenz")
        return

    freq_hz = f"{float(freq) * 1e6:.0f}"

    try:
        # RTL-SDR verfügbar?
        if _rtlsdr:
            if not _rtlsdr.detect_usb().get("present"):
                S["radio_playing"] = False
                S["radio_station"] = "RTL-SDR nicht gefunden"
                return
            if _rtlsdr.is_busy():
                import log as _l; _l.warn("FM: RTL-SDR belegt")
                return
        # rtl_fm -> audio pipe
        from modules import audio as _audio
        _mpv_extra = _audio.get_mpv_args(settings, source="fm")
        _is_bt = "--ao=pulse" in " ".join(_mpv_extra)
        if _is_bt:
            cmd = (
                "rtl_fm -M wbfm -f " + freq_hz + " -s 250000 -r 32000 -A fast - 2>/dev/null | "
                "mpv --no-video --really-quiet --title=pidrive_fm "
                "--demuxer=rawaudio --demuxer-rawaudio-rate=32000 "
                "--demuxer-rawaudio-channels=1 " + " ".join(_mpv_extra) + " - 2>/dev/null"
            )
        else:
            cmd = (
                "rtl_fm -M wbfm -f " + freq_hz + " -s 250000 -r 32000 -A fast - 2>/dev/null | "
                "aplay -t raw -r 32000 -f S16_LE -c 1 -D hw:1,0 2>/dev/null"
            )
        if _rtlsdr:
            try:
                _player_proc = _rtlsdr.start_process(
                    cmd, owner="fm_play", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as _e:
                import log as _l; _l.error("FM: RTL-SDR Lock: " + str(_e))
                return
        else:
            _player_proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        S["radio_playing"] = True
        S["radio_station"] = f"FM: {name} ({freq} MHz)"
        S["radio_type"]    = "FM"
        log.action("FM", f"Wiedergabe: {name} ({freq} MHz)")
    except Exception as e:
        log.error(f"FM play Fehler: {e}")

def stop(S):
    global _player_proc
    if _rtlsdr:
        _rtlsdr.stop_process()
    _bg("pkill -f pidrive_fm 2>/dev/null")
    _bg("pkill -f rtl_fm 2>/dev/null")
    if _player_proc:
        try: _player_proc.terminate()
        except Exception: pass
        _player_proc = None
    if S.get("radio_type") == "FM":
        S["radio_playing"] = False
        S["radio_station"] = ""


def freq_input_screen(screen=None):
    """Headless Frequenz-Eingabe via File-Trigger. Gibt Frequenz-String zurueck."""
    freq = 87.5
    deadline = __import__("time").time() + 60
    while __import__("time").time() < deadline:
        ipc.write_progress(
            "FM Frequenz",
            f"{freq:.1f} MHz  (↑↓ 0.1  ←→ 1.0  Enter=OK  Back=Abbruch)",
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
        if   cmd == "up":    freq = min(108.0, round(freq + 0.1, 1))
        elif cmd == "down":  freq = max(87.5,  round(freq - 0.1, 1))
        elif cmd == "right": freq = min(108.0, round(freq + 1.0, 1))
        elif cmd == "left":  freq = max(87.5,  round(freq - 1.0, 1))
        elif cmd in ("enter",):
            ipc.clear_progress(); return f"{freq:.1f}"
        elif cmd in ("back",):
            ipc.clear_progress(); return None
    ipc.clear_progress()
    return None

# build_items() entfernt in v0.7.1

def scan_stations(S):
    """FM Suchlauf via rtl_fm Squelch. Gibt Liste von Stationen zurueck.

    Timeout muss > USB-Init-Zeit von rtl_fm sein (~0.5s).
    Faustformel: 1.5s je Frequenz, 0.2 MHz Raster = ~88 Frequenzen = ~2.5 Min.
    Squelch -l 30: empfindlich genug fuer Innenräume mit Fensterantenne.
    """
    import subprocess, time
    results = []
    # 87.6–107.8 MHz in 0.2 MHz Schritten (88 Frequenzen, ~2.5 Min)
    freq = 87.6
    while freq <= 107.9:
        freq_hz = int(freq * 1e6)
        # 1.5s: USB-Init (~0.5s) + Tuning (~0.3s) + Datenfluss (~0.7s)
        cmd = (f"timeout 1.5s rtl_fm -M wbfm -f {freq_hz} "
               f"-s 200000 -l 30 - 2>/dev/null | wc -c")
        try:
            r = subprocess.run(cmd, shell=True,
                               capture_output=True, text=True, timeout=3)
            count = int(r.stdout.strip() or "0")
            if count > 5000:  # bei 1.5s + Signal: viele Bytes erwartet
                results.append({"id": f"fm_{str(freq).replace('.','_')}",
                                 "name": f"FM {freq:.1f} MHz",
                                 "freq_mhz": freq, "enabled": True, "favorite": False})
                log.info(f"FM Scan: Signal @ {freq:.1f} MHz ({count} bytes)")
        except Exception:
            pass
        freq = round(freq + 0.2, 1)
    log.info(f"FM Scan abgeschlossen: {len(results)} Sender")
    return results


def play_next(S, stations):
    """Naechste FM Station abspielen."""
    if not stations:
        return
    current = S.get("radio_station", "")
    names   = [s.get("name","") for s in stations]
    idx = 0
    for i, name in enumerate(names):
        if name in current:
            idx = (i + 1) % len(stations); break
    play_station(stations[idx], S)


def play_prev(S, stations):
    """Vorherige FM Station abspielen."""
    if not stations:
        return
    current = S.get("radio_station", "")
    names   = [s.get("name","") for s in stations]
    idx = 0
    for i, name in enumerate(names):
        if name in current:
            idx = (i - 1) % len(stations); break
    play_station(stations[idx], S)
