"""
modules/webradio.py - Webradio Modul
PiDrive Project - GPL-v3

Benoetigt: mpv (sudo apt install mpv)
Stationen: config/stations.json
"""

import subprocess
import json
import os
import time
from ui import Item, show_message, pick_list, C_BLUE

STATIONS_FILE = os.path.join(os.path.dirname(__file__), "../config/stations.json")
_player_proc = None

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def load_stations():
    """Stationen aus JSON laden."""
    try:
        with open(STATIONS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def is_playing(S):
    return S.get("radio_playing", False)

def play_station(station, S):
    """Station abspielen via mpv."""
    global _player_proc
    stop(S)
    try:
        _player_proc = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet",
             "--title=pidrive_radio", station["url"]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        S["radio_playing"] = True
        S["radio_station"] = station["name"]
    except FileNotFoundError:
        # mpv nicht installiert
        S["radio_playing"] = False
        S["radio_station"] = "mpv fehlt!"

def stop(S):
    global _player_proc
    _bg("pkill -f pidrive_radio 2>/dev/null")
    if _player_proc:
        try:
            _player_proc.terminate()
        except Exception:
            pass
        _player_proc = None
    S["radio_playing"] = False
    S["radio_station"] = ""

def build_items(screen, S):
    """Gibt Webradio-Untermenue-Items zurueck."""
    stations = load_stations()

    def select_station():
        names = [f"{st['name']} ({st['genre']})" for st in stations]
        if not names:
            show_message(screen, "Webradio", "Keine Stationen konfiguriert")
            time.sleep(2)
            return
        chosen = pick_list(screen, "Stationen", names, color=C_BLUE)
        if chosen:
            idx = names.index(chosen)
            show_message(screen, "Webradio", f"Lade: {stations[idx]['name']}...")
            play_station(stations[idx], S)

    def stop_action():
        stop(S)
        show_message(screen, "Webradio", "Gestoppt")
        time.sleep(1)

    items = [
        Item("Station waehlen",
             sub=lambda: S.get("radio_station", "Keine") if S.get("radio_playing") else "Gestoppt",
             action=select_station),
        Item("Stop",
             action=stop_action),
    ]

    return items
