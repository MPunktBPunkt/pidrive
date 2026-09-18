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
MENU_TREE_FILE = "/tmp/pidrive_menu_tree.json"
PROGRESS_FILE = "/tmp/pidrive_progress.json"
LIST_FILE     = "/tmp/pidrive_list.json"
READY_FILE    = "/tmp/pidrive_ready"
USB_STATUS_FILE = "/tmp/pidrive_usb_status.json"
# DEBUG_FILE: entfernt v0.11.96 (Display deaktiviert)


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


def _dls_for_status(S: dict) -> str:
    """DLS nur fuer DAB — kein Track-Fallback fuer Scanner/FM/Web."""
    rt = str(S.get("radio_type", "")).upper()
    if rt == "SCANNER":
        return ""
    dls = S.get("dls_text") or ""
    if dls:
        return dls
    if rt == "DAB":
        return S.get("dls") or ""
    return ""


def _library_file_for_status(S):
    """Absoluter Pfad der aktuellen Bibliotheks-Datei (für PUMP-Cover/APIC)."""
    path = S.get("library_file") or ""
    if path:
        return path
    try:
        from modules import local_player
        return local_player.current_file() or ""
    except Exception:
        return ""


def write_status(S, settings):
    # keep library_file in S fresh for consumers (PUMP bridge, WebUI)
    try:
        from modules import local_player
        if local_player.is_playing():
            S["library_file"] = local_player.current_file() or S.get("library_file", "")
        elif not S.get("library_playing"):
            S.pop("library_file", None)
    except Exception:
        pass
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
        "dls_text":  _dls_for_status(S),
        "dls_raw":   S.get("dls_raw", ""),
        "library":   S.get("library_playing", False),
        "lib_track": S.get("library_track", S.get("lib_track", "")),
        "library_file": _library_file_for_status(S),
        "audio_out": settings.get("audio_output", "auto"),
        "audio_effective": _get_audio_effective() or settings.get("audio_output","auto"),
        "volume":  settings.get("volume", None),
        "audio_reason":    _get_audio_reason(),
        "ip":        S.get("ip", ""),
        # Phase 2: zentraler control_context (v0.8.17)
        # Mögliche Werte: idle | menu | radio_fm | radio_dab | radio_web | scanner | spotify | library
        "control_context":      S.get("control_context", "idle"),
        "dab_playback_state":   S.get("dab_playback_state", "idle"),
        "dab_sync_ok":          S.get("dab_sync_ok", False),
        "dab_sync_seen":        S.get("dab_sync_seen", False),
        "dab_partial_sync":     S.get("dab_partial_sync", False),
        "dab_audio_ready":      S.get("dab_audio_ready", False),
        "dab_pcm_seen":         S.get("dab_pcm_seen", False),
        "dab_superframe_seen":  S.get("dab_superframe_seen", False),
        "dab_attempting":       S.get("dab_attempting", False),
        "dab_last_error":       S.get("dab_last_error", ""),
        "metadata_unavailable": S.get("metadata_unavailable", False),
        "degraded_imports":     _degraded_imports(),
        "processes":            S.get("processes", []),
        "scanner":              _scanner_status(S),
        "usb":                  _usb_status(),
        "ts":        int(time.time()),
    })


def _usb_status():
    """ESP / PUMP Presence aus usb_pump_client (/tmp/pidrive_usb_status.json)."""
    raw = read_json(USB_STATUS_FILE, {})
    if not isinstance(raw, dict):
        raw = {}
    online = bool(raw.get("online"))
    try:
        age = int(time.time()) - int(raw.get("ts") or 0)
    except (TypeError, ValueError):
        age = 9999
    # Stale ohne Poll → offline. Etwas Spielraum (Poll 2s, kurze Hänger).
    if online and age > 30:
        online = False
    # Wenn Poll hängt, aber letzte Snapshot klar „ESP da“ war und Serial noch da:
    # nicht als tot anzeigen nur wegen age — UI zeigt age_s separat.
    # (Online bleibt False bei age>30; FW/OTG-Felder bleiben sichtbar.)
    return {
        "online": online,
        "http_ok": bool(raw.get("http_ok")),
        "serial_present": bool(raw.get("serial_present")),
        "serial_ports": raw.get("serial_ports") or [],
        "port": raw.get("port") or "",
        "esp_host": raw.get("esp_host") or "",
        "fw": raw.get("fw") or "",
        "pump_up": bool(raw.get("pump_up")),
        "otg_up": bool(raw.get("otg_up")),
        "otg_suspended": bool(raw.get("otg_suspended")),
        "uart_up": bool(raw.get("uart_up")),
        "msc_ready": bool(raw.get("msc_ready")),
        "playing_name": raw.get("playing_name") or "",
        "playing_uid": raw.get("playing_uid") or "",
        "id3_len": int(raw.get("id3_len") or 0),
        "stream_active": bool(raw.get("stream_active")),
        "stream_bytes": int(raw.get("stream_bytes") or 0),
        "stream_cap": int(raw.get("stream_cap") or 0),
        "buffer_ms": int(raw.get("buffer_ms") or 0),
        "source": raw.get("source") or "none",
        "age_s": age if raw.get("ts") else None,
    }


def _scanner_status(S):
    sc = S.get("scanner")
    if isinstance(sc, dict) and sc.get("active"):
        return sc
    active = str(S.get("radio_type", "")).upper() == "SCANNER"
    if isinstance(sc, dict) and not active:
        # inaktives Dict behalten, aber active aus radio_type ableiten
        out = dict(sc)
        out["active"] = False
        return out
    return {
        "active": active,
        "band": S.get("scanner_band", ""),
        "freq": (sc or {}).get("freq") if isinstance(sc, dict) else None,
        "name": S.get("radio_station", ""),
        "squelch": S.get("scanner_squelch"),
    }


def _degraded_imports():
    try:
        from modules import degraded_imports as _deg
        return _deg.list_degraded()
    except Exception:
        return []


def write_menu(menu_state):
    """Menüzustand schreiben. Erwartet MenuState.export() dict."""
    write_json(MENU_FILE, menu_state)


def write_menu_tree(tree_export: dict):
    """Vollständigen Menübaum schreiben (nur bei uid_counter-Änderung)."""
    write_json(MENU_TREE_FILE, tree_export)


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


def append_trigger(cmd: str):
    """Trigger an Queue anhängen — threadsicher, verlustfrei.
    Ersetzt direktes open(CMD_FILE,'w') in AVRCP/WebUI/CLI.
    """
    try:
        with open(CMD_FILE, "a", encoding="utf-8") as f:
            f.write(cmd.strip() + "\n")
    except Exception:
        pass


def drain_triggers() -> list:
    """Alle ausstehenden Trigger atomar lesen und Queue leeren.
    Gibt Liste von Trigger-Strings zurück (FIFO-Reihenfolge).
    """
    tmp = CMD_FILE + ".drain"
    try:
        os.replace(CMD_FILE, tmp)
    except FileNotFoundError:
        return []
    except Exception:
        return []
    try:
        lines = open(tmp, encoding="utf-8").read().splitlines()
        return [l.strip() for l in lines if l.strip()]
    except Exception:
        return []
    finally:
        try: os.unlink(tmp)
        except Exception: pass


def headless_pick(title, items, timeout=30):
    """Auswahlmenü via /tmp/pidrive_list.json + Trigger-Steuerung."""
    if not items: return None
    sel = 0
    write_json(LIST_FILE, {"active": True, "title": title,
                            "items": items, "selected": sel})
    deadline = time.time() + timeout
    while time.time() < deadline:
        cmds = drain_triggers()
        if not cmds:
            time.sleep(0.1); continue
        cmd = cmds[0]  # für interaktive Menus: erstes Event pro Poll
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
        cmds = drain_triggers()
        if not cmds:
            time.sleep(0.1); continue
        cmd = cmds[0]
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
