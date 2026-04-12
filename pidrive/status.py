"""
status.py - System-Status Cache (non-blocking)
PiDrive Project - GPL-v3

Laeuft in eigenem Hintergrund-Thread — blockiert nie den Main-Loop.
"""

import subprocess
import threading
import time

# Globaler Status-Cache (thread-safe durch Lock)
S = {
    "wifi":             False,
    "wifi_ssid":        "",
    "bt":               False,
    "bt_device":        "",
    "ip":               "",
    "spotify":          False,
    "spotify_track":    "",
    "spotify_artist":   "",
    "spotify_album":    "",
    "radio_playing":    False,
    "radio_station":    "",
    "radio_type":       "",
    "radio_name":       "",
    "library_playing":  False,
    "library_track":    "",
    "audio_output":     "auto",
    "ts":               0,
}

_lock       = threading.Lock()
_refresh_iv = 5.0   # Sekunden zwischen Refreshes
_running    = False


def _run(cmd, timeout=3):
    """Subprocess-Wrapper mit Timeout."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _refresh_loop():
    """Laeuft im Hintergrund-Thread."""
    global _running
    while _running:
        _do_refresh()
        time.sleep(_refresh_iv)


def _do_refresh():
    """Alle Systemwerte ermitteln und cache aktualisieren."""
    new = {}
    try:
        # WiFi: rfkill + iwgetid zusammenfassen
        rk = _run("rfkill list wifi 2>/dev/null", timeout=2)
        new["wifi"] = "Soft blocked: no" in rk
        new["wifi_ssid"] = _run("iwgetid -r 2>/dev/null", timeout=2)

        # IP (schneller als ip a show)
        hi = _run("hostname -I 2>/dev/null", timeout=2)
        new["ip"] = hi.split()[0] if hi else ""

        # Bluetooth: hciconfig (schnell)
        hc = _run("hciconfig 2>/dev/null", timeout=2)
        new["bt"] = "UP RUNNING" in hc

        # Spotify
        sp = _run("systemctl is-active raspotify 2>/dev/null", timeout=2)
        new["spotify"] = (sp == "active")

        # Spotify Track
        new["spotify_track"] = ""
        new["spotify_artist"] = ""
        new["spotify_album"] = ""
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

    # Atomar in S schreiben
    with _lock:
        S.update(new)


def start():
    """Hintergrund-Thread starten."""
    global _running
    if _running:
        return
    _running = True
    _do_refresh()  # Sofort einmal ausführen
    t = threading.Thread(target=_refresh_loop, daemon=True)
    t.start()


def stop():
    global _running
    _running = False


def refresh(force=False):
    """Kompatibilitaets-Stub — refresh läuft jetzt im Hintergrund."""
    if force:
        _do_refresh()


def invalidate():
    """Cache invalidieren — naechstes refresh() liest neu."""
    with _lock:
        S["ts"] = 0
