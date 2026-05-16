"""
status.py - System-Status Cache (non-blocking)
PiDrive v0.9.14-final

Neu/konsolidiert:
- BT-Status robust via bluetoothctl info
- bt_device konsistent mit bt_status
- bt_status: verbunden / getrennt / verbindet / aus
- exportiert Runtime-Prozessliste für WebUI
"""

import subprocess
import threading
import time
from settings import load_settings

S = {
    "wifi":            False,
    "wifi_ssid":       "",
    "bt":              False,          # True = Gerät verbunden
    "bt_on":           False,          # True = Adapter UP (auch ohne Verbindung)
    "bt_device":       "",
    "bt_status":       "getrennt",
    "ip":              "",
    "spotify":         False,
    "spotify_track":   "",
    "spotify_artist":  "",
    "spotify_album":   "",
    "radio_playing":   False,
    "radio_station":   "",
    "radio_type":      "",
    "radio_name":      "",
    "library_playing": False,
    "library_track":   "",
    "audio_output":    "auto",
    "processes":       [],
    "ts":              0,
}

_lock       = threading.Lock()
_refresh_iv = 5.0
_running    = False


def _run(cmd, timeout=3):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _refresh_loop():
    global _running
    while _running:
        _do_refresh()
        time.sleep(_refresh_iv)


def _do_refresh():
    new = {}
    try:
        # WiFi
        rk = _run("rfkill list wifi 2>/dev/null", timeout=2)
        new["wifi"] = "Soft blocked: no" in rk
        new["wifi_ssid"] = _run("iwgetid -r 2>/dev/null", timeout=2)

        hi = _run("hostname -I 2>/dev/null", timeout=2)
        new["ip"] = hi.split()[0] if hi else ""

        # BT — robust via bluetoothctl info
        hc = _run("hciconfig 2>/dev/null", timeout=2)
        bt_adapter_up = "UP RUNNING" in hc

        new["bt"] = False
        new["bt_on"] = bt_adapter_up
        new["bt_device"] = ""
        new["bt_status"] = "aus" if not bt_adapter_up else "getrennt"

        if bt_adapter_up:
            settings = load_settings()
            last_mac = settings.get("bt_last_mac", "").strip()
            last_name = settings.get("bt_last_name", "").strip()

            # Schritt 1: last_mac aus Settings prüfen
            if last_mac:
                info = _run(f"bluetoothctl info {last_mac} 2>/dev/null", timeout=5)
                if "connected: yes" in info.lower():
                    new["bt"] = True
                    new["bt_device"] = last_name or last_mac
                    new["bt_status"] = "verbunden"
                elif "paired: yes" in info.lower() or "trusted: yes" in info.lower():
                    new["bt"] = False
                    new["bt_device"] = last_name or last_mac
                    new["bt_status"] = "getrennt"
                else:
                    new["bt"] = False
                    new["bt_device"] = last_name or ""
                    new["bt_status"] = "getrennt"

            # Schritt 2: Fallback — alle verbundenen Geräte prüfen (z.B. nach manuellem bluetoothctl connect)
            if not new["bt"]:
                try:
                    # "bluetoothctl devices Connected" (BlueZ 5.60+)
                    conn_out = _run("bluetoothctl devices Connected 2>/dev/null", timeout=4)
                    if not conn_out:
                        # Fallback: alle Paired-Geräte durchgehen
                        paired = _run("bluetoothctl devices Paired 2>/dev/null", timeout=4)
                        for line in paired.splitlines():
                            parts = line.split()
                            if len(parts) >= 2 and ":" in parts[1]:
                                mac = parts[1]
                                info = _run(f"bluetoothctl info {mac} 2>/dev/null", timeout=3)
                                if "connected: yes" in info.lower():
                                    name = " ".join(parts[2:]) if len(parts) > 2 else mac
                                    conn_out = f"Device {mac} {name}"
                                    break
                    if conn_out and conn_out.strip():
                        parts = conn_out.strip().split()
                        if len(parts) >= 2:
                            found_mac  = parts[1] if ":" in parts[1] else (parts[2] if len(parts) > 2 else "")
                            found_name = " ".join(parts[2:]) if len(parts) > 2 else found_mac
                            if found_mac:
                                new["bt"]        = True
                                new["bt_device"] = found_name or found_mac
                                new["bt_status"] = "verbunden"
                                # MAC für nächstes Mal speichern
                                if not last_mac and found_mac:
                                    try:
                                        settings["bt_last_mac"]  = found_mac
                                        settings["bt_last_name"] = found_name
                                        from settings import save_settings as _ss
                                        _ss(settings)
                                    except Exception: pass
                except Exception:
                    pass

        # Spotify
        sp = _run("systemctl is-active raspotify 2>/dev/null", timeout=2)
        new["spotify"] = (sp == "active")
        new["spotify_track"]  = ""
        new["spotify_artist"] = ""
        new["spotify_album"]  = ""
        if new["spotify"]:
            try:
                with open("/tmp/spotify_status") as f:
                    line = f.readline().strip()
                if "|" in line:
                    p = line.split("|")
                    new["spotify_track"]  = p[1][:40] if len(p) > 1 else ""
                    new["spotify_artist"] = p[2][:30] if len(p) > 2 else ""
                    new["spotify_album"]  = p[3][:30] if len(p) > 3 else ""
            except Exception:
                pass

        # Runtime-Prozesse für WebUI
        ps = _run(
            r"ps ax -o pid=,comm=,cmd= | egrep 'python3|mpv|rtl_fm|welle-cli|librespot|pulseaudio|bluetoothd' | grep -v grep",
            timeout=4
        )
        new["processes"] = [ln.strip() for ln in ps.splitlines() if ln.strip()]

    except Exception:
        pass

    new["ts"] = time.time()
    with _lock:
        S.update(new)


def start():
    global _running
    if _running:
        return
    _running = True
    _do_refresh()
    t = threading.Thread(target=_refresh_loop, daemon=True)
    t.start()


def stop():
    global _running
    _running = False


def refresh(force=False):
    if force:
        _do_refresh()


def invalidate():
    with _lock:
        S["ts"] = 0