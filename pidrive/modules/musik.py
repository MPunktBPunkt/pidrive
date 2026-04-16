"""
modules/musik.py - Spotify Modul
PiDrive v0.8.10 - pygame-frei, Altlasten entfernt
"""

import subprocess
import ipc
import log


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def spotify_toggle(S):
    if S.get("spotify"):
        log.info("Spotify: stop raspotify")
        _bg("systemctl stop raspotify")
    else:
        log.info("Spotify: start raspotify")
        _bg("systemctl start raspotify")
    S["ts"] = 0


def get_track_label(S):
    if not S.get("spotify"):
        return "Spotify gestoppt"
    track  = S.get("spotify_track", "")
    artist = S.get("spotify_artist", "")
    if track and artist:
        return f"{artist} - {track}"[:48]
    return track[:48] if track else "Warte auf Wiedergabe..."


def show_spotify_info(S):
    track  = S.get("spotify_track",  "-")
    artist = S.get("spotify_artist", "-")
    album  = S.get("spotify_album",  "-")
    ipc.write_progress(track[:24], f"{artist} | {album}"[:36], color="blue")
