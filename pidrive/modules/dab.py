"""
modules/dab.py - DAB+ Radio
PiDrive v0.6.1 — pygame-frei, Progress via IPC
"""

import subprocess
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
import threading
import os
import time
import log
import ipc

C_DAB = (0, 200, 180)

_player_proc = None
_scan_running = False
_scan_results = []

def _run(cmd, capture=False, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if capture else r.returncode == 0
    except Exception:
        return "" if capture else False

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def is_rtlsdr_available():
    out = _run("lsusb 2>/dev/null", capture=True)
    return any(k in out.lower() for k in ["rtl", "realtek", "2838", "0bda"])

def is_welle_available():
    return _run("which welle-cli", capture=True) != ""

def load_stations():
    import json
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        return json.load(open(path))
    except Exception:
        return []

def save_stations(stations):
    import json
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        with open(path, "w") as f:
            json.dump(stations, f, indent=2)
    except Exception as e:
        log.error(f"DAB save Fehler: {e}")

def scan_dab_channels(progress_cb=None):
    global _scan_running, _scan_results
    _scan_running = True
    _scan_results = []

    channels = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]
    found = []
    total = len(channels)

    for i, ch in enumerate(channels):
        if not _scan_running:
            break
        if progress_cb:
            progress_cb(int(i / total * 100),
                        f"Scanne {ch}... ({i}/{total})",
                        len(found))
                # Exklusiver Lock für RTL-SDR
        if _rtlsdr and _rtlsdr.is_busy():
            log.warn("DAB Scan: RTL-SDR belegt, ueberspringe " + ch)
            continue
        # welle-cli 2.2: alle Ausgaben auf stderr → mit 2>&1 fangen
        out = _run("timeout 6 welle-cli -c " + ch + " 2>&1",
                   capture=True, timeout=5)
        if out and "usb_claim_interface error" in out:
            log.warn("DAB: RTL-SDR blockiert auf Kanal " + ch +
                     " — DVB-Treiber geladen?")
            continue
        if out:
            # Strikt: NUR "Service label: NAME" ist ein echter Sender
            # Alle anderen welle-cli Ausgaben sind Debug/Fehler
            for line in out.splitlines():
                line = line.strip()
                if "Service label:" not in line and "service label:" not in line.lower():
                    continue
                name = line.split(":", 1)[-1].strip()
                if not name or len(name) < 2 or len(name) > 60:
                    continue
                # Nochmal prüfen: kein technischer Text
                bad = ["kHz","MHz","SoapySDR","OFDM","usb_","rtl_",
                       "welle-cli","InputFactory","Aborted","SyncOn",
                       "Wait","stream","clock","antenna","[INFO]","Error"]
                if any(b.lower() in name.lower() for b in bad):
                    continue
                if name not in [s["name"] for s in found]:
                    found.append({"name": name, "channel": ch, "ensemble": ""})
                    log.info("DAB gefunden: " + name + " auf " + ch)

    _scan_results = found
    _scan_running = False
    return found

def play_station(station, S, settings=None):
    global _player_proc
    stop(S)
    if settings is not None:
        settings["last_dab_station"] = station
        try:
            import json as _j
            with open("/home/pi/pidrive/pidrive/config/settings.json","w") as _f:
                _j.dump(settings, _f, indent=2)
        except Exception:
            pass
    ch   = station.get("channel", "")
    name = station.get("name", "")
    if not ch:
        return
    if _rtlsdr:
        if not _rtlsdr.detect_usb().get("present"):
            import log as _l; _l.error("DAB: kein RTL-SDR")
            return
        if _rtlsdr.is_busy():
            import log as _l; _l.warn("DAB: RTL-SDR belegt")
            return
    try:
        from modules import audio as _audio
        _mpv_args = " ".join(_audio.get_mpv_args(settings, source="dab"))
        _cmd = (
            "welle-cli -D 0 -c " + ch + " -s '" + name + "' -o - 2>/dev/null | "
            "mpv --no-video --really-quiet --title=pidrive_dab " + _mpv_args + " - 2>/dev/null"
        )
        _lock_ctx = (_rtlsdr.acquire_lock(owner="dab_play") if _rtlsdr
                     else __import__("contextlib").nullcontext())
        with _lock_ctx:
            _player_proc = subprocess.Popen(
                _cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        S["radio_playing"] = True
        S["radio_station"] = "DAB: " + name
        S["radio_type"]    = "DAB"
        log.action("DAB", "Wiedergabe: " + name + " (" + ch + ")")
    except Exception as e:
        log.error(f"DAB play Fehler: {e}")

def stop(S):
    global _player_proc, _scan_running
    _scan_running = False
    _bg("pkill -f pidrive_dab 2>/dev/null")
    _bg("pkill -f welle-cli 2>/dev/null")
    if _player_proc:
        try: _player_proc.terminate()
        except Exception: pass
        _player_proc = None
    S["radio_playing"] = False
    if S.get("radio_type") == "DAB":
        S["radio_station"] = ""

# build_items() entfernt in v0.7.1 — Menü wird von menu_model.py gebaut

def play_by_name(name, S):
    """DAB Station nach Name abspielen."""
    import json, os
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path))
        stations = data.get("stations", data) if isinstance(data, dict) else data
        for s in stations:
            if s.get("name","") == name:
                play_station(s, S); return
    except Exception as e:
        log.error(f"DAB play_by_name: {e}")


def play_next(S, stations):
    """Naechste DAB Station."""
    if not stations:
        return
    current = S.get("radio_station","")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name","") == current:
            idx = (i+1) % len(stations); break
    play_station(stations[idx], S)


def play_prev(S, stations):
    """Vorherige DAB Station."""
    if not stations:
        return
    current = S.get("radio_station","")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name","") == current:
            idx = (i-1) % len(stations); break
    play_station(stations[idx], S)
