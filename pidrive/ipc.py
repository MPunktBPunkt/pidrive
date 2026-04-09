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


PROGRESS_FILE = "/tmp/pidrive_progress.json"

def write_progress(title, message="", pct=None, lines=None, color="blue"):
    """Fortschritt/Status fuer Display schreiben.
    
    title:   Haupttitel (z.B. "DAB+ Scan")
    message: Statuszeile (z.B. "Kanal 7A...")
    pct:     Fortschritt 0-100 oder None
    lines:   Liste von Statuszeilen fuer laengere Ausgaben
    color:   "blue" | "green" | "red" | "orange"
    """
    write_json(PROGRESS_FILE, {
        "active":   True,
        "title":    title,
        "message":  message,
        "pct":      pct,
        "lines":    lines or [],
        "color":    color,
        "ts":       __import__("time").time(),
    })


def clear_progress():
    """Progress-Anzeige beenden."""
    write_json(PROGRESS_FILE, {"active": False})

LIST_FILE = "/tmp/pidrive_list.json"

def headless_pick(title, items, timeout=30):
    """Schreibt Auswahlliste in IPC, wartet auf Trigger-Auswahl.
    Gibt gewaehlten String zurueck oder None bei Abbruch."""
    import time as _time
    sel = 0
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        write_json(LIST_FILE, {
            "active": True, "title": title,
            "items": items, "selected": sel,
            "ts": _time.time(),
        })
        if not __import__("os").path.exists(CMD_FILE):
            _time.sleep(0.1)
            continue
        try:
            cmd = open(CMD_FILE).read().strip()
            __import__("os").remove(CMD_FILE)
        except Exception:
            _time.sleep(0.1)
            continue
        if   cmd == "up"   and sel > 0:              sel -= 1
        elif cmd == "down" and sel < len(items) - 1: sel += 1
        elif cmd in ("enter", "right"):
            write_json(LIST_FILE, {"active": False})
            return items[sel]
        elif cmd in ("back", "left"):
            write_json(LIST_FILE, {"active": False})
            return None
    write_json(LIST_FILE, {"active": False})
    return None


def headless_confirm(title, message, timeout=15):
    """Bestaetigungsdialog via IPC. Gibt True/False zurueck."""
    import time as _time
    write_progress(title, message + " (Enter=Ja  Back=Nein)", color="orange")
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        if not __import__("os").path.exists(CMD_FILE):
            _time.sleep(0.1)
            continue
        try:
            cmd = open(CMD_FILE).read().strip()
            __import__("os").remove(CMD_FILE)
        except Exception:
            _time.sleep(0.1)
            continue
        if cmd in ("enter", "right"):
            clear_progress(); return True
        elif cmd in ("back", "left", "esc"):
            clear_progress(); return False
    clear_progress()
    return False
