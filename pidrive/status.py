"""
status.py - System-Status Cache
PiDrive Project - GPL-v3
"""

import subprocess
import time

# Globaler Status-Cache
S = {
    "wifi":             False,
    "conn":             False,
    "ssid":             "",
    "bt":               False,
    "bt_sink":          "",
    "bt_connected_dev": "",
    "ip":               "-",
    "host":             "-",
    "spotify":          False,
    "spotify_track":    "",
    "spotify_artist":   "",
    "spotify_album":    "",
    "radio_playing":    False,
    "radio_station":    "",
    "library_playing":  False,
    "library_track":    "",
    "ts":               0,
}

def _run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""

def refresh(force=False):
    """Status aktualisieren (max alle 6 Sekunden)."""
    if not force and time.time() - S["ts"] < 6:
        return

    try:
        # WiFi
        rk = _run("rfkill list wifi 2>/dev/null")
        S["wifi"] = "Soft blocked: no" in rk
        ip_out = _run("ip a show wlan0 2>/dev/null")
        S["conn"] = "inet " in ip_out
        S["ssid"] = _run("iwgetid -r 2>/dev/null")

        # Bluetooth
        hc = _run("hciconfig 2>/dev/null")
        S["bt"] = "UP RUNNING" in hc
        bt_sink = _run("pactl list sinks short 2>/dev/null | grep bluez")
        S["bt_sink"] = bt_sink.split()[0] if bt_sink else ""
        bt_dev = _run("bluetoothctl info 2>/dev/null | grep 'Name:' | head -1")
        S["bt_connected_dev"] = bt_dev.replace("Name:", "").strip()

        # System
        hi = _run("hostname -I 2>/dev/null")
        S["ip"] = hi.split()[0] if hi else "-"
        S["host"] = _run("hostname")

        # Spotify/Raspotify
        sp = _run("systemctl is-active raspotify 2>/dev/null")
        S["spotify"] = (sp == "active")

        # Spotify aktueller Track (via /tmp/spotify_status von onevent Script)
        if S["spotify"]:
            _read_spotify_status()

    except Exception:
        pass

    S["ts"] = time.time()

def _read_spotify_status():
    """Liest /tmp/spotify_status das vom onevent Script geschrieben wird."""
    try:
        with open("/tmp/spotify_status", "r") as f:
            line = f.readline().strip()
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                S["spotify_track"]  = parts[1][:40] if parts[1] else ""
                S["spotify_artist"] = parts[2][:30] if len(parts) > 2 else ""
                S["spotify_album"]  = parts[3][:30] if len(parts) > 3 else ""
    except Exception:
        pass

def invalidate():
    """Cache sofort invalidieren."""
    S["ts"] = 0
