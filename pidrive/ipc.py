"""
ipc.py - PiDrive Inter-Process Communication
Atomares JSON-Lesen/Schreiben zwischen Core und Display.
"""

import os
import json
import time

# Pfade
CMD_FILE     = "/tmp/pidrive_cmd"
STATUS_FILE  = "/tmp/pidrive_status.json"
MENU_FILE    = "/tmp/pidrive_menu.json"
PLAYING_FILE = "/tmp/pidrive_nowplaying.json"


def write_json(path, data):
    """Atomar schreiben: erst .tmp dann os.replace()."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        pass


def read_json(path, default=None):
    """JSON lesen, bei Fehler default zurückgeben."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def write_status(S, settings):
    """Status-JSON aus dem Status-Dict schreiben."""
    write_json(STATUS_FILE, {
        "wifi":       S.get("wifi", False),
        "wifi_ssid":  S.get("ssid", ""),
        "bt":         S.get("bt", False),
        "bt_device":  S.get("bt_connected_dev", ""),
        "spotify":    S.get("spotify", False),
        "track":      S.get("spotify_track", ""),
        "artist":     S.get("spotify_artist", ""),
        "album":      S.get("spotify_album", ""),
        "radio":      S.get("radio_playing", False),
        "radio_name": S.get("radio_station", ""),
        "library":    S.get("library_playing", False),
        "lib_track":  S.get("library_track", ""),
        "audio_out":  settings.get("audio_output", "auto"),
        "ip":         S.get("ip", "-"),
        "ts":         int(time.time()),
    })


def write_menu(cat_idx, cat_label, item_idx, item_label, radio_type=""):
    """Menü-Position schreiben."""
    write_json(MENU_FILE, {
        "cat":        cat_idx,
        "cat_label":  cat_label,
        "item":       item_idx,
        "item_label": item_label,
        "radio_type": radio_type,
    })
