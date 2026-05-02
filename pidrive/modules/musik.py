"""
modules/musik.py - Spotify Modul
PiDrive v0.8.10 - pygame-frei, Altlasten entfernt
"""

import subprocess
import ipc
import log

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def spotify_toggle(S):
    if S.get("spotify"):
        log.info("Spotify: stop raspotify")
        _bg("systemctl stop raspotify")
        # v0.10.2: source_state aktualisieren (defensiv)
        if _src_state:
            try: _src_state.commit_source("idle")
            except Exception: pass
    else:
        log.info("Spotify: start raspotify")
        _bg("systemctl start raspotify")
        # Hinweis: commit_source("spotify") erfolgt verzögert nach Aktivierung
        # (async systemctl start) — main_core.py übernimmt den Commit
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
