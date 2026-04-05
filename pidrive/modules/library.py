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
import pygame
from ui import (Item, show_message, pick_list,
                draw_rect, get_font,
                W, H, STATUS_H, C_BG, C_HEADER, C_ACCENT,
                C_WHITE, C_GRAY, C_PURPLE, C_DARK, C_GREEN)

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

def show_now_playing(screen, tags, art_surf):
    """Now-Playing Screen mit Album-Art."""
    while True:
        screen.fill(C_BG)
        draw_rect(screen, C_HEADER, (0, 0, W, STATUS_H))
        pygame.draw.line(screen, C_PURPLE, (0, STATUS_H - 1), (W, STATUS_H - 1), 2)
        t = get_font(14, bold=True).render("Wiedergabe", True, C_WHITE)
        screen.blit(t, (W//2 - t.get_width()//2, STATUS_H//2 - t.get_height()//2))

        y = STATUS_H + 10

        # Album-Art
        if art_surf:
            aw, ah = art_surf.get_size()
            ax = W//2 - aw//2
            screen.blit(art_surf, (ax, y))
            y += ah + 10
        else:
            # Platzhalter
            draw_rect(screen, (30, 30, 45), (W//2 - 80, y, 160, 160))
            ph = get_font(40).render("♪", True, (60, 60, 80))
            screen.blit(ph, (W//2 - ph.get_width()//2, y + 55))
            y += 175

        # Track-Info
        title_f  = get_font(16, bold=True)
        artist_f = get_font(13)
        album_f  = get_font(12)

        title_s = title_f.render(tags["title"][:24], True, C_WHITE)
        screen.blit(title_s, (W//2 - title_s.get_width()//2, y))
        y += title_s.get_height() + 4

        if tags["artist"]:
            art_s = artist_f.render(tags["artist"][:28], True, C_GREEN)
            screen.blit(art_s, (W//2 - art_s.get_width()//2, y))
            y += art_s.get_height() + 2

        if tags["album"]:
            alb_s = album_f.render(tags["album"][:30], True, C_GRAY)
            screen.blit(alb_s, (W//2 - alb_s.get_width()//2, y))
            y += alb_s.get_height() + 10

        # Hinweis
        hint = get_font(12).render("[ESC/Links] Zurueck", True, (60, 60, 80))
        screen.blit(hint, (W//2 - hint.get_width()//2, H - 30))

        pygame.display.flip()

        # Event-Loop
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_LEFT,
                              pygame.K_RETURN, pygame.K_KP_ENTER):
                    return

        pygame.time.wait(100)

def build_items(screen, S, settings):
    """Gibt Bibliothek-Untermenue-Items zurueck."""
    music_path = settings.get("music_path",
                              os.path.expanduser("~/Musik"))

    def browse_library():
        if not os.path.isdir(music_path):
            show_message(screen, "Bibliothek",
                         f"Pfad nicht gefunden:", color=C_PURPLE)
            time.sleep(2)
            return

        files = scan_files(music_path)
        if not files:
            show_message(screen, "Bibliothek", "Keine Dateien gefunden")
            time.sleep(2)
            return

        # Dateinamen ohne Pfad anzeigen
        names = [os.path.basename(f) for f in files]
        chosen_name = pick_list(screen, "Bibliothek", names, color=C_PURPLE)
        if not chosen_name:
            return

        idx = names.index(chosen_name)
        filepath = files[idx]

        # Tags lesen
        show_message(screen, "Laden...", chosen_name[:30], color=C_PURPLE)
        tags = get_tags(filepath)
        art_surf = _load_art(tags["art"], max_size=160) if tags["art"] else None

        # Abspielen
        play_file(filepath, S)

        # Now-Playing anzeigen
        if S.get("library_playing"):
            show_now_playing(screen, tags, art_surf)

    def stop_action():
        stop_playback(S)
        show_message(screen, "Bibliothek", "Gestoppt")
        time.sleep(1)

    def set_path_action():
        show_message(screen, "Musik-Pfad", music_path[:36])
        time.sleep(3)

    items = [
        Item("Durchsuchen",
             sub=lambda: S.get("library_track", "Leer") if S.get("library_playing")
                         else f"{music_path[-20:]}",
             action=browse_library),
        Item("Stop",
             action=stop_action),
        Item("Pfad",
             sub=lambda: music_path[-30:],
             action=set_path_action),
    ]
    return items
