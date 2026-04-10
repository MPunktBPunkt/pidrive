"""
ipc.py - PiDrive IPC v0.7.0
Atomares JSON zwischen Core, Display und Web UI.

Neues Format (v0.7.0):
  menu.json: path, cursor, nodes, rev, can_back + Compat-Felder
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
    except Exception as e:
        import log; log.error(f"ipc write_json {path}: {e}")

def read_json(path, default=None):
    if default is None: default = {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_status(S, settings):
    write_json(STATUS_FILE, {
        "wifi":      S.get("wifi",    False),
        "wifi_ssid": S.get("wifi_ssid", ""),
        "bt":        S.get("bt",      False),
        "bt_device": S.get("bt_device", ""),
        "spotify":   S.get("spotify", False),
        "track":     S.get("track",   ""),
        "artist":    S.get("artist",  ""),
        "album":     S.get("album",   ""),
        "radio":     S.get("radio",   False),
        "radio_name":S.get("radio_station", ""),
        "radio_type":S.get("radio_type", ""),
        "library":   S.get("library_playing", False),
        "lib_track": S.get("library_track", ""),
        "audio_out": settings.get("audio_output", "auto"),
        "ip":        S.get("ip", ""),
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
