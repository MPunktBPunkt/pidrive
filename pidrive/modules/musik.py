"""
modules/musik.py - Spotify & Wiedergabe Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, time, ipc

def _bg(cmd):
    try: subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def spotify_toggle(S):
    _bg("systemctl stop raspotify" if S["spotify"] else "systemctl start raspotify")
    S["ts"] = 0

def get_track_label(S):
    if not S["spotify"]: return "Spotify gestoppt"
    track  = S.get("spotify_track",  "")
    artist = S.get("spotify_artist", "")
    if track and artist: return f"{artist} - {track}"[:32]
    return track[:32] if track else "Warte auf Wiedergabe..."

def build_category(screen, S, settings):
    def spotify_info():
        track  = S.get("spotify_track",  "-")
        artist = S.get("spotify_artist", "-")
        album  = S.get("spotify_album",  "-")
        ipc.write_progress(track[:24], f"{artist} | {album}"[:36], color="blue")
        time.sleep(3); ipc.clear_progress()

    return [
        Item("Spotify",
             sub=lambda: "Laeuft" if S["spotify"] else "Gestoppt",
             toggle=lambda: spotify_toggle(S),
             state=lambda: S["spotify"]),
        Item("Wiedergabe",
             sub=lambda: get_track_label(S),
             action=spotify_info),
    ]
