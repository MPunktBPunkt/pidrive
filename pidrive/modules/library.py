"""
modules/library.py - MP3 Bibliothek mit Album-Art
PiDrive Project - GPL-v3

Benoetigt: mutagen (pip install mutagen)
           pygame (fuer Wiedergabe und Bild-Anzeige)
Musik-Pfad: settings["music_path"] (Standard: ~/Musik)
"""

import os
import subprocess
import time
import io
import ipc

_player_proc = None
SUPPORTED = (".mp3", ".m4a", ".flac", ".ogg", ".wav")

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def scan_files(path):
    """Alle unterstuetzten Audiodateien im Pfad finden."""
    files = []
    try:
        for root, dirs, fnames in os.walk(path):
            for fn in sorted(fnames):
                if fn.lower().endswith(SUPPORTED):
                    files.append(os.path.join(root, fn))
    except Exception:
        pass
    return files

def get_tags(filepath):
    """ID3/Tags auslesen. Gibt dict mit title, artist, album, art zurueck."""
    tags = {"title": os.path.basename(filepath),
            "artist": "", "album": "", "art": None}
    try:
        from mutagen import File as MFile
        from mutagen.id3 import ID3
        f = MFile(filepath)
        if f is None:
            return tags
        if hasattr(f, "tags") and f.tags:
            # MP3/ID3
            if hasattr(f.tags, "getall"):
                tit = f.tags.getall("TIT2")
                art = f.tags.getall("TPE1")
                alb = f.tags.getall("TALB")
                if tit: tags["title"]  = str(tit[0])[:40]
                if art: tags["artist"] = str(art[0])[:30]
                if alb: tags["album"]  = str(alb[0])[:30]
                # Album-Art
                apic = f.tags.getall("APIC")
                if apic:
                    tags["art"] = apic[0].data
            else:
                # Andere Formate (FLAC, OGG...)
                t = f.tags.get("title", [""])[0]
                a = f.tags.get("artist", [""])[0]
                b = f.tags.get("album", [""])[0]
                if t: tags["title"]  = str(t)[:40]
                if a: tags["artist"] = str(a)[:30]
                if b: tags["album"]  = str(b)[:30]
    except Exception:
        pass
    return tags

def _load_art(art_data, max_size=200):
    """Album-Art als pygame Surface laden."""
    try:
        img = pygame.image.load(io.BytesIO(art_data))
        w, h = img.get_size()
        scale = min(max_size / w, max_size / h)
        nw, nh = int(w * scale), int(h * scale)
        return pygame.transform.scale(img, (nw, nh))
    except Exception:
        return None

def play_file(filepath, S):
    """Datei abspielen via mpv."""
    global _player_proc
    stop_playback(S)
    try:
        _player_proc = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet",
             "--title=pidrive_library", filepath],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        S["library_playing"] = True
        S["library_track"] = os.path.basename(filepath)
    except FileNotFoundError:
        S["library_playing"] = False
        S["library_track"] = "mpv fehlt!"

def stop_playback(S):
    global _player_proc
    _bg("pkill -f pidrive_library 2>/dev/null")
    if _player_proc:
        try: _player_proc.terminate()
        except Exception: pass
        _player_proc = None
    S["library_playing"] = False

def show_now_playing(tags, S):
    """Now-Playing via IPC — kein pygame."""
    ipc.write_progress(
        tags.get("title", "Unbekannt")[:28],
        f"{tags.get('artist','')[:20]} | {tags.get('album','')[:18]}",
        color="blue"
    )

# build_items entfernt

def browse_and_play(S, settings):
    """Bibliothek durchsuchen via headless_pick und abspielen."""
    import os, time, ipc
    music_path = settings.get("music_path", os.path.expanduser("~/Musik"))
    if not os.path.isdir(music_path):
        ipc.write_progress("Bibliothek", f"Pfad nicht gefunden", color="red")
        time.sleep(2); ipc.clear_progress(); return

    files = scan_files(music_path)
    if not files:
        ipc.write_progress("Bibliothek", "Keine MP3-Dateien", color="orange")
        time.sleep(2); ipc.clear_progress(); return

    names = [os.path.basename(f) for f in files]
    chosen = ipc.headless_pick("Bibliothek", names)
    if not chosen:
        return

    idx = names.index(chosen)
    ipc.write_progress("Laden...", chosen[:32])
    tags = get_tags(files[idx])
    play_file(files[idx], S)
    if S.get("library_playing"):
        show_now_playing(tags, S)
