"""
status.py - System-Status Cache (non-blocking)
PiDrive Project - GPL-v3

v0.8.9:
- BT-Status robust via bluetoothctl info (nicht nur hciconfig)
- bt_device immer konsistent mit bt_status
- bt_status: verbunden / getrennt / verbindet / aus
"""

import subprocess
import threading
import time
from settings import load_settings

S = {
    "wifi":            False,
    "wifi_ssid":       "",
    "bt":              False,
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
        new["wifi"]     = "Soft blocked: no" in rk
        new["wifi_ssid"] = _run("iwgetid -r 2>/dev/null", timeout=2)

        hi = _run("hostname -I 2>/dev/null", timeout=2)
        new["ip"] = hi.split()[0] if hi else ""

        # BT — robust via bluetoothctl info
        hc = _run("hciconfig 2>/dev/null", timeout=2)
        bt_adapter_up = "UP RUNNING" in hc

        new["bt"]        = False
        new["bt_device"] = ""
        new["bt_status"] = "aus" if not bt_adapter_up else "getrennt"

        if bt_adapter_up:
            settings  = load_settings()
            last_mac  = settings.get("bt_last_mac",  "").strip()
            last_name = settings.get("bt_last_name", "").strip()

            if last_mac:
                info = _run(f"bluetoothctl info {last_mac} 2>/dev/null", timeout=4)
                low  = info.lower()
                if "connected: yes" in low:
                    new["bt"]        = True
                    new["bt_device"] = last_name or last_mac
                    new["bt_status"] = "verbunden"
                elif "paired: yes" in low or "trusted: yes" in low:
                    new["bt"]        = False
                    new["bt_device"] = last_name or last_mac
                    new["bt_status"] = "getrennt"
                else:
                    new["bt"]        = False
                    new["bt_device"] = last_name or ""
                    new["bt_status"] = "getrennt"

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
