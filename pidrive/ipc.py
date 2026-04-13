"""
ipc.py - PiDrive IPC v0.7.10
Atomares JSON zwischen Core, Display und Web UI.

IPC-VERTRAG (stabil ab v0.7.10):
============================================================
STATUS: /tmp/pidrive_status.json
  wifi      bool     WLAN verbunden
  wifi_ssid str      Netzwerkname
  bt        bool     Bluetooth aktiv
  bt_device str      verbundenes Gerät
  spotify   bool     Spotify aktiv
  track     str      Spotify Titel
  artist    str      Spotify Artist
  album     str      Spotify Album
  radio     bool     Radio aktiv
  radio_name str     Sendername
  radio_type str     WEB/DAB/FM/SCANNER
  library   bool     Bibliothek aktiv
  lib_track str      aktueller Track
  audio_out str      Audioausgang (klinke/hdmi/bt/auto)
  ip        str      IP-Adresse
  ts        int      Unix-Timestamp

MENÜ: /tmp/pidrive_menu.json
  rev       int      Änderungszähler (steigt bei jeder Navigation)
  path      list     Pfad-Labels ["PiDrive","Quellen","FM Radio","Sender"]
  title     str      letzten 2 Pfad-Elemente als String
  cursor    int      selektierter Index in nodes[]
  can_back  bool     true wenn nicht im Root
  nodes     list     aktuelle Knoten (id/label/type/active/playable/meta)
  -- Compat-Felder (für alte Display/Web-Versionen) --
  cat       int      Root-Kategorie Index
  cat_label str      Root-Kategorie Label
  item      int      = cursor
  item_label str     = nodes[cursor].label
  categories list    Root-Kategorie Labels
  items     list     nodes[].label Liste

PROGRESS: /tmp/pidrive_progress.json
  active    bool
  title     str
  message   str
  pct       int|null  0-100 für Fortschrittsbalken
  color     str       blue/green/orange/red

LIST: /tmp/pidrive_list.json (headless_pick)
  active    bool
  title     str
  items     list
  selected  int

COMMAND: /tmp/pidrive_cmd
  up/down/left/right/enter/back
  cat:0..3
  dab_scan, fm_scan
  fm_next, fm_prev, dab_next, dab_prev
  reload_stations:dab|fm|webradio
  scan_up:band, scan_down:band, scan_next:band, scan_prev:band
  wifi_on/off/toggle, bt_on/off/toggle
  spotify_on/off/toggle
  audio_klinke/hdmi/bt/all
  vol_up, vol_down
  reboot, shutdown, update
============================================================
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
        pass  # write error silently ignored (tmpfs race)

def read_json(path, default=None):
    if default is None: default = {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _get_audio_effective():
    try:
        from modules.audio import get_last_decision
        return get_last_decision().get("effective", "")
    except Exception:
        return ""


def _get_audio_reason():
    try:
        from modules.audio import get_last_decision
        return get_last_decision().get("reason", "")
    except Exception:
        return ""


def write_status(S, settings):
    write_json(STATUS_FILE, {
        "wifi":      S.get("wifi",    False),
        "wifi_ssid": S.get("wifi_ssid", ""),
        "bt":        S.get("bt",      False),
        "bt_device": S.get("bt_device", ""),
        "spotify":   S.get("spotify", False),
        "track":     S.get("track", S.get("spotify_track",  "")),
        "artist":    S.get("artist",S.get("spotify_artist", "")),
        "album":     S.get("album", S.get("spotify_album",  "")),
        "radio":     S.get("radio_playing", S.get("radio", False)),
        "radio_name":S.get("radio_station", ""),
        "radio_type":S.get("radio_type", ""),
        "library":   S.get("library_playing", False),
        "lib_track": S.get("library_track", S.get("lib_track", "")),
        "audio_out": settings.get("audio_output", "auto"),
        "audio_effective": _get_audio_effective(),
        "audio_reason":    _get_audio_reason(),
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
