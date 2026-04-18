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
RTLSDR_FILE  = "/tmp/pidrive_rtlsdr.json"
AVRCP_FILE   = "/tmp/pidrive_avrcp.json"
LIST_FILE    = "/tmp/pidrive_list.json"
LOG_FILE  = "/var/log/pidrive/pidrive.log"
READY_FILE= "/tmp/pidrive_ready"

ALLOWED_COMMANDS = {
    "up", "down", "left", "right", "enter", "back",
    "wifi_on", "wifi_off", "wifi_toggle", "wifi_scan",
    "bt_on", "bt_off", "bt_toggle", "bt_scan",
    "bt_disconnect", "bt_reconnect_last",
    "spotify_on", "spotify_off", "spotify_toggle",
    "radio_stop", "library_stop",
    "audio_klinke", "audio_hdmi", "audio_bt", "audio_all",
    "vol_up", "vol_down",
    "gain_fm_auto", "gain_dab_auto",
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


PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"


def get_audio_debug() -> dict:
    """
    Vollstaendiges Audio-Debug-Cockpit fuer WebUI — v0.8.12.
    Liefert:
      - pulse_active: PulseAudio Systemdaemon aktiv?
      - default_sink: aktueller Default-Sink
      - sinks:        alle verfuegbaren PulseAudio-Sinks
      - sink_inputs:  laufende Sink-Inputs mit Prozessnamen
      - decision:     letzte audio.py Routing-Entscheidung
    """
    data = {
        "pulse_active": False,
        "default_sink": "",
        "sinks": [],
        "sink_inputs": [],
        "decision": {},
    }

    # 1) letzte PiDrive Audio-Entscheidung aus shared state file (v0.8.13)
    # Liest /tmp/pidrive_audio_state.json — geschrieben vom Core-Prozess
    # get_last_decision() zeigte nur den WebUI-Prozesszustand, nicht den Core-Zustand
    try:
        import sys
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules.audio import read_last_decision_file
        data["decision"] = read_last_decision_file()
    except Exception:
        data["decision"] = {}

    # 2) PulseAudio aktiv?
    try:
        pa = safe_run("systemctl is-active pulseaudio 2>/dev/null")
        data["pulse_active"] = (pa.get("stdout", "").strip() == "active")
    except Exception:
        pass

    # 3) Default-Sink
    try:
        ds = safe_run(PA_ENV + " pactl get-default-sink 2>/dev/null")
        data["default_sink"] = (ds.get("stdout", "") or "").strip()
        # Fallback: pactl info wenn get-default-sink leer ist (v0.8.13)
        if not data["default_sink"]:
            info = safe_run(PA_ENV + " pactl info 2>/dev/null")
            for ln in (info.get("stdout", "") or "").splitlines():
                if "Default Sink:" in ln:
                    data["default_sink"] = ln.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    # 4) Alle Sinks
    try:
        sinks = safe_run(PA_ENV + " pactl list sinks short 2>/dev/null")
        out = sinks.get("stdout", "") or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                typ  = "bt" if "bluez_sink" in name else \
                       "hdmi" if "hdmi" in name.lower() else \
                       "alsa" if "alsa_output" in name else "other"
                data["sinks"].append({
                    "id":   parts[0],
                    "name": name,
                    "type": typ,
                    "raw":  line.strip(),
                })
    except Exception:
        pass

    # 5) Sink-Inputs (kurz)
    try:
        sin = safe_run(PA_ENV + " pactl list sink-inputs short 2>/dev/null")
        out = sin.get("stdout", "") or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            data["sink_inputs"].append({
                "id":     parts[0] if len(parts) > 0 else "",
                "sink":   parts[1] if len(parts) > 1 else "",
                "client": parts[2] if len(parts) > 2 else "",
                "driver": parts[3] if len(parts) > 3 else "",
                "raw":    line.strip(),
            })
    except Exception:
        pass

    # 6) Sink-Input Details: Prozessname aus vollem pactl list
    try:
        detail = safe_run(PA_ENV + " pactl list sink-inputs 2>/dev/null")
        txt = detail.get("stdout", "") or ""
        blocks = txt.split("Sink Input #")
        parsed = {}
        for block in blocks[1:]:
            lines = block.splitlines()
            if not lines:
                continue
            sid = lines[0].strip()
            item = {
                "application_name":  "",
                "process_binary":    "",
                "process_id":        "",
                "media_name":        "",
            }
            for ln in lines:
                s = ln.strip()
                if 'application.name = "' in s:
                    item["application_name"] = s.split('"')[1]
                elif 'application.process.binary = "' in s:
                    item["process_binary"] = s.split('"')[1]
                elif 'application.process.id = "' in s:
                    item["process_id"] = s.split('"')[1]
                elif 'media.name = "' in s:
                    item["media_name"] = s.split('"')[1]
            parsed[sid] = item

        for row in data["sink_inputs"]:
            extra = parsed.get(str(row.get("id", "")), {})
            row.update(extra)
    except Exception:
        pass

    return data


def build_view_model():
    status   = read_json(STATUS_FILE, {})
    menu     = read_json(MENU_FILE,   {})
    progress = read_json(PROGRESS_FILE, {})
    rtlsdr   = read_json(RTLSDR_FILE, {})
    avrcp    = read_json(AVRCP_FILE,  {})
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
        "rtlsdr":         rtlsdr,
        "rtlsdr_age":     file_age(RTLSDR_FILE),
        "rtlsdr_exists":  os.path.exists(RTLSDR_FILE),
        "avrcp":          avrcp,
        "avrcp_age":      file_age(AVRCP_FILE),
        "avrcp_exists":   os.path.exists(AVRCP_FILE),
        "audio_debug":    get_audio_debug(),
        "list_data":      list_data,
        "list_active":    list_data.get("active", False),
        "list_title":     list_data.get("title", ""),
        "list_items":     list_data.get("items", []),
        "list_selected":  list_data.get("selected", 0),
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

    prefixes = ("cat:", "reload_stations:",
                "scan_up:", "scan_down:", "scan_next:", "scan_prev:",
                "scan_jump:", "scan_step:", "scan_setfreq:", "scan_inputfreq:",
                "bt_connect:", "wifi_connect:", "bt_repair:",
                "fm_gain:", "dab_gain:")
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
    elif target == "avrcp":
        cmd = "journalctl -u pidrive_avrcp -n 100 --no-pager"
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

@app.route("/api/rtlsdr")
def api_rtlsdr():
    data = read_json(RTLSDR_FILE, {})
    return jsonify({"ok": bool(data), "data": data,
                    "exists": os.path.exists(RTLSDR_FILE),
                    "age": file_age(RTLSDR_FILE)})

@app.route("/api/rtlsdr/refresh")
def api_rtlsdr_refresh():
    """Passive Diagnose neu ausführen (öffnet Device NICHT)."""
    import subprocess as _sp
    try:
        _sp.run(["/usr/bin/python3",
                 "/home/pi/pidrive/pidrive/modules/rtlsdr.py",
                 "--json"],
                timeout=10, capture_output=True)
    except Exception:
        pass
    return jsonify({"ok": True, "data": read_json(RTLSDR_FILE, {})})

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
    if name not in ("pidrive_core", "pidrive_display", "pidrive_web", "pidrive_avrcp"):
        return jsonify({"ok": False, "error": "Ungültiger Service"}), 400
    return jsonify(safe_run(f"systemctl status {name} --no-pager"))


@app.route("/api/avrcp")
def api_avrcp():
    """AVRCP Debug-Status."""
    data = read_json(AVRCP_FILE, {})
    return jsonify({
        "ok":     bool(data),
        "data":   data,
        "exists": os.path.exists(AVRCP_FILE),
        "age":    file_age(AVRCP_FILE),
    })


@app.route("/api/audio")
def api_audio():
    """Audio-Routing Debug Cockpit — v0.8.12: Sinks + Sink-Inputs + Prozessnamen."""
    return jsonify({
        "ok":   True,
        "data": get_audio_debug(),
    })


@app.route("/api/gain")
def api_gain():
    """Gibt aktuelle Gain-Einstellungen zurück."""
    try:
        import sys
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from settings import load_settings as _ls
        s = _ls()
        return jsonify({
            "ok": True,
            "fm_gain":  s.get("fm_gain",  -1),
            "dab_gain": s.get("dab_gain", -1),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/volume")
def api_volume():
    """Gibt aktuelle PulseAudio-Lautstärke zurück."""
    try:
        r = safe_run(
            "PULSE_SERVER=unix:/var/run/pulse/native "
            "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null"
        )
        txt = r.get("stdout", "") or ""
        vol = ""
        for part in txt.split():
            if part.endswith("%"):
                vol = part
                break
        return jsonify({"ok": True, "volume_raw": txt.strip(), "volume": vol})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)