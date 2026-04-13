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
        # rtl_fm -> mpv pipe
        from modules import audio as _audio
        _mpv_extra = " ".join(_audio.get_mpv_args(settings, source="fm"))
        cmd = (
            "rtl_fm -M wbfm -f " + freq_hz + " -r 200000 - 2>/dev/null | "
            "mpv --no-video --really-quiet --title=pidrive_fm "
            "--demuxer=rawaudio --demuxer-rawaudio-rate=200000 "
            "--demuxer-rawaudio-channels=1 " + _mpv_extra + " - 2>/dev/null"
        )
        _player_proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        S["radio_playing"] = True
        S["radio_station"] = f"FM: {name} ({freq} MHz)"
        S["radio_type"]    = "FM"
        log.action("FM", f"Wiedergabe: {name} ({freq} MHz)")
    except Exception as e:
        log.error(f"FM play Fehler: {e}")

def stop(S):
    global _player_proc
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
    """FM Suchlauf via rtl_fm Squelch. Gibt Liste von Stationen zurueck."""
    import subprocess, time
    results = []
    # 87.5–108.0 MHz in 0.1 MHz Schritten
    freq = 87.5
    while freq <= 108.0:
        freq_hz = int(freq * 1e6)
        cmd = f"timeout 0.4s rtl_fm -M wbfm -f {freq_hz} -s 200000 -l 70 - 2>/dev/null | wc -c"
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=2)
            if int(r.stdout.strip() or "0") > 1000:
                results.append({"id": f"fm_{str(freq).replace('.','_')}",
                                 "name": f"FM {freq:.1f} MHz",
                                 "freq_mhz": freq, "enabled": True, "favorite": False})
                log.info(f"FM Scan: Signal @ {freq:.1f} MHz")
        except Exception:
            pass
        freq = round(freq + 0.1, 1)
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
