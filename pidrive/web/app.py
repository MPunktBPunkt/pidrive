"""web/app.py — PiDrive WebUI Flask-App
Hauptdatei für das Webfrontend. Läuft als pidrive_web.service (ExecStart: web/app.py).
"""
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import time
import socket
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify, make_response

# Paket-Root (pidrive/) — sonst schlägt "from web.shared" fehl wenn app.py direkt gestartet wird
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    static_url_path="/static",
)


# ── v0.10.55: Shared helpers aus webui_shared.py ──────────────────────────────
from web.shared import *  # noqa: F401,F403
from web.shared import (
    CMD_FILE, STATUS_FILE, MENU_FILE, PROGRESS_FILE, RTLSDR_FILE,
    AVRCP_FILE, LIST_FILE, LOG_FILE, READY_FILE, KNOWN_BT_FILE,
    BT_AGENT_FILE, DAB_DEBUG_FILE, ALLOWED_COMMANDS, PA_ENV,
    read_json, read_json_meta, write_cmd, file_age, get_ip, safe_run,
    build_view_model, get_dab_status_debug, get_audio_debug,
)
from web.shared.constants import ALLOWED_COMMAND_PREFIXES

# ── v0.10.55: Blueprints registrieren ─────────────────────────────────────────
# Fehler werden geloggt UND in app.config gehalten (Banner auf jeder Seite, W1/V6)
app.config["BLUEPRINT_IMPORT_ERROR"] = None
try:
    from web.api.routes_dab      import dab_bp;      app.register_blueprint(dab_bp)
    from web.api.routes_bt       import bt_bp;       app.register_blueprint(bt_bp)
    from web.api.routes_audio    import audio_bp;    app.register_blueprint(audio_bp)
    from web.api.routes_webradio import webradio_bp; app.register_blueprint(webradio_bp)
    from web.api.routes_music   import music_bp;    app.register_blueprint(music_bp)
except Exception as _bp_err:
    import log as _log
    _log.error(f"WebUI Blueprint-Import FEHLER: {_bp_err} — Betroffene API-Routen nicht verfügbar!")
    app.config["BLUEPRINT_IMPORT_ERROR"] = str(_bp_err)


@app.context_processor
def _inject_blueprint_warning():
    return {
        "blueprint_import_error": app.config.get("BLUEPRINT_IMPORT_ERROR"),
    }

# ── /api/* gibt immer JSON zurück, nie HTML-Fehlerseiten ─────────────────
@app.errorhandler(404)
def _api_err404(e):
    from flask import request as _req
    if _req.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not Found", "path": _req.path}), 404
    return str(e), 404

@app.errorhandler(500)
def _api_err500(e):
    from flask import request as _req
    if _req.path.startswith("/api/"):
        return jsonify({"ok": False, "error": str(e)}), 500
    return str(e), 500



def _sanitize_floats(obj, _depth=0):
    """Ersetzt NaN/Infinity durch None — JSON-Spec kennt diese nicht."""
    if _depth > 20:
        return None
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v, _depth+1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_floats(v, _depth+1) for v in obj]
    return obj




# ── Unterseiten (v0.10.55) ──────────────────────────────────────────────
@app.route("/bluetooth")
def page_bluetooth():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model bluetooth.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("bluetooth.html", vm=vm)

@app.route("/menu")
def page_menu():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model menu.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("menu.html", vm=vm)


@app.route("/audio")
def page_audio():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model audio.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("audio.html", vm=vm)

@app.route("/rf-tools")
def page_rf_tools():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model rf-tools.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("rf-tools.html", vm=vm)

@app.route("/diagnostics")
def page_diagnostics():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model diagnostics.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("diagnostics.html", vm=vm)

@app.route("/avrcp")
def page_avrcp():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model avrcp.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("avrcp.html", vm=vm)

@app.route("/webradio-admin")
def page_webradio_admin():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model webradio-admin.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("webradio-admin.html", vm=vm)

@app.route("/music-admin")
def page_music_admin():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
    except Exception as _e:
        import log as _log
        _log.error(f"build_view_model music-admin.html: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {}, "settings": {}}
    return render_template("music-admin.html", vm=vm)


@app.route("/")
def index():
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)  # NaN/Infinity → null (JS-kompatibel)
    except Exception as _e:
        import log as _log_idx
        _log_idx.error(f"build_view_model Fehler: {_e}")
        vm = {"version": "?", "ip": "?", "status": {}, "menu": {},
              "progress": {}, "rtlsdr": {}, "avrcp": {}, "audio_debug": {},
              "source_state": {}, "dab_scan_debug": {}, "dab_status_debug": {},
              "spectrum_debug": {}, "known_bt_devices": {}, "bt_agent": {},
              "processes": [], "list_data": {}, "list_active": False,
              "list_title": "", "list_items": [], "list_selected": 0,
              "nodes": [], "categories": [], "items": [],
              "path": [], "cursor": 0, "rev": 0, "can_back": False,
              "debug": {"rev": 0, "error": str(_e)}}
    # JSON-Vorab-Test: wirft Exception BEVOR tojson im Template crasht
    import json as _json
    try:
        _json.dumps(vm)
    except Exception as _json_err:
        import log as _log_json
        _log_json.error(f"VM JSON-Serialisierung fehlgeschlagen: {_json_err}")
        # Erneut sanitizen mit aggressiverer Methode
        vm = _sanitize_floats(vm)
        try: _json.dumps(vm)
        except: vm = {"version": "error", "debug": {"rev": 0}, "nodes": [],
                      "path": [], "cursor": 0, "can_back": False, "status": {}}

    resp = make_response(render_template("index.html", vm=vm))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/cover/<name>")
def cover_art(name):
    """Cover Art Endpunkt für MPRIS2 artUrl (BMW holt Bild wenn im selben Netz)."""
    import os as _os
    static_dir = _os.path.join(_os.path.dirname(__file__), "static")
    fname = name.replace(".svg", "").replace(".png", "")
    candidates = [
        _os.path.join(static_dir, f"{fname}.svg"),
        _os.path.join(static_dir, "pidrive_logo.svg"),
    ]
    for p in candidates:
        if _os.path.exists(p):
            with open(p) as _svg_f:
                svg = _svg_f.read()
            return app.response_class(svg, mimetype="image/svg+xml")
    return "", 404


@app.route("/api/ping")
def api_ping():
    """Einfacher Verbindungstest — gibt ok:true zurück."""
    return jsonify({"ok": True, "version": get_version()})


@app.route("/api/core")
def api_core():
    """
    Leichter Endpoint fuer Fast-Poll (~1.2s).
    status.json + menu.json + source_state.json
    status_age/menu_age kommen aus Dateialter (W2/S1/S2), nicht aus Request-Zeit.
    """
    status, status_meta = read_json_meta(STATUS_FILE, {}, stale_after_s=3.0)
    menu, menu_meta = read_json_meta(MENU_FILE, {})
    prog   = read_json(PROGRESS_FILE, {})
    list_d = read_json(LIST_FILE, {})
    nodes  = menu.get("nodes", [])
    cursor = menu.get("cursor", 0)
    sel    = nodes[cursor] if nodes and cursor < len(nodes) else {}
    status_age = status_meta.get("age")
    menu_age = menu_meta.get("age")
    core_ready = os.path.exists(READY_FILE)
    try:
        from modules.source_state import load_snapshot_file
        source_state = load_snapshot_file()
    except Exception:
        source_state = {}
    # Fallback: sticky-/tmp-Schreibfehler → Datei stale, Core-Status hat radio_type
    try:
        cur = str((source_state or {}).get("source_current") or "idle").lower()
        rt = str((status or {}).get("radio_type") or "").upper()
        if cur in ("", "idle") and rt:
            _map = {
                "SCANNER": "scanner",
                "DAB": "dab", "DAB+": "dab",
                "FM": "fm",
                "WEB": "webradio", "WEBRADIO": "webradio",
                "SPOTIFY": "spotify",
            }
            mapped = _map.get(rt)
            if mapped:
                source_state = dict(source_state or {})
                source_state["source_current"] = mapped
                source_state["_inferred_from_radio_type"] = True
    except Exception:
        pass
    try:
        from modules.playback_meta import metadata_for_source
        now = metadata_for_source(source_state.get("source_current", "idle"), status)
    except Exception:
        now = {}

    return jsonify({
        "status":       status,
        "source_state": source_state,
        "now":          now,
        "path":         menu.get("path", []),
        "nodes":        nodes,
        "cursor":       cursor,
        "rev":          menu.get("rev", 0),
        "can_back":     menu.get("can_back", False),
        "categories":   menu.get("categories", []),
        "items":        menu.get("items", []),
        "progress":     prog,
        "list_data":    list_d,
        "list_active":      list_d.get("active", False),
        "list_title":       list_d.get("title", ""),
        "list_items":         list_d.get("items", []),
        "list_selected":      list_d.get("selected", 0),
        # Lebendigkeit aus Dateialter — nicht Request-Zeit (S2)
        "core_ready":   core_ready,
        "status_age":   status_age,
        "menu_age":     menu_age,
        "status_error": status_meta.get("reason"),  # missing|corrupt|stale|None
        "menu_error":   menu_meta.get("reason"),
        "ts":           time.time(),
        "debug": {
            "rev":            menu.get("rev", 0),
            "path":           menu.get("path", []),
            "title":          menu.get("title", ""),
            "cursor":         cursor,
            "can_back":       menu.get("can_back", False),
            "selected_label": sel.get("label", "") if isinstance(sel, dict) else str(sel),
            "selected_type":  sel.get("type", "")  if isinstance(sel, dict) else "",
            "node_count":     len(nodes),
            "core_ready":     core_ready,
            "status_age":     status_age,
            "menu_age":       menu_age,
            "status_error":   status_meta.get("reason"),
        },
    })


@app.route("/api/playlist")
def api_playlist():
    """Wiedergabe-History aus play_history.json."""
    import datetime as _dt
    date = request.args.get("date", "today")
    hist_path = os.path.join(str(_PKG_ROOT), "config", "play_history.json")
    try:
        with open(hist_path, encoding="utf-8") as f:
            entries = json.load(f)
    except Exception:
        entries = []
    today = _dt.date.today().isoformat()
    if date == "today":
        filtered = [e for e in entries if str(e.get("date", "")).startswith(today)]
        label = f"Heute ({today})"
    elif date == "all":
        filtered = entries
        label = "Alle Eintraege"
    elif date == "last":
        filtered = entries[-30:]
        label = "Letzte 30"
    else:
        filtered = [e for e in entries if str(e.get("date", "")).startswith(date)]
        label = date
    filtered = list(reversed(filtered[-50:]))
    return jsonify({"ok": True, "label": label, "count": len(filtered), "entries": filtered})


@app.route("/api/state")
def api_state():
    """ViewModel für Debug/Diagnose. Senderlisten: /api/lists (W2/S9)."""
    try:
        vm = build_view_model()
        vm = _sanitize_floats(vm)
        return jsonify(vm)
    except Exception as e:
        import log as _log
        _log.error(f"api_state: {e}")
        return jsonify({"error": str(e), "ok": False}), 500


def _load_config_list(fname, key="stations"):
    """Billiger JSON-Listen-Lader aus config/."""
    path = os.path.join(str(_PKG_ROOT), "config", fname)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get(key, data.get("favorites", []))
        return data if isinstance(data, list) else []
    except Exception:
        return []


@app.route("/api/lists")
def api_lists():
    """Billige Sender-/Favoritenlisten ohne pactl/ViewModel (W2/S9)."""
    return jsonify({
        "ok": True,
        "dab_stations": _load_config_list("dab_stations.json", "stations"),
        "web_stations": _load_config_list("stations.json", "stations"),
        "fm_stations":  _load_config_list("fm_stations.json", "stations"),
        "favorites":    _load_config_list("favorites.json", "favorites"),
    })


@app.route("/api/favorites")
def api_favorites():
    """Favoritenliste (V4/W2 — ersetzt fehlende Route für page-index.js)."""
    return jsonify({"ok": True, "favorites": _load_config_list("favorites.json", "favorites")})


@app.route("/api/runtime")
def api_runtime():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from settings import load_settings as _ls
        settings = _ls()
    except Exception:
        settings = {}

    status = read_json(STATUS_FILE, {})
    return jsonify({
        "ok": True,
        "settings": {
            "audio_output": settings.get("audio_output", "-"),
            "volume": settings.get("volume", "-"),
            "fm_gain": settings.get("fm_gain", "-"),
            "dab_gain": settings.get("dab_gain", "-"),
            "scanner_gain": settings.get("scanner_gain", "-"),
            "ppm_correction": settings.get("ppm_correction", "-"),
            "scanner_squelch": settings.get("scanner_squelch", "-"),
            "squelch": settings.get("scanner_squelch", "-"),
            "last_source": settings.get("last_source", "-"),
            "dab_scan_wait_lock": settings.get("dab_scan_wait_lock", "-"),
            "dab_scan_http_timeout": settings.get("dab_scan_http_timeout", "-"),
            "dab_scan_port": settings.get("dab_scan_port", "-"),
            "dab_scan_channels": settings.get("dab_scan_channels", []),
            "dab_channels": ", ".join(settings.get("dab_scan_channels", [])) or "-",
        },
        "version": get_version(),
        "source_state": get_source_state_debug(),
        "dab_scan_debug": get_dab_scan_debug(),
        "dab_status": get_dab_status_debug(),
        "spectrum_debug": get_spectrum_debug(),
        "audio": get_audio_debug(),
        "known_bt_devices": read_json(KNOWN_BT_FILE, {"devices": []}),
        "bt_agent": read_json(BT_AGENT_FILE, {}),
        "processes": status.get("processes", []),
    })


@app.route("/api/cmd", methods=["POST"])
def api_cmd():
    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()

    if not cmd:
        return jsonify({"ok": False, "error": "Kein Befehl übergeben"}), 400

    prefixes = ALLOWED_COMMAND_PREFIXES
    if not (cmd in ALLOWED_COMMANDS or any(cmd.startswith(p) for p in prefixes)):
        return jsonify({"ok": False, "error": f"Befehl nicht erlaubt: {cmd}"}), 400

    try:
        write_cmd(cmd)
        import log as _log_cmd
        _log_cmd.info(f"WebUI CMD: {cmd!r} von {request.remote_addr}")
        return jsonify({"ok": True, "cmd": cmd})
    except Exception as e:
        import log as _log_cmd
        _log_cmd.error(f"WebUI CMD Fehler: {cmd!r} — {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/logs")
def api_logs():
    target = request.args.get("target", "core")
    log_dir = "/var/log/pidrive"

    if target == "core":
        # Versuche journalctl, Fallback auf Logdatei
        r = safe_run("journalctl -u pidrive_core -n 150 --no-pager 2>/dev/null")
        if not r.get("ok") or not r.get("stdout","").strip():
            r = safe_run(f"tail -n 150 {log_dir}/core.log 2>/dev/null || tail -n 150 {LOG_FILE} 2>/dev/null")
        return jsonify(r)
    elif target == "display":
        r = safe_run(f"tail -n 150 {log_dir}/display.log 2>/dev/null || echo '(display log not found)'")
        return jsonify(r)
    elif target == "avrcp":
        r = safe_run("journalctl -u pidrive_avrcp -n 150 --no-pager 2>/dev/null")
        if not r.get("ok") or not r.get("stdout","").strip():
            r = safe_run(f"tail -n 150 {log_dir}/avrcp.log 2>/dev/null")
        return jsonify(r)
    elif target == "app":
        return jsonify(safe_run(f"tail -n 150 {LOG_FILE} 2>/dev/null || echo '(log not found)'"))
    else:
        return jsonify({"ok": False, "error": "Ungültiges Log-Target"}), 400


@app.route("/api/diagnose")
def api_diagnose():
    diag_py = BASE_DIR / "diagnose.py"
    if diag_py.exists():
        return jsonify(safe_run(f"/usr/bin/python3 {diag_py}"))
    return jsonify({
        "ok": False,
        "code": 1,
        "stdout": "",
        "stderr": "diagnose.py nicht gefunden",
        "cmd": "diagnose.py"
    })


@app.route("/api/webui/smoke", methods=["GET"])
def api_webui_smoke_status():
    """Status + Log-Tail + letztes JSON-Ergebnis des WebUI-Live-Smoke."""
    try:
        from web.shared.webui_smoke_runner import get_status
        return jsonify({"ok": True, **get_status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/webui/smoke/start", methods=["POST"])
def api_webui_smoke_start():
    """
    Startet Live-Smoke im Hintergrund.
    Body/Query: mode=quick|flows|full (default flows)
    """
    try:
        from web.shared.webui_smoke_runner import start as smoke_start
        data = request.get_json(silent=True) or {}
        mode = (data.get("mode") or request.args.get("mode") or "flows").strip()
        # Immer localhost — Test läuft auf dem Pi neben der WebUI
        base = (data.get("base") or "http://127.0.0.1:8080").strip()
        result = smoke_start(mode=mode, base=base)
        code = 200 if result.get("ok") else 409
        return jsonify(result), code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/webui/smoke/stop", methods=["POST"])
def api_webui_smoke_stop():
    try:
        from web.shared.webui_smoke_runner import stop as smoke_stop
        return jsonify(smoke_stop())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/grep")
def api_grep():
    import shlex
    # BASE_DIR ist pidrive/web — Paketwurzel ist _PKG_ROOT (V5)
    target = str(_PKG_ROOT)
    if not os.path.isdir(target):
        return jsonify({
            "ok": False,
            "code": 1,
            "stdout": "",
            "stderr": f"Pfad nicht gefunden: {target}",
            "cmd": "grep",
        })
    cmd = 'grep -Ern ' + shlex.quote('ERROR|WARNING|Fehler') + ' ' + shlex.quote(target)
    return jsonify(safe_run(cmd))


@app.route("/api/rtlsdr")
def api_rtlsdr():
    """RTL-SDR Status. Bei fehlender/staler Diagnose automatisch neu erheben."""
    data = read_json(RTLSDR_FILE, {})
    age = file_age(RTLSDR_FILE)
    stale = (not data) or (age is None) or (isinstance(age, (int, float)) and age > 60)
    if stale:
        try:
            from modules.radio import rtlsdr as _rtl
            data = _rtl.diagnose(active_tests=False) or {}
            age = file_age(RTLSDR_FILE)
        except Exception as e:
            usb = (data or {}).get("usb") or {}
            return jsonify({
                "ok": False,
                "error": str(e),
                "present": bool(usb.get("present")),
                "usb_id": _rtlsdr_usb_id(usb),
                "data": data or {},
                "exists": os.path.exists(RTLSDR_FILE),
                "age": age,
            })
    usb = (data or {}).get("usb") or {}
    present = bool(usb.get("present"))
    return jsonify({
        "ok": True,
        "present": present,
        "usb_id": _rtlsdr_usb_id(usb),
        "data": data,
        "exists": os.path.exists(RTLSDR_FILE),
        "age": age,
        "hint": None if present else "Kein RTL-SDR per lsusb — Stick am Pi anstecken",
    })


def _rtlsdr_usb_id(usb: dict) -> str:
    matches = usb.get("matches") or []
    if not matches:
        return ""
    # "Bus 001 Device 004: ID 0bda:2838 Realtek ..." → "0bda:2838"
    import re as _re
    m = _re.search(r"ID\s+([0-9a-fA-F]{4}:[0-9a-fA-F]{4})", matches[0])
    return m.group(1) if m else matches[0][:60]


@app.route("/api/rtlsdr/refresh")
def api_rtlsdr_refresh():
    try:
        from modules.radio import rtlsdr as _rtl
        data = _rtl.diagnose(active_tests=False) or {}
    except Exception as _e:
        data = read_json(RTLSDR_FILE, {})
        usb = (data or {}).get("usb") or {}
        return jsonify({
            "ok": False,
            "error": str(_e),
            "present": bool(usb.get("present")),
            "usb_id": _rtlsdr_usb_id(usb),
            "data": data,
            "file_exists": os.path.exists(RTLSDR_FILE),
        })
    usb = (data or {}).get("usb") or {}
    present = bool(usb.get("present"))
    return jsonify({
        "ok": True,
        "present": present,
        "usb_id": _rtlsdr_usb_id(usb),
        "data": data,
        "file_exists": os.path.exists(RTLSDR_FILE),
        "hint": None if present else "Kein RTL-SDR per lsusb — Stick am Pi anstecken",
    })

@app.route("/api/rtlsdr/reset", methods=["POST"])
def api_rtlsdr_reset():
    try:
        write_cmd("rtlsdr_reset")
        return jsonify({"ok": True, "msg": "RTL-SDR Reset gestartet — dauert ~5s"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


PPM_CAL_LOG = "/tmp/pidrive_ppm_calibrate.log"
PPM_CAL_META = "/tmp/pidrive_ppm_calibrate.json"


def _ppm_parse_log_text(stdout: str) -> dict:
    """Parse rtl_test -p Output → current/cumulative/suggested."""
    import re as _re
    lines = (stdout or "").splitlines()
    cum_ppms = []
    cur_ppms = []
    for ln in lines:
        m = _re.search(r"cumulative PPM[: ]+([-+]?[0-9]+)", ln, _re.I)
        if m:
            try:
                cum_ppms.append(int(m.group(1)))
            except Exception:
                pass
        m = _re.search(r"current PPM[: ]+([-+]?[0-9]+)", ln, _re.I)
        if m:
            try:
                cur_ppms.append(int(m.group(1)))
            except Exception:
                pass

    ppm = None
    method = "nicht erkannt"
    if cum_ppms:
        ppm = cum_ppms[-1]
        stability = (
            "⚠ zu wenige Messungen — noch unzuverlässig"
            if len(cum_ppms) < 6
            else f"{len(cum_ppms)} Messungen — stabil"
        )
        method = f"cumulative PPM ({stability})"
    elif cur_ppms:
        sorted_c = sorted(cur_ppms)
        ppm = sorted_c[len(sorted_c) // 2]
        method = f"current PPM Median aus {len(cur_ppms)} Werten"
    else:
        for ln in lines:
            m = _re.search(r"real sample rate[: ]+([\d.]+)", ln, _re.I)
            if m:
                try:
                    measured = float(m.group(1))
                    ppm = round((measured - 2048000.0) / 2048000.0 * 1e6)
                    method = f"Samplerate-Berechnung ({measured:.0f} S/s)"
                except Exception:
                    pass
                break

    return {
        "suggested_ppm": ppm,
        "current_ppm": cur_ppms[-1] if cur_ppms else None,
        "cumulative_ppm": cum_ppms[-1] if cum_ppms else None,
        "samples": len(cum_ppms),
        "method": method,
        "ppm_found": f"{ppm} ppm" if ppm is not None else None,
    }


def _ppm_result_hints(ppm, method: str, err: str = "") -> list:
    hints = []
    if err:
        hints.append(err)
    if ppm is None:
        hints.append("Kein PPM-Wert erkannt — Stick belegt oder nicht gefunden?")
        hints.append("Manuell: Wert ±5 beim FM-Hören testen")
    else:
        hints.append(f"Methode: {method}")
        if abs(ppm) > 100:
            hints.append("⚠ Wert > 100 ppm — sehr hoch, eventuell Stick-Problem")
        elif abs(ppm) > 50:
            hints.append("Hinweis: Typischer Bereich für RTL2838 ist ±20–60 ppm")
        hints.append("Übernehmen speichert dauerhaft; FM/Scanner neu starten zum Aktivieren")
    return hints


def _ppm_calibrate_run(duration_s: int = 180) -> dict:
    """Blockierend: rtl_test -p für duration_s (CLI / Sync-API)."""
    import subprocess as _sp
    duration_s = max(60, min(int(duration_s or 180), 300))
    stdout = ""
    err = ""
    try:
        cp = _sp.run(
            ["timeout", f"{duration_s}s", "rtl_test", "-p"],
            capture_output=True, text=True, timeout=duration_s + 20,
        )
        stdout = (cp.stdout or "") + (cp.stderr or "")
    except _sp.TimeoutExpired as e:
        stdout = (e.stdout or "") + (e.stderr or "")
        err = "Messung per Python-Timeout beendet"
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "rtl_test nicht gefunden (rtl-sdr Paket)",
            "suggested_ppm": None,
            "method": "nicht erkannt",
            "hints": ["rtl-sdr installieren: apt install rtl-sdr"],
            "stdout": "",
            "samples": 0,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "suggested_ppm": None,
            "method": "nicht erkannt",
            "hints": [str(e)],
            "stdout": "",
            "samples": 0,
        }

    parsed = _ppm_parse_log_text(stdout)
    hints = _ppm_result_hints(parsed.get("suggested_ppm"), parsed.get("method") or "", err)
    return {
        "ok": True,
        "stdout": stdout[-1000:],
        "suggested_ppm": parsed.get("suggested_ppm"),
        "current_ppm": parsed.get("current_ppm"),
        "cumulative_ppm": parsed.get("cumulative_ppm"),
        "ppm_found": parsed.get("ppm_found"),
        "method": parsed.get("method"),
        "hints": hints,
        "hint": (hints[0] if hints else ""),
        "samples": parsed.get("samples") or 0,
        "duration_s": duration_s,
    }


def _ppm_meta_read() -> dict:
    try:
        with open(PPM_CAL_META, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _ppm_meta_write(data: dict) -> None:
    try:
        tmp = PPM_CAL_META + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PPM_CAL_META)
    except Exception:
        pass


def _ppm_pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _ppm_open_log_write():
    """Log/Meta schreibbar machen (ältere root-Runs hinterlassen oft mode 644 root)."""
    for path in (PPM_CAL_LOG, PPM_CAL_META):
        try:
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o666)
                except OSError:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
        except OSError:
            pass
    log_f = open(PPM_CAL_LOG, "w", encoding="utf-8")
    try:
        os.chmod(PPM_CAL_LOG, 0o666)
    except OSError:
        pass
    return log_f


def _ppm_calibrate_start(duration_s: int = 180) -> dict:
    """Startet rtl_test -p im Hintergrund; Status per /api/ppm_calibrate/status."""
    import subprocess as _sp
    duration_s = max(60, min(int(duration_s or 180), 300))
    meta = _ppm_meta_read()
    if meta.get("running") and _ppm_pid_alive(meta.get("pid")):
        return {
            "ok": True,
            "started": False,
            "already_running": True,
            "duration_s": meta.get("duration_s", duration_s),
            "started_ts": meta.get("started_ts"),
            "pid": meta.get("pid"),
        }
    # alte Prozesse beenden
    try:
        _sp.run(["pkill", "-f", "rtl_test -p"], capture_output=True, timeout=3)
    except Exception:
        pass
    time.sleep(0.4)
    try:
        log_f = _ppm_open_log_write()
    except Exception as e:
        return {"ok": False, "error": f"Log nicht schreibbar: {e}"}
    try:
        proc = _sp.Popen(
            ["stdbuf", "-oL", "-eL", "timeout", f"{duration_s}s", "rtl_test", "-p"],
            stdout=log_f,
            stderr=_sp.STDOUT,
            start_new_session=True,
        )
    except FileNotFoundError:
        # stdbuf optional — Fallback ohne Line-Buffering
        try:
            log_f.seek(0)
            log_f.truncate()
            proc = _sp.Popen(
                ["timeout", f"{duration_s}s", "rtl_test", "-p"],
                stdout=log_f,
                stderr=_sp.STDOUT,
                start_new_session=True,
            )
        except FileNotFoundError:
            log_f.close()
            return {"ok": False, "error": "rtl_test nicht gefunden (rtl-sdr Paket)"}
        except Exception as e:
            log_f.close()
            return {"ok": False, "error": str(e)}
    except Exception as e:
        log_f.close()
        return {"ok": False, "error": str(e)}
    finally:
        try:
            log_f.close()
        except Exception:
            pass

    started_ts = time.time()
    meta = {
        "running": True,
        "pid": proc.pid,
        "started_ts": started_ts,
        "duration_s": duration_s,
        "log": PPM_CAL_LOG,
    }
    _ppm_meta_write(meta)
    try:
        os.chmod(PPM_CAL_META, 0o666)
    except OSError:
        pass
    return {
        "ok": True,
        "started": True,
        "already_running": False,
        "pid": proc.pid,
        "duration_s": duration_s,
        "started_ts": started_ts,
    }


def _ppm_calibrate_status() -> dict:
    meta = _ppm_meta_read()
    started_ts = float(meta.get("started_ts") or 0)
    duration_s = int(meta.get("duration_s") or 180)
    pid = meta.get("pid")
    alive = _ppm_pid_alive(pid)
    now = time.time()
    elapsed = max(0, int(now - started_ts)) if started_ts else 0
    remaining = max(0, duration_s - elapsed) if started_ts else duration_s

    stdout = ""
    try:
        with open(PPM_CAL_LOG, "r", encoding="utf-8", errors="replace") as f:
            stdout = f.read()
    except Exception:
        pass
    parsed = _ppm_parse_log_text(stdout)

    running = bool(meta.get("running")) and alive
    # timeout-Prozess beendet → fertig
    if meta.get("running") and not alive and started_ts:
        running = False
        if meta.get("running"):
            meta["running"] = False
            meta["finished_ts"] = now
            _ppm_meta_write(meta)

    done = bool(started_ts) and not running and bool(stdout or elapsed >= 5)
    ppm = parsed.get("suggested_ppm")
    hints = _ppm_result_hints(ppm, parsed.get("method") or "") if done else []

    return {
        "ok": True,
        "running": running,
        "done": done,
        "pid": pid,
        "elapsed_s": elapsed,
        "remaining_s": remaining if running else 0,
        "duration_s": duration_s,
        "progress_pct": min(100, int(100 * elapsed / duration_s)) if duration_s else 0,
        "current_ppm": parsed.get("current_ppm"),
        "cumulative_ppm": parsed.get("cumulative_ppm"),
        "suggested_ppm": ppm if done else parsed.get("cumulative_ppm"),
        "samples": parsed.get("samples") or 0,
        "method": parsed.get("method"),
        "hints": hints,
        "hint": (hints[0] if hints else ""),
        "has_log": bool(stdout),
        "stdout_tail": stdout[-400:] if done else "",
    }


@app.route("/api/rtlsdr/calibrate")
def api_rtlsdr_calibrate():
    # Sync: ~3 Min blockierend (CLI)
    duration = 180
    try:
        duration = int(request.args.get("duration", 180))
    except Exception:
        pass
    return jsonify(_ppm_calibrate_run(duration_s=duration))


@app.route("/api/ppm_calibrate", methods=["GET", "POST"])
def api_ppm_calibrate():
    """Sync-Kalibrierung (CLI). WebUI nutzt /start + /status für Live-Fortschritt."""
    duration = 180
    try:
        if request.method == "POST" and request.is_json:
            duration = int((request.get_json(silent=True) or {}).get("duration", 180))
        else:
            duration = int(request.args.get("duration", 180))
    except Exception:
        pass
    data = _ppm_calibrate_run(duration_s=duration)
    code = 200 if data.get("ok") else 500
    return jsonify(data), code


@app.route("/api/ppm_calibrate/start", methods=["POST", "GET"])
def api_ppm_calibrate_start():
    duration = 180
    try:
        if request.method == "POST" and request.is_json:
            duration = int((request.get_json(silent=True) or {}).get("duration", 180))
        else:
            duration = int(request.args.get("duration", 180))
    except Exception:
        pass
    # Radio freigeben (Core-Cmd)
    try:
        write_cmd("radio_stop")
    except Exception:
        pass
    time.sleep(1.0)
    data = _ppm_calibrate_start(duration_s=duration)
    code = 200 if data.get("ok") else 500
    return jsonify(data), code


@app.route("/api/ppm_calibrate/status")
def api_ppm_calibrate_status():
    return jsonify(_ppm_calibrate_status())


@app.route("/api/scanner/airband-stations", methods=["GET"])
def api_airband_stations():
    """Lokale Airband-Presets aus config/airband_stations.json."""
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules.radio import scanner as _sc
        stations = _sc.load_airband_stations()
        return jsonify({
            "ok": True,
            "stations": stations,
            "count": len(stations),
            "path": "config/airband_stations.json",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "stations": []}), 500


@app.route("/api/scanner/settings", methods=["GET", "POST"])
def api_scanner_settings():
    """
    v0.10.55: Scanner-Einstellungen lesen/schreiben.
    GET  → aktuelle Werte (inkl. scanner_use_spectrum)
    POST → Werte speichern, z.B. {"scanner_use_spectrum": true}
    """
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from settings import load_settings as _ls, save_settings as _ss
        s = _ls()

        if request.method == "GET":
            tune = {}
            try:
                from modules.radio import scanner as _sc
                # Live-State aus Core-Status falls verfügbar
                import json as _j
                st = {}
                try:
                    with open("/tmp/pidrive_status.json", "r", encoding="utf-8") as f:
                        st = _j.load(f) or {}
                except Exception:
                    st = {}
                # airband_tune steckt nicht immer im Status — Defaults reichen für Anzeige
                tune = _sc.get_airband_tune_params(s, S=None)
                # Wenn Core Status airband_tune hat:
                at = st.get("airband_tune")
                if isinstance(at, dict) and ("gain" in at or "sample_rate" in at or "hp_hz" in at):
                    for k in ("gain", "sample_rate", "hp_hz", "lp_hz"):
                        if k in at:
                            tune[k] = int(at[k])
                    tune["dirty"] = bool(at.get("dirty"))
            except Exception:
                tune = {
                    "gain": s.get("scanner_airband_gain", 20),
                    "sample_rate": s.get("scanner_airband_sample_rate", 16000),
                    "hp_hz": s.get("scanner_airband_hp_hz", 250),
                    "lp_hz": s.get("scanner_airband_lp_hz", 3000),
                    "dirty": False,
                    "default_gain": s.get("scanner_airband_gain", 20),
                    "default_sample_rate": s.get("scanner_airband_sample_rate", 16000),
                    "default_hp_hz": s.get("scanner_airband_hp_hz", 250),
                    "default_lp_hz": s.get("scanner_airband_lp_hz", 3000),
                }
            fm_tune = {}
            try:
                from modules.radio import fm as _fm
                fm_tune = _fm.get_fm_tune_params(s, S=None)
                ft = st.get("fm_tune")
                if isinstance(ft, dict) and ("hp_hz" in ft or "lp_hz" in ft):
                    for k in ("hp_hz", "lp_hz"):
                        if k in ft:
                            fm_tune[k] = int(ft[k])
                    fm_tune["dirty"] = bool(ft.get("dirty"))
            except Exception:
                fm_tune = {
                    "hp_hz": s.get("fm_hp_hz", 60),
                    "lp_hz": s.get("fm_lp_hz", 12000),
                    "dirty": False,
                    "default_hp_hz": s.get("fm_hp_hz", 60),
                    "default_lp_hz": s.get("fm_lp_hz", 12000),
                }
            return jsonify({
                "ok": True,
                "data": {
                    "scanner_use_spectrum":   s.get("scanner_use_spectrum", False),
                    "scanner_spectrum_debug": s.get("scanner_spectrum_debug", False),
                    "scanner_pmr_autotune":   s.get("scanner_pmr_autotune", False),
                    "scanner_pmr_hold_s":     s.get("scanner_pmr_hold_s", 15),
                    "scanner_pmr_trigger_on_db":  s.get("scanner_pmr_trigger_on_db", 25.0),
                    "scanner_pmr_trigger_off_db": s.get("scanner_pmr_trigger_off_db", 14.0),
                    "scanner_pmr_watch_s":        s.get("scanner_pmr_watch_s", 1.0),
                    "scanner_airband_last_freq":  s.get("scanner_airband_last_freq", 121.5),
                    "scanner_airband_autotune":   s.get("scanner_airband_autotune", True),
                    "scanner_airband_hold_s":     s.get("scanner_airband_hold_s", 20),
                    "scanner_airband_gain":       s.get("scanner_airband_gain", 20),
                    "scanner_airband_sample_rate": s.get("scanner_airband_sample_rate", 16000),
                    "scanner_airband_hp_hz":      s.get("scanner_airband_hp_hz", 250),
                    "scanner_airband_lp_hz":      s.get("scanner_airband_lp_hz", 3000),
                    "scanner_airband_squelch":    s.get("scanner_airband_squelch", 0),
                    "fm_hp_hz":                  s.get("fm_hp_hz", 60),
                    "fm_lp_hz":                  s.get("fm_lp_hz", 12000),
                    "scanner_gain":           s.get("scanner_gain", -1),
                    "scanner_squelch":        s.get("scanner_squelch", 25),
                    "ppm_correction":         s.get("ppm_correction", 0),
                    "airband_tune":           tune,
                    "fm_tune":                fm_tune,
                }
            })

        # POST: update fields
        body = request.get_json(silent=True) or {}
        changed = []
        for key in ("scanner_use_spectrum", "scanner_spectrum_debug",
                    "scanner_pmr_autotune", "scanner_pmr_hold_s",
                    "scanner_pmr_trigger_on_db", "scanner_pmr_trigger_off_db",
                    "scanner_pmr_watch_s", "scanner_airband_last_freq",
                    "scanner_airband_autotune", "scanner_airband_hold_s",
                    "scanner_airband_gain", "scanner_airband_sample_rate",
                    "scanner_airband_hp_hz", "scanner_airband_lp_hz",
                    "scanner_airband_squelch",
                    "fm_hp_hz", "fm_lp_hz",
                    "scanner_gain", "scanner_squelch"):
            if key in body:
                if key in ("scanner_pmr_autotune", "scanner_airband_autotune"):
                    s[key] = bool(body[key])
                elif key in ("scanner_pmr_hold_s",
                             "scanner_pmr_trigger_on_db",
                             "scanner_pmr_trigger_off_db",
                             "scanner_pmr_watch_s",
                             "scanner_airband_last_freq",
                             "scanner_airband_hold_s"):
                    s[key] = float(body[key])
                else:
                    s[key] = body[key]
                changed.append(key)
        if changed:
            _ss(s)
        return jsonify({"ok": True, "changed": changed, "data": {k: s[k] for k in changed}})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/scanner/airband-monitor", methods=["GET"])
def api_airband_monitor():
    """Status der Airband-Dauerüberwachung."""
    try:
        import json as _j
        st = {}
        try:
            with open("/tmp/pidrive_airband_monitor.json", "r", encoding="utf-8") as f:
                st = _j.load(f)
        except Exception:
            st = {"running": False}
        try:
            from modules.radio import scanner as _sc
            if hasattr(_sc, "get_airband_monitor_status"):
                st = _sc.get_airband_monitor_status()
        except Exception:
            pass
        return jsonify({"ok": True, "status": st})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/scanner/pmr-monitor", methods=["GET"])
def api_pmr_monitor():
    """Status + optionale Log-Tail der PMR-Überwachung."""
    try:
        import json as _j
        st = {}
        try:
            with open("/tmp/pidrive_pmr_monitor.json", "r", encoding="utf-8") as f:
                st = _j.load(f)
        except Exception:
            st = {"running": False}
        # Abgeleitete Felder nachziehen (auch wenn Status von Disk)
        try:
            from modules.radio import scanner as _sc
            if hasattr(_sc, "_pmr_enrich_status"):
                st = _sc._pmr_enrich_status(st if isinstance(st, dict) else {})
        except Exception:
            pass
        n = int(request.args.get("n", 20))
        n = max(1, min(n, 200))
        lines = []
        try:
            with open("/var/log/pidrive/pmr_monitor.jsonl", "r", encoding="utf-8") as f:
                raw = f.readlines()[-n:]
            for line in raw:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(_j.loads(line))
                except Exception:
                    lines.append({"raw": line[:200]})
        except FileNotFoundError:
            pass
        summary = {
            "monitor_effective_state": (st or {}).get("monitor_effective_state"),
            "peek_summary": {
                "count": (st or {}).get("peek_count"),
                "last_ch": (st or {}).get("last_peek_ch"),
                "last_relative_db": (st or {}).get("last_peek_relative_db"),
            },
            "error_summary": {
                "count": (st or {}).get("capture_error_count"),
                "streak": (st or {}).get("capture_error_streak"),
                "class": (st or {}).get("last_error_class"),
                "usb_reset_count": (st or {}).get("usb_reset_count"),
            },
        }
        return jsonify({
            "ok": True,
            "status": st,
            "summary": summary,
            "log": lines,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/spectrum/last")
def api_spectrum_last():
    return jsonify({
        "ok": True,
        "data": get_spectrum_debug(),
        "age": file_age("/tmp/pidrive_spectrum.json"),
        "exists": os.path.exists("/tmp/pidrive_spectrum.json"),
    })


@app.route("/api/spectrum/capture", methods=["GET", "POST"])
def api_spectrum_capture():
    """
    Spectrum Capture. Unterstützt:
    - band=pmr446|freenet → watch_channels() mit Peak-Identifizierung (v0.10.55)
    - mode=range          → Start/Stop-Bereich (Plot, Auto-SR oder sample_rate_hz)
    - mode=fm_sweep       → Legacy FM-Band-Sweep (Peak-Kandidaten, kein Plot)
    - mode=snapshot       → Einzelmessung bei center_mhz

    Bei aktivem PMR-Monitor: Standardmäßig Monitor stoppen und Capture fortsetzen
    (preempt_monitor=0 zum Ablehnen).
    """
    args = request.get_json(silent=True) or {}
    if not args:
        args = {k: v for k, v in request.args.items()}

    band = args.get("band", "")
    mode = (args.get("mode") or "fm_sweep").strip().lower()
    preempted_monitor = False
    try:
        from modules import source_state as _ss_gate
        import ipc as _ipc
        import time as _t_gate
        ok_gate, why = _ss_gate.rtl_capture_gate()
        if not ok_gate:
            raw_pre = args.get("preempt_monitor", args.get("stop_monitor", "1"))
            do_preempt = str(raw_pre).strip().lower() not in ("0", "false", "no", "off")
            if do_preempt and "PMR-Monitor" in (why or ""):
                _ipc.append_trigger("pmr_monitor_stop")
                for _ in range(40):
                    _t_gate.sleep(0.25)
                    ok_gate, why = _ss_gate.rtl_capture_gate()
                    if ok_gate:
                        preempted_monitor = True
                        break
            if do_preempt and not ok_gate and "Airband-Monitor" in (why or ""):
                _ipc.append_trigger("airband_monitor_stop")
                for _ in range(40):
                    _t_gate.sleep(0.25)
                    ok_gate, why = _ss_gate.rtl_capture_gate()
                    if ok_gate:
                        preempted_monitor = True
                        break
            # Orphaned rtl_sdr / busy without monitor → hard recover once
            if (not ok_gate) and do_preempt and "RTL-Gerät belegt" in (why or ""):
                try:
                    from modules.radio import rtlsdr as _rtl_rec
                    if hasattr(_rtl_rec, "recover_busy_device"):
                        _rtl_rec.recover_busy_device(
                            reason="spectrum_capture_preempt", level="hard"
                        )
                        _t_gate.sleep(0.35)
                        ok_gate, why = _ss_gate.rtl_capture_gate()
                except Exception:
                    pass
            if not ok_gate:
                return jsonify({
                    "ok": False,
                    "error": why,
                    "blocked_by_state": True,
                    "hint": "preempt_monitor=1 stoppt den Detektor und wiederholt den Capture",
                }), 409
    except Exception:
        pass
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules.radio import spectrum
        from settings import load_settings as _ls
        s = _ls()
        ppm  = int(args.get("ppm",  s.get("ppm_correction", 0)))
        gain = int(args.get("gain", s.get("scanner_gain", -1)))
        debug = bool(args.get("debug", s.get("scanner_spectrum_debug", False)))

        # v0.10.55: Peak-Identifizierung für PMR446 / Freenet
        if band in ("pmr446", "freenet"):
            import dataclasses as _dc
            watcher = spectrum.build_default_watcher(ppm=ppm, gain=gain)
            profile = spectrum.PMR446_PROFILE if band == "pmr446" else spectrum.FREENET_PROFILE
            try:
                ws = float(args.get("watch_seconds", profile.watch_seconds))
                ws = max(0.6, min(ws, 8.0))
            except (TypeError, ValueError):
                ws = profile.watch_seconds
            if abs(ws - profile.watch_seconds) > 0.05:
                profile = _dc.replace(profile, watch_seconds=ws)
            result = watcher.watch_channels(profile, debug=debug)
            cands = [
                spectrum._candidate_to_dict(c)
                for c in ((result.candidates if result else []) or [])
                if c is not None
            ]
            best = None
            if result and result.best_candidate:
                best = spectrum._candidate_to_dict(result.best_candidate)
            # UI-Filter: nur klarer Gewinner + nahe Konkurrenten (kein Nachbar-Rauschen)
            filtered = cands
            if best and cands:
                best_score = float(best.get("score") or 0)
                best_rel = float(best.get("relative_db") or 0)
                filtered = [
                    c for c in cands
                    if float(c.get("relative_db") or 0) >= max(12.0, best_rel - 10.0)
                    and float(c.get("score") or 0) >= max(8.0, best_score * 0.55)
                ]
                if not filtered:
                    filtered = [best]
            active_chs = []
            for c in filtered:
                nm = str(c.get("channel_name") or "")
                digits = "".join(ch for ch in nm if ch.isdigit())
                if digits:
                    active_chs.append(int(digits))
            primary = None
            if best:
                nm = str(best.get("channel_name") or "")
                digits = "".join(ch for ch in nm if ch.isdigit())
                if digits:
                    primary = int(digits)
            ended_s = 0.0
            if result:
                try:
                    ended_s = max(0.0, float(result.watch_ended_ts) - float(result.watch_started_ts))
                except Exception:
                    ended_s = float(ws)
            return jsonify({
                "ok": True,
                "band": band,
                "preempted_monitor": preempted_monitor,
                "data": {
                    "active_channels": filtered,
                    "active_channels_raw": cands,
                    "active_ch_numbers": active_chs,
                    "primary_ch": primary,
                    "found": bool(result and result.found),
                    "watch_seconds": round(ended_s, 2),
                    "frames_processed": result.frames_processed if result else 0,
                    "best_candidate": best,
                },
            })

        # Gemeinsame optionale Auflösungsparameter
        n_samp = args.get("sample_count")
        n_samp = int(n_samp) if n_samp not in (None, "") else None
        sr_raw = args.get("sample_rate_hz", args.get("sample_rate"))
        sr_hz = int(sr_raw) if sr_raw not in (None, "", "auto", "0") else None
        avg_raw = args.get("avg_frames", args.get("avg", 1))
        try:
            avg_frames = max(1, min(int(avg_raw or 1), 32))
        except Exception:
            avg_frames = 1

        if mode in ("range", "band"):
            start = float(args.get("start_mhz", args.get("start", 87.5)))
            stop = float(args.get("stop_mhz", args.get("stop", 108.0)))
            step_raw = args.get("step_mhz", args.get("step"))
            step = float(step_raw) if step_raw not in (None, "") else None
            result = spectrum.capture_range(
                start_mhz=start, stop_mhz=stop,
                sample_rate_hz=sr_hz,
                sample_count=n_samp if n_samp else 65536,
                ppm=ppm, gain=gain, step_mhz=step,
                avg_frames=avg_frames,
            )
        elif mode in ("snapshot", "single"):
            # UI sendete früher nur "center" — Alias akzeptieren
            center_raw = args.get("center_mhz", args.get("center", 98.0))
            center = float(center_raw)
            # 262144 Samples hängen auf manchen Sticks/USB-Hubs; Snapshot braucht weniger
            samp = n_samp if n_samp else 65536
            kwargs = dict(
                center_mhz=center, ppm=ppm, gain=gain, sample_count=samp,
                avg_frames=avg_frames,
            )
            if sr_hz:
                kwargs["sample_rate_hz"] = sr_hz
            result = spectrum.capture_spectrum(**kwargs)
            if result.get("ok") and result.get("mode") == "single":
                result["mode"] = "snapshot"
            if result.get("ok") and result.get("bin_hz"):
                result["rbw_hz"] = round(float(result["bin_hz"]), 3)
        else:
            start = float(args.get("start_mhz", 87.5))
            stop  = float(args.get("stop_mhz", 108.0))
            step  = float(args.get("step_mhz", 1.0))
            kwargs = dict(
                start_mhz=start, stop_mhz=stop, step_mhz=step,
                ppm=ppm, gain=gain,
            )
            if n_samp:
                kwargs["sample_count"] = n_samp
            if sr_hz:
                kwargs["sample_rate_hz"] = sr_hz
            result = spectrum.sweep_fm_band(**kwargs)
        if isinstance(result, dict):
            result = dict(result)
            result["preempted_monitor"] = preempted_monitor
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _spectrum_export_dir():
    """Ordner für Spektrum-Exports auf dem Pi."""
    try:
        from settings import BASE_DIR as _sb
        d = os.path.join(str(_sb), "exports", "spectrum")
    except Exception:
        d = os.path.join(str(Path.home()), "pidrive", "exports", "spectrum")
    os.makedirs(d, exist_ok=True)
    return d


@app.route("/api/spectrum/export", methods=["POST"])
def api_spectrum_export():
    """
    Speichert PNG (und optional Meta-JSON) unter pidrive/exports/spectrum/.
    Body JSON: { png_base64: "data:image/png;base64,..." | raw b64,
                 include_json: true, name: optional }
    """
    import base64
    import re as _re
    from datetime import datetime as _dt

    args = request.get_json(silent=True) or {}
    png_b64 = args.get("png_base64") or args.get("png") or ""
    if not png_b64:
        return jsonify({"ok": False, "error": "png_base64 fehlt"}), 400

    m = _re.match(r"^data:image/png;base64,(.+)$", png_b64, _re.I | _re.S)
    raw_b64 = m.group(1) if m else png_b64
    try:
        png_bytes = base64.b64decode(raw_b64, validate=False)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Base64 ungültig: {e}"}), 400
    if len(png_bytes) < 32 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        return jsonify({"ok": False, "error": "kein gültiges PNG"}), 400
    if len(png_bytes) > 8_000_000:
        return jsonify({"ok": False, "error": "PNG zu groß"}), 400

    stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
    hint = (args.get("name") or "").strip()
    hint = _re.sub(r"[^A-Za-z0-9._-]+", "_", hint)[:40]
    base = f"spectrum-{stamp}" + (f"-{hint}" if hint else "")

    out_dir = _spectrum_export_dir()
    png_path = os.path.join(out_dir, base + ".png")
    try:
        with open(png_path, "wb") as f:
            f.write(png_bytes)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    json_path = None
    if args.get("include_json", True):
        try:
            from modules.radio import spectrum as _sp
            data = _sp.load_last_spectrum() or {}
        except Exception:
            data = {}
        # Spektrum-Bins weglassen oder stark kürzen — Meta reicht zum Nachvollziehen
        meta = {k: v for k, v in data.items() if k != "spectrum_db"}
        spec = data.get("spectrum_db") or []
        if spec:
            # Downsample für Archiv (~500 Punkte)
            step = max(1, len(spec) // 500)
            meta["spectrum_db_downsampled"] = spec[::step]
            meta["spectrum_bins_full"] = len(spec)
        meta["export_png"] = os.path.basename(png_path)
        json_path = os.path.join(out_dir, base + ".json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception:
            json_path = None

    return jsonify({
        "ok": True,
        "dir": out_dir,
        "png": png_path,
        "json": json_path,
        "name": os.path.basename(png_path),
    })


@app.route("/api/spectrum/exports")
def api_spectrum_exports_list():
    out_dir = _spectrum_export_dir()
    try:
        files = sorted(
            (f for f in os.listdir(out_dir) if f.endswith((".png", ".json"))),
            reverse=True,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "dir": out_dir})
    return jsonify({
        "ok": True,
        "dir": out_dir,
        "files": files[:50],
        "count": len(files),
    })


@app.route("/api/spectrum/stations")
def api_spectrum_stations():
    try:
        from modules.radio import spectrum
        min_hits = int(request.args.get("min_hits", 2))
        stations = spectrum.get_confirmed_stations(min_hits=min_hits)
        return jsonify({"ok": True, "stations": stations, "count": len(stations)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/avrcp")
def api_avrcp():
    data = read_json(AVRCP_FILE, {})
    return jsonify({
        "ok": bool(data),
        "data": data,
        "exists": os.path.exists(AVRCP_FILE),
        "age": file_age(AVRCP_FILE),
    })


@app.route("/api/service")
def api_service():
    name = request.args.get("name", "pidrive_core")
    if name not in ("pidrive_core", "pidrive_web", "pidrive_avrcp"):
        return jsonify({"ok": False, "error": "Ungültiger Service"}), 400
    return jsonify(safe_run(f"systemctl status {name} --no-pager"))


@app.route("/api/debug/summary")
def api_debug_summary():
    return jsonify({
        "ok": True,
        "version": get_version(),
        "source_state": get_source_state_debug(),
        "dab_scan": get_dab_scan_debug(),
        "dab_status": get_dab_status_debug(),
        "spectrum": get_spectrum_debug(),
        "audio": get_audio_debug(),
        "known_bt_devices": read_json(KNOWN_BT_FILE, {"devices": []}),
        "bt_agent": read_json(BT_AGENT_FILE, {}),
    })



# ──────────────────────────────────────────────────────────────────────────────
# Webradio-API liegt in web.api.routes_webradio (Blueprint)
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/api/diag/system")
def api_diag_system():
    """Diagnose-Daten: lsusb, Prozesse mit User/PID/Rechten, Audio-Pfad, CPU/RAM."""
    from web.shared import safe_run
    import os, json
    
    out = {}
    
    # lsusb
    r = safe_run("lsusb 2>/dev/null")
    out["lsusb"] = r.get("stdout", "").strip()
    
    # Relevante Prozesse mit User + PID + Cmdline
    r = safe_run("ps -eo pid,user,pcpu,pmem,stat,cmd --no-headers 2>/dev/null | "
                 "grep -E 'python|pipewire|wireplumber|pulseaudio|welle|rtl_fm|mpv|bluetoothd|raspotify|librespot' | "
                 "grep -v grep | head -20")
    out["processes"] = r.get("stdout", "").strip()
    
    # CPU + RAM
    r = safe_run("top -bn1 2>/dev/null | head -5")
    out["top"] = r.get("stdout", "").strip()
    
    # Parallele pidrive-Instanzen
    # pgrep -x: exakter Match, verhindert Selbst-/Substring-Treffer
    r = safe_run("pgrep -c -f 'python3.*main_core' 2>/dev/null || echo 0")
    out["core_instances"] = (r.get("stdout","1")).strip()
    r = safe_run("pgrep -cx welle-cli 2>/dev/null || echo 0")
    out["wellechli_instances"] = (r.get("stdout","0")).strip()
    r = safe_run("pgrep -cx rtl_fm 2>/dev/null || echo 0")
    out["rtlfm_instances"] = (r.get("stdout","0")).strip()
    
    # PulseAudio System vs User
    r = safe_run("pgrep -a pipewire 2>/dev/null") or safe_run("pgrep -a pulseaudio 2>/dev/null")
    pa_procs = r.get("stdout","").strip()
    out["pa_mode"] = "system" if "--system" in pa_procs else ("user" if pa_procs else "none")
    out["pa_procs"] = pa_procs
    
    # Aktueller Audio-Pfad
    r = safe_run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null")
    out["pa_sinks"] = r.get("stdout","").strip()
    r = safe_run("PULSE_SERVER=unix:/var/run/pulse/native pactl get-default-sink 2>/dev/null")
    out["pa_default_sink"] = r.get("stdout","").strip()
    r = safe_run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sink-inputs short 2>/dev/null")
    out["pa_inputs"] = r.get("stdout","").strip()
    
    # asound.conf
    try:
        out["asound_conf"] = open("/etc/asound.conf").read()
    except: out["asound_conf"] = "(nicht vorhanden)"
    
    # ALSA Karten
    r = safe_run("aplay -l 2>/dev/null")
    out["alsa_cards"] = r.get("stdout","").strip()
    
    # Berechtigungen wichtiger Dateien
    r = safe_run("ls -la /var/run/pulse/ 2>/dev/null; ls -la /tmp/pidrive_cmd 2>/dev/null || echo '(kein cmd)'")
    out["permissions"] = r.get("stdout","").strip()
    
    # Kernel + uptime
    r = safe_run("uname -r; uptime")
    out["system"] = r.get("stdout","").strip()
    
    return jsonify({"ok": True, "data": out})


@app.route("/api/dab/errfile")
def api_dab_errfile():
    """DAB welle-cli Stderr-Datei lesen (Session-spezifisch oder global)."""
    import os, glob
    from web.shared import read_json
    
    session_id = request.args.get("session", "")
    lines_n = int(request.args.get("n", "80"))
    
    # Session-spezifische Datei bevorzugen
    candidates = []
    if session_id:
        sf = f"/tmp/pidrive_dab_{session_id}.err"
        if os.path.exists(sf):
            candidates.append(sf)
    
    # Alle dab err files, neueste zuerst
    all_err = sorted(glob.glob("/tmp/pidrive_dab_*.err"), key=os.path.getmtime, reverse=True)
    for f in all_err:
        if f not in candidates:
            candidates.append(f)
    
    if not candidates:
        return jsonify({"ok": False, "error": "Keine DAB Fehler-Datei gefunden", "files": []})
    
    target = candidates[0]
    try:
        with open(target, errors="replace") as f:
            content = f.readlines()
        
        # Last N lines
        lines = content[-lines_n:]
        
        # Parse line types
        parsed = []
        for ln in lines:
            ln = ln.rstrip()
            if not ln: continue
            if "Superframe sync succeeded" in ln:
                t = "success"
            elif "Found sync" in ln:
                t = "sync"
            elif "Lost" in ln or "failed" in ln or "error" in ln.lower():
                t = "error"
            elif "DLS:" in ln or "UTCTime" in ln:
                t = "dls"
            elif "PCM" in ln or "pcm" in ln:
                t = "pcm"
            elif "Service" in ln or "Ensemble" in ln:
                t = "info"
            else:
                t = "normal"
            parsed.append({"line": ln, "type": t})
        
        return jsonify({
            "ok": True,
            "file": target,
            "size": os.path.getsize(target),
            "total_lines": len(content),
            "lines": parsed,
            "all_files": [{"path": f, "size": os.path.getsize(f),
                           "age_s": int(__import__("time").time() - os.path.getmtime(f))}
                          for f in candidates[:5]],
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "file": target})


@app.route("/api/system/resources")
def api_system_resources():
    import subprocess as _sp2
    data = {"ok": True}
    try:
        df = _sp2.run("df -h / 2>/dev/null", shell=True, capture_output=True, text=True).stdout
        for ln in df.splitlines():
            p = ln.split()
            if len(p) >= 5 and p[0] != "Filesystem":
                pct_int = int(p[4].rstrip('%')) if p[4].rstrip('%').isdigit() else 0
                data.update({
                    "disk_used": p[2],
                    "disk_total": p[1],
                    "disk_avail": p[3],
                    "disk_pct": p[4],
                    "disk_warn": pct_int > 80
                })
    except Exception:
        pass
    try:
        fr = _sp2.run("free -m 2>/dev/null", shell=True, capture_output=True, text=True).stdout
        for ln in fr.splitlines():
            if ln.startswith("Mem:"):
                p = ln.split()
                data.update({
                    "ram_total_mb": p[1],
                    "ram_used_mb": p[2],
                    "ram_free_mb": p[3]
                })
    except Exception:
        pass
    try:
        data["uptime"] = _sp2.run("uptime -p 2>/dev/null", shell=True,
                                  capture_output=True, text=True).stdout.strip()
    except Exception:
        pass
    # Throttling (S8) — fehlt → UI darf nicht „OK“ vortäuschen
    try:
        thr = _sp2.run("vcgencmd get_throttled 2>/dev/null", shell=True,
                       capture_output=True, text=True).stdout.strip()
        if "=" in thr:
            data["throttled"] = thr.split("=", 1)[1].strip()
        elif thr:
            data["throttled"] = thr
        else:
            data["throttled"] = None
    except Exception:
        data["throttled"] = None
    logs = {}
    for lf in ["pidrive.log", "core.log", "display.log"]:
        lp = f"/var/log/pidrive/{lf}"
        if os.path.exists(lp):
            logs[lf] = {"size_kb": round(os.path.getsize(lp) / 1024, 1)}
    data["logs"] = logs
    return jsonify(data)


if __name__ == "__main__":
    # threaded: langer Monitor-Stream (/api/audio/listen) darf Polling nicht blockieren
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
