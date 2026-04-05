"""
modules/musik.py - Spotify & Wiedergabe Modul
PiDrive Project - GPL-v3
"""

import subprocess
import time
from ui import Item, Category, show_message, pick_list, C_PURPLE

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def spotify_toggle(S):
    if S["spotify"]:
        _bg("systemctl stop raspotify")
    else:
        _bg("systemctl start raspotify")
    S["ts"] = 0

def get_track_label(S):
    if not S["spotify"]:
        return "Spotify gestoppt"
    track = S.get("spotify_track", "")
    artist = S.get("spotify_artist", "")
    if track and artist:
        return f"{artist} - {track}"[:32]
    elif track:
        return track[:32]
    return "Warte auf Wiedergabe..."

def build_category(screen, S, settings):
    """Gibt die Musik-Kategorie zurueck."""

    def spotify_info_action():
        track  = S.get("spotify_track", "-")
        artist = S.get("spotify_artist", "-")
        album  = S.get("spotify_album",  "-")
        show_message(screen, track[:20], f"{artist} | {album}"[:36],
                     color=C_PURPLE)
        time.sleep(3)

    items = [
        Item("Spotify",
             sub=lambda: "Laeuft" if S["spotify"] else "Gestoppt",
             toggle=lambda: spotify_toggle(S),
             state=lambda: S["spotify"]),
        Item("Wiedergabe",
             sub=lambda: get_track_label(S),
             action=spotify_info_action),
    ]

    return items
