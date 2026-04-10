#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import socket
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))

CMD_FILE = "/tmp/pidrive_cmd"
STATUS_FILE = "/tmp/pidrive_status.json"
MENU_FILE = "/tmp/pidrive_menu.json"
PROGRESS_FILE = "/tmp/pidrive_progress.json"
LIST_FILE = "/tmp/pidrive_list.json"
LOG_FILE  = "/var/log/pidrive/pidrive.log"
READY_FILE= "/tmp/pidrive_ready"

ALLOWED_COMMANDS = {
    "up", "down", "left", "right", "enter", "back",
    "wifi_on", "wifi_off", "wifi_toggle", "wifi_scan",
    "bt_on", "bt_off", "bt_toggle", "bt_scan",
    "spotify_on", "spotify_off", "spotify_toggle",
    "radio_stop", "library_stop",
    "audio_klinke", "audio_hdmi", "audio_bt", "audio_all",
    "vol_up", "vol_down",
    "dab_scan", "fm_scan",
    "fm_next", "fm_prev", "dab_next", "dab_prev",
    "lib_browse",
    "reboot", "shutdown", "sys_info", "sys_version", "update",
}

def read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_cmd(cmd):
    with open(CMD_FILE, "w", encoding="utf-8") as f:
        f.write(cmd.strip() + "\n")

def file_age(path):
    try:
        return round(time.time() - os.path.getmtime(path), 1)
    except Exception:
        return None

def get_ip():
    # robust genug für LAN/WLAN-Entwicklung
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "?"
def safe_run(cmd):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=15
        )
        return {
            "ok": r.returncode == 0,
            "code": r.returncode,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "cmd": cmd,
        }
    except Exception as e:
        return {
            "ok": False,
            "code": -1,
            "stdout": "",
            "stderr": str(e),
            "cmd": cmd,
        }

def get_version():
    try:
        with open(BASE_DIR / "VERSION", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "?"

def build_view_model():
    status   = read_json(STATUS_FILE, {})
    menu     = read_json(MENU_FILE,   {})
    progress = read_json(PROGRESS_FILE, {})
    list_data= read_json(LIST_FILE,   {})

    # v0.7.0: nodes aus Baummodell, Compat-Fallback
    nodes      = menu.get("nodes",      [])
    categories = menu.get("categories", [])
    items_list = menu.get("items",      [])

    # Selektierter Knoten
    cursor   = menu.get("cursor", 0)
    sel_node = nodes[cursor] if nodes and cursor < len(nodes) else {}

    # Debug-Info für Phase 2 (GPT-5.4)
    debug = {
        "rev":           menu.get("rev", 0),
        "path":          menu.get("path", []),
        "title":         menu.get("title", ""),
        "cursor":        cursor,
        "can_back":      menu.get("can_back", False),
        "selected_label":sel_node.get("label","") if isinstance(sel_node,dict) else str(sel_node),
        "selected_type": sel_node.get("type","") if isinstance(sel_node,dict) else "",
        "node_count":    len(nodes),
        "core_ready":    os.path.exists(READY_FILE),
        "status_age":    file_age(STATUS_FILE),
        "menu_age":      file_age(MENU_FILE),
    }

    return {
        "version":        get_version(),
        "ip":             get_ip(),
        "status":         status,
        "menu":           menu,
        "progress":       progress,
        "list_data":      list_data,
        "nodes":          nodes,
        "categories":     categories,
        "items":          items_list,
        "path":           menu.get("path", []),
        "cursor":         cursor,
        "rev":            menu.get("rev", 0),
        "can_back":       menu.get("can_back", False),
        "debug":          debug,
        "status_age":     file_age(STATUS_FILE),
        "menu_age":       file_age(MENU_FILE),
        "progress_age":   file_age(PROGRESS_FILE),
        "list_age":       file_age(LIST_FILE),
        "status_exists":  os.path.exists(STATUS_FILE),
        "menu_exists":    os.path.exists(MENU_FILE),
        "progress_exists":os.path.exists(PROGRESS_FILE),
        "list_exists":    os.path.exists(LIST_FILE),
        "log_exists":     os.path.exists(LOG_FILE),
    }

@app.route("/")
def index():
    vm = build_view_model()
    return render_template("index.html", vm=vm)

@app.route("/api/state")
def api_state():
    return jsonify(build_view_model())

@app.route("/api/cmd", methods=["POST"])
def api_cmd():
    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()

    if not cmd:
        return jsonify({"ok": False, "error": "Kein Befehl übergeben"}), 400

    prefixes = ("cat:", "reload_stations:", "scan_up:", "scan_down:",
                  "scan_next:", "scan_prev:")
    if not (cmd in ALLOWED_COMMANDS or any(cmd.startswith(p) for p in prefixes)):
        return jsonify({"ok": False, "error": f"Befehl nicht erlaubt: {cmd}"}), 400

    try:
        write_cmd(cmd)
        return jsonify({"ok": True, "cmd": cmd})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/logs")
def api_logs():
    target = request.args.get("target", "core")

    if target == "core":
        cmd = "journalctl -u pidrive_core -n 100 --no-pager"
    elif target == "display":
        cmd = "journalctl -u pidrive_display -n 100 --no-pager"
    elif target == "app":
        cmd = f"tail -n 100 {LOG_FILE}"
    else:
        return jsonify({"ok": False, "error": "Ungültiges Log-Target"}), 400

    return jsonify(safe_run(cmd))

@app.route("/api/diagnose")
def api_diagnose():
    # Falls diagnose.py vorhanden ist
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

@app.route("/api/grep")
def api_grep():
    cmd = r'''grep -R "pidrive_status\|pidrive_menu\|write_json\|json.dump" /home/pi/pidrive/pidrive -n'''
    return jsonify(safe_run(cmd))

@app.route("/api/ready")
def api_ready():
    import pathlib
    ready = pathlib.Path("/tmp/pidrive_ready").exists()
    return jsonify({
        "core_ready":   ready,
        "status_ok":    pathlib.Path("/tmp/pidrive_status.json").exists(),
        "menu_ok":      pathlib.Path("/tmp/pidrive_menu.json").exists(),
    })

@app.route("/api/nav", methods=["POST"])
def api_nav():
    """Direktnavigation: {"target": 3} setzt Cursor auf Index 3.
    Ersetzt N einzelne up/down-Requests durch einen einzigen Aufruf."""
    data = request.get_json(silent=True) or {}
    target = data.get("target")
    cmd    = data.get("cmd")

    if cmd:
        # Direkt-Cmd (enter, back etc.)
        if cmd not in ("enter","back","left","right","up","down"):
            return jsonify({"ok": False, "error": "cmd nicht erlaubt"}), 400
        try:
            write_cmd(cmd)
            return jsonify({"ok": True, "cmd": cmd})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    if target is None:
        return jsonify({"ok": False, "error": "target oder cmd fehlt"}), 400

    # Aktuellen Cursor aus menu.json lesen
    menu = read_json(MENU_FILE, {})
    current = menu.get("cursor", menu.get("item", 0))
    steps = int(target) - int(current)

    if steps == 0:
        # Schon dort — direkt enter
        try:
            write_cmd("enter")
            return jsonify({"ok": True, "steps": 0, "cmd": "enter"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    direction = "down" if steps > 0 else "up"
    import time
    try:
        for _ in range(abs(steps)):
            write_cmd(direction)
            time.sleep(0.06)   # kurze Pause zwischen Schritten
        write_cmd("enter")
        return jsonify({"ok": True, "steps": steps, "direction": direction})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/service")
def api_service():
    name = request.args.get("name", "pidrive_core")
    if name not in ("pidrive_core", "pidrive_display", "pidrive_web"):
        return jsonify({"ok": False, "error": "Ungültiger Service"}), 400
    return jsonify(safe_run(f"systemctl status {name} --no-pager"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)