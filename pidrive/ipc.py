"""
ipc.py — Inter-Process-Communication (JSON-Dateien in /tmp)
Aufrufer: main_core.py, main_display.py, webui.py, diagnose.py
Schreibt: /tmp/pidrive_status.json, /tmp/pidrive_menu.json, /tmp/pidrive_cmd
Liest: /tmp/pidrive_cmd (Trigger-Datei für Befehle)
"""


import os, json, time

CMD_FILE      = "/tmp/pidrive_cmd"
STATUS_FILE   = "/tmp/pidrive_status.json"
MENU_FILE     = "/tmp/pidrive_menu.json"
PROGRESS_FILE = "/tmp/pidrive_progress.json"
LIST_FILE     = "/tmp/pidrive_list.json"
READY_FILE    = "/tmp/pidrive_ready"
DEBUG_FILE    = "/tmp/pidrive_display_debug.json"


def write_json(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass  # write error silently ignored (tmpfs race)

def read_json(path, default=None):
    if default is None: default = {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _get_audio_effective():
    """Audio-Effective aus shared State-File (v0.9.4)."""
    try:
        from modules.audio import read_last_decision_file
        return read_last_decision_file().get("effective", "")
    except Exception:
        return ""


def _get_audio_reason():
    """Audio-Reason aus shared State-File (v0.9.4)."""
    try:
        from modules.audio import read_last_decision_file
        return read_last_decision_file().get("reason", "")
    except Exception:
        return ""


def write_status(S, settings):
    write_json(STATUS_FILE, {
        "wifi":      S.get("wifi",    False),
        "wifi_ssid": S.get("wifi_ssid", ""),
        "bt":        S.get("bt",      False),
        "bt_on":     S.get("bt_on",   False),   # Adapter-UP (dreistufiges BT-Icon)
        "bt_status": S.get("bt_status", "getrennt"),
        "bt_device": S.get("bt_device", ""),
        "spotify":   S.get("spotify", False),
        "track":     S.get("track", S.get("spotify_track",  "")),
        "artist":    S.get("artist",S.get("spotify_artist", "")),
        "album":     S.get("album", S.get("spotify_album",  "")),
        "radio":     S.get("radio_playing", S.get("radio", False)),
        "radio_name":S.get("radio_station", ""),
        "radio_type":S.get("radio_type", ""),
        "dls_text":  S.get("dls_text", S.get("dls", S.get("track", ""))),
        "dls_raw":   S.get("dls_raw", ""),
        "library":   S.get("library_playing", False),
        "lib_track": S.get("library_track", S.get("lib_track", "")),
        "audio_out": settings.get("audio_output", "auto"),
        "audio_effective": _get_audio_effective() or settings.get("audio_output","auto"),
        "audio_reason":    _get_audio_reason(),
        "ip":        S.get("ip", ""),
        # Phase 2: zentraler control_context (v0.8.17)
        # Mögliche Werte: idle | menu | radio_fm | radio_dab | radio_web | scanner | spotify | library
        "control_context": S.get("control_context", "idle"),
        "ts":        int(time.time()),
    })


def write_menu(menu_state):
    """Menüzustand schreiben. Erwartet MenuState.export() dict."""
    write_json(MENU_FILE, menu_state)


def write_progress(title, message="", pct=None, lines=None, color="blue"):
    write_json(PROGRESS_FILE, {
        "active":  True,
        "title":   title[:40],
        "message": message[:60],
        "pct":     pct,
        "lines":   lines or [],
        "color":   color,
        "ts":      int(time.time()),
    })

def clear_progress():
    write_json(PROGRESS_FILE, {"active": False})


def headless_pick(title, items, timeout=30):
    """Auswahlmenü via /tmp/pidrive_list.json + Trigger-Steuerung."""
    if not items: return None
    sel = 0
    write_json(LIST_FILE, {"active": True, "title": title,
                            "items": items, "selected": sel})
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not os.path.exists(CMD_FILE):
            time.sleep(0.1); continue
        try:
            cmd = open(CMD_FILE).read().strip()
            os.remove(CMD_FILE)
        except Exception:
            continue
        if   cmd == "up":    sel = max(0, sel - 1)
        elif cmd == "down":  sel = min(len(items)-1, sel + 1)
        elif cmd in ("enter","right"):
            write_json(LIST_FILE, {"active": False})
            return items[sel]
        elif cmd in ("back","left"):
            write_json(LIST_FILE, {"active": False})
            return None
        write_json(LIST_FILE, {"active": True, "title": title,
                                "items": items, "selected": sel})
    write_json(LIST_FILE, {"active": False})
    return None


def headless_confirm(title, message, timeout=15):
    write_json(LIST_FILE, {"active": True, "title": title,
                            "items": ["Ja","Nein"], "selected": 0})
    deadline = time.time() + timeout
    sel = 0
    while time.time() < deadline:
        if not os.path.exists(CMD_FILE):
            time.sleep(0.1); continue
        try:
            cmd = open(CMD_FILE).read().strip()
            os.remove(CMD_FILE)
        except Exception:
            continue
        if cmd in ("up","down"): sel = 1 - sel
        elif cmd in ("enter","right"):
            write_json(LIST_FILE, {"active": False})
            return sel == 0
        elif cmd in ("back","left"):
            write_json(LIST_FILE, {"active": False})
            return False
        write_json(LIST_FILE, {"active": True, "title": title,
                                "items": ["Ja","Nein"], "selected": sel})
    write_json(LIST_FILE, {"active": False})
    return False
