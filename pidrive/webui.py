#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
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
LOG_FILE     = "/var/log/pidrive/pidrive.log"
READY_FILE   = "/tmp/pidrive_ready"
KNOWN_BT_FILE = "/tmp/pidrive_bt_known_devices.json"
BT_AGENT_FILE = "/tmp/pidrive_bt_agent.json"

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
    "dab_scan", "dab_scan_replace", "fm_scan",
    "fm_next", "fm_prev", "dab_next", "dab_prev",
    "lib_browse",
    "reboot", "shutdown", "sys_info", "sys_version", "update",
    "rtlsdr_reset",
    "bt_backup", "bt_restore",
}

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

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


def _sink_is_hdmi(name: str) -> bool:
    import re
    n = (name or "").lower()
    if "hdmi" in n:
        return True
    if re.search(r"alsa_output\.0\.", name or ""):
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Audio Debug
# ──────────────────────────────────────────────────────────────────────────────

def get_audio_debug() -> dict:
    """
    Vollständiges Audio-Debug-Cockpit.
    Liefert:
      - pulse_active
      - default_sink
      - sinks
      - sink_inputs
      - decision (/tmp/pidrive_audio_state.json)
      - current_volume
    """
    data = {
        "pulse_active": False,
        "default_sink": "",
        "sinks": [],
        "sink_inputs": [],
        "decision": {},
        "current_volume": "–",
    }

    # Letzte Core-Entscheidung + Fallback-Badge
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules.audio import read_last_decision_file
        data["decision"] = read_last_decision_file()
        # v0.9.26: Fallback-Badge wenn requested≠effective
        dec = data["decision"]
        data["fallback_active"] = bool(
            dec.get("requested") and dec.get("effective") and
            dec.get("requested") != dec.get("effective")
        )
        data["fallback_reason"] = dec.get("reason", "")
    except Exception:
        data["decision"] = {}
        data["fallback_active"] = False
        data["fallback_reason"] = ""

    # PulseAudio — drei Zustände (v0.9.26 Korrektur):
    # "active"   : systemctl aktiv UND pactl antwortet
    # "service"  : systemctl aktiv, aber pactl leer (Socket-Problem)
    # False      : systemctl nicht aktiv
    try:
        pa_svc = safe_run("systemctl is-active pulseaudio 2>/dev/null")
        pa_svc_ok = (pa_svc.get("stdout", "").strip() in ("active", "activating"))
        if pa_svc_ok:
            pa2 = safe_run(PA_ENV + " pactl info 2>/dev/null")
            pa_api_ok = bool(pa2.get("stdout", "").strip())
            data["pulse_active"] = True if pa_api_ok else "service_only"
        else:
            data["pulse_active"] = False
    except Exception:
        data["pulse_active"] = False

    # Default-Sink
    try:
        ds = safe_run(PA_ENV + " pactl get-default-sink 2>/dev/null")
        data["default_sink"] = (ds.get("stdout", "") or "").strip()
        if not data["default_sink"]:
            info = safe_run(PA_ENV + " pactl info 2>/dev/null")
            for ln in (info.get("stdout", "") or "").splitlines():
                if "Default Sink:" in ln:
                    data["default_sink"] = ln.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    # Alle Sinks
    try:
        sinks = safe_run(PA_ENV + " pactl list sinks short 2>/dev/null")
        out = sinks.get("stdout", "") or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                typ = (
                    "bt" if "bluez_sink" in name else
                    "hdmi" if _sink_is_hdmi(name) else
                    "alsa" if "alsa_output" in name else
                    "other"
                )
                data["sinks"].append({
                    "id": parts[0],
                    "name": name,
                    "type": typ,
                    "raw": line.strip(),
                })
    except Exception:
        pass

    # Sink-Inputs kurz — v0.9.26: nur echte Inputs (id muss Zahl sein)
    try:
        sin = safe_run(PA_ENV + " pactl list sink-inputs short 2>/dev/null")
        out = sin.get("stdout", "") or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if not parts or not parts[0].isdigit():
                continue  # keine Platzhalterzeile
            data["sink_inputs"].append({
                "id":     parts[0],
                "sink_id": parts[1] if len(parts) > 1 else "",
                "client": parts[2] if len(parts) > 2 else "",
                "driver": parts[3] if len(parts) > 3 else "",
                "raw":    line.strip(),
            })
    except Exception:
        pass

    # Sink-Input Details
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
                "application_name": "",
                "process_binary": "",
                "process_id": "",
                "media_name": "",
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

        # Sink-ID zu Namen auflösen
        sink_id_map = {s["id"]: s["name"] for s in data["sinks"]}
        for row in data["sink_inputs"]:
            extra = parsed.get(str(row.get("id", "")), {})
            row.update(extra)
            row["app_name"] = extra.get("application_name") or extra.get("media_name") or ""
            row["binary"]   = extra.get("process_binary", "")
            row["pid"]      = extra.get("process_id", "")
            row["sink_name"]= sink_id_map.get(row.get("sink_id", ""), "")
    except Exception:
        pass

    # Robuste Lautstärke
    try:
        vol = api_volume().json if hasattr(api_volume(), "json") else {}
        if isinstance(vol, dict):
            data["current_volume"] = vol.get("volume", "–")
    except Exception:
        pass

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Source / DAB / Spectrum Debug
# ──────────────────────────────────────────────────────────────────────────────

def get_source_state_debug():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules import source_state
        return source_state.load_snapshot_file() or source_state.snapshot()
    except Exception as e:
        return {"error": str(e)}


def get_dab_scan_debug():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules import dab
        return dab.load_last_scan_diag_file() or dab.get_last_scan_diag()
    except Exception as e:
        return {"error": str(e)}


def get_spectrum_debug():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules import spectrum
        return spectrum.load_last_spectrum()
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# View Model
# ──────────────────────────────────────────────────────────────────────────────

def build_view_model():
    status    = read_json(STATUS_FILE, {})
    menu      = read_json(MENU_FILE, {})
    progress  = read_json(PROGRESS_FILE, {})
    rtlsdr    = read_json(RTLSDR_FILE, {})
    avrcp     = read_json(AVRCP_FILE, {})
    list_data = read_json(LIST_FILE, {})
    bt_known  = read_json(KNOWN_BT_FILE, {"devices": []})
    bt_agent  = read_json(BT_AGENT_FILE, {})

    nodes      = menu.get("nodes", [])
    categories = menu.get("categories", [])
    items_list = menu.get("items", [])

    cursor   = menu.get("cursor", 0)
    sel_node = nodes[cursor] if nodes and cursor < len(nodes) else {}

    debug = {
        "rev":            menu.get("rev", 0),
        "path":           menu.get("path", []),
        "title":          menu.get("title", ""),
        "cursor":         cursor,
        "can_back":       menu.get("can_back", False),
        "selected_label": sel_node.get("label", "") if isinstance(sel_node, dict) else str(sel_node),
        "selected_type":  sel_node.get("type", "") if isinstance(sel_node, dict) else "",
        "node_count":     len(nodes),
        "core_ready":     os.path.exists(READY_FILE),
        "status_age":     file_age(STATUS_FILE),
        "menu_age":       file_age(MENU_FILE),
    }

    return {
        "version":         get_version(),
        "ip":              get_ip(),
        "status":          status,
        "menu":            menu,
        "progress":        progress,
        "rtlsdr":          rtlsdr,
        "rtlsdr_age":      file_age(RTLSDR_FILE),
        "rtlsdr_exists":   os.path.exists(RTLSDR_FILE),
        "avrcp":           avrcp,
        "avrcp_age":       file_age(AVRCP_FILE),
        "avrcp_exists":    os.path.exists(AVRCP_FILE),
        "audio_debug":     get_audio_debug(),
        "source_state":    get_source_state_debug(),
        "dab_scan_debug":  get_dab_scan_debug(),
        "spectrum_debug":  get_spectrum_debug(),
        "known_bt_devices": bt_known,
        "bt_agent":        bt_agent,
        "processes":       status.get("processes", []),  # für renderProcesses
        "list_data":       list_data,
        "list_active":     list_data.get("active", False),
        "list_title":      list_data.get("title", ""),
        "list_items":      list_data.get("items", []),
        "list_selected":   list_data.get("selected", 0),
        "nodes":           nodes,
        "categories":      categories,
        "items":           items_list,
        "path":            menu.get("path", []),
        "cursor":          cursor,
        "rev":             menu.get("rev", 0),
        "can_back":        menu.get("can_back", False),
        "debug":           debug,
        "status_age":      file_age(STATUS_FILE),
        "menu_age":        file_age(MENU_FILE),
        "progress_age":    file_age(PROGRESS_FILE),
        "list_age":        file_age(LIST_FILE),
        "status_exists":   os.path.exists(STATUS_FILE),
        "menu_exists":     os.path.exists(MENU_FILE),
        "progress_exists": os.path.exists(PROGRESS_FILE),
        "list_exists":     os.path.exists(LIST_FILE),
        "log_exists":      os.path.exists(LOG_FILE),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    vm = build_view_model()
    return render_template("index.html", vm=vm)


@app.route("/api/state")
def api_state():
    return jsonify(build_view_model())


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
            "last_source": settings.get("last_source", "-"),
            "dab_scan_wait_lock": settings.get("dab_scan_wait_lock", "-"),
            "dab_scan_http_timeout": settings.get("dab_scan_http_timeout", "-"),
            "dab_scan_port": settings.get("dab_scan_port", "-"),
            "dab_scan_channels": settings.get("dab_scan_channels", []),
        },
        "version": get_version(),
        "source_state": get_source_state_debug(),
        "dab_scan_debug": get_dab_scan_debug(),
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

    prefixes = (
        "cat:", "reload_stations:",
        "scan_up:", "scan_down:", "scan_next:", "scan_prev:",
        "scan_jump:", "scan_step:", "scan_setfreq:", "scan_inputfreq:",
        "dab_scan_channels:", "bt_connect:", "wifi_connect:", "bt_repair:",
        "fm_gain:", "dab_gain:", "ppm:", "squelch:", "scanner_gain:"
    )
    if not (cmd in ALLOWED_COMMANDS or any(cmd.startswith(p) for p in prefixes)):
        return jsonify({"ok": False, "error": f"Befehl nicht erlaubt: {cmd}"}), 400

    try:
        write_cmd(cmd)
        return jsonify({"ok": True, "cmd": cmd})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/bt/known")
def api_bt_known():
    data = read_json(KNOWN_BT_FILE, {"devices": []})
    devs = data.get("devices", []) if isinstance(data, dict) else []
    try:
        devs = sorted(devs, key=lambda d: (
            0 if d.get("connected") else 1,
            0 if d.get("paired") else 1,
            0 if d.get("known") else 1,
            (d.get("name") or "").lower(),
            d.get("mac") or ""
        ))
    except Exception:
        pass
    return jsonify({"ok": True, "data": {"devices": devs}})


@app.route("/api/bt/connect_known", methods=["POST"])
def api_bt_connect_known():
    data = request.get_json(silent=True) or {}
    mac = (data.get("mac") or "").strip()
    if not mac:
        return jsonify({"ok": False, "error": "mac fehlt"}), 400
    write_cmd("bt_connect:" + mac)
    return jsonify({"ok": True, "cmd": "bt_connect:" + mac})


@app.route("/api/bt/agent")
def api_bt_agent():
    return jsonify({"ok": True, "data": read_json(BT_AGENT_FILE, {})})


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
    return jsonify({
        "ok": bool(data),
        "data": data,
        "exists": os.path.exists(RTLSDR_FILE),
        "age": file_age(RTLSDR_FILE)
    })


@app.route("/api/rtlsdr/refresh")
def api_rtlsdr_refresh():
    import subprocess as _sp, sys as _sys
    try:
        # v0.9.26: BASE_DIR-relativer Pfad statt Hardcode
        _rtl_py = str(BASE_DIR / "modules" / "rtlsdr.py")
        _r = _sp.run([_sys.executable, _rtl_py, "--json"],
                     timeout=10, capture_output=True)
    except Exception as _e:
        return jsonify({"ok": False, "error": str(_e),
                        "data": read_json(RTLSDR_FILE, {}),
                        "file_exists": os.path.exists(RTLSDR_FILE)})
    data = read_json(RTLSDR_FILE, {})
    return jsonify({"ok": True, "data": data,
                    "file_exists": os.path.exists(RTLSDR_FILE)})


@app.route("/api/rtlsdr/reset", methods=["POST"])
def api_rtlsdr_reset():
    try:
        write_cmd("rtlsdr_reset")
        return jsonify({"ok": True, "msg": "RTL-SDR Reset gestartet — dauert ~5s"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/dab/diag")
def api_dab_diag():
    import subprocess as _sp
    channel = request.args.get("channel", "")
    port    = request.args.get("port", "7979")

    if not channel:
        return jsonify({"ok": False, "error": "channel Parameter fehlt (z.B. ?channel=11D)"})

    try:
        port = int(port)
        if not (1024 <= port <= 65535):
            return jsonify({"ok": False, "error": "Port muss zwischen 1024 und 65535 sein"})
    except Exception:
        return jsonify({"ok": False, "error": "Ungültiger Port"})

    try:
        with open("/tmp/pidrive_cmd", "w") as _f:
            _f.write("radio_stop\n")
    except Exception:
        pass

    time.sleep(1.5)

    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
    time.sleep(0.5)

    cmd = f"welle-cli -c {channel} -C 1 -w {port} 2>&1 &"
    try:
        _sp.Popen(cmd, shell=True, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    return jsonify({
        "ok": True,
        "channel": channel,
        "port": port,
        "url": f"http://PI_IP:{port}/",
        "note": f"welle-cli Webserver gestartet auf Port {port} — Browser: http://[PI-IP]:{port}/",
    })


@app.route("/api/dab/diag/stop")
def api_dab_diag_stop():
    import subprocess as _sp
    _sp.run("pkill -f 'welle-cli.*-w' 2>/dev/null", shell=True, capture_output=True)
    return jsonify({"ok": True, "note": "welle-cli Webserver gestoppt"})


@app.route("/api/dab/scan/settings", methods=["GET", "POST"])
def api_dab_scan_settings():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from settings import load_settings as _ls, save_settings as _ss
        s = _ls()

        if request.method == "GET":
            return jsonify({
                "ok": True,
                "data": {
                    "dab_scan_wait_lock": s.get("dab_scan_wait_lock", 20),
                    "dab_scan_http_timeout": s.get("dab_scan_http_timeout", 4),
                    "dab_scan_port": s.get("dab_scan_port", 7981),
                    "dab_scan_channels": s.get("dab_scan_channels", []),
                }
            })

        data = request.get_json(silent=True) or {}
        s["dab_scan_wait_lock"] = int(data.get("dab_scan_wait_lock", s.get("dab_scan_wait_lock", 20)))
        s["dab_scan_http_timeout"] = int(data.get("dab_scan_http_timeout", s.get("dab_scan_http_timeout", 4)))
        s["dab_scan_port"] = int(data.get("dab_scan_port", s.get("dab_scan_port", 7981)))
        chans = data.get("dab_scan_channels", s.get("dab_scan_channels", []))
        if isinstance(chans, str):
            chans = [x.strip().upper() for x in chans.split(",") if x.strip()]
        s["dab_scan_channels"] = chans
        _ss(s)
        return jsonify({"ok": True, "saved": True, "data": s})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/audio")
def api_audio():
    return jsonify({
        "ok": True,
        "data": get_audio_debug(),
    })


@app.route("/api/gain")
def api_gain():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from settings import load_settings as _ls
        s = _ls()
        return jsonify({
            "ok": True,
            "fm_gain": s.get("fm_gain", -1),
            "dab_gain": s.get("dab_gain", -1),
            "ppm_correction": s.get("ppm_correction", 0),
            "scanner_squelch": s.get("scanner_squelch", 25),
            "scanner_gain": s.get("scanner_gain", -1),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/rtlsdr/calibrate")
def api_rtlsdr_calibrate():
    import re as _re
    result = safe_run("timeout 32s rtl_test -p 2>&1")
    stdout = result.get("stdout", "") or ""

    ppm = None
    method = "nicht erkannt"
    lines = stdout.splitlines()

    cum_ppms = []
    for ln in lines:
        m = _re.search(r'cumulative PPM[: ]+([-+]?[0-9]+)', ln, _re.I)
        if m:
            try:
                cum_ppms.append(int(m.group(1)))
            except Exception:
                pass

    if cum_ppms:
        ppm = cum_ppms[-1]
        method = f"cumulative PPM aus rtl_test ({len(cum_ppms)} Messungen, letzter Wert)"

    if ppm is None:
        cur_ppms = []
        for ln in lines:
            m = _re.search(r'current PPM[: ]+([-+]?[0-9]+)', ln, _re.I)
            if m:
                try:
                    cur_ppms.append(int(m.group(1)))
                except Exception:
                    pass
        if cur_ppms:
            cur_ppms.sort()
            ppm = cur_ppms[len(cur_ppms)//2]
            method = f"current PPM Median aus {len(cur_ppms)} Werten"

    if ppm is None:
        for ln in lines:
            m = _re.search(r'real sample rate[: ]+([\d.]+)', ln, _re.I)
            if m:
                try:
                    measured = float(m.group(1))
                    nominal = 2048000.0
                    ppm_raw = (measured - nominal) / nominal * 1e6
                    ppm = round(ppm_raw)
                    method = f"Samplerate-Berechnung ({measured:.0f} S/s)"
                except Exception:
                    pass
                break

    hints = []
    if ppm is None:
        hints.append("Kein PPM-Wert erkannt — mögliche Ursachen:")
        hints.append("• RTL-SDR Stick noch nicht freigegeben (kurz warten, erneut versuchen)")
        hints.append("• Kalibrierung läuft nur wenn kein FM/DAB/Scanner aktiv ist")
        hints.append("• Timeout zu kurz — 30s reicht normalerweise")
        hints.append("Manuelle Alternative: PPM-Wert schrittweise ±5 testen beim FM-Hören")
    else:
        hints.append(f"Methode: {method}")
        if abs(ppm) > 100:
            hints.append("⚠ Wert > 100 ppm — sehr hoch, eventuell Stick-Problem")
        elif abs(ppm) > 50:
            hints.append("Hinweis: Typischer Bereich für RTL2838 ist ±20-60 ppm")
        hints.append("Nach Übernehmen → FM neu starten um Wert zu aktivieren")

    return jsonify({
        "ok": True,
        "stdout": stdout[-1000:],
        "suggested_ppm": ppm,
        "method": method,
        "hints": hints,
    })


@app.route("/api/volume")
def api_volume():
    """
    PulseAudio-Lautstärke (v0.9.15).
    Parst aus pactl list sinks statt get-sink-volume, da letzteres in --system Mode fehlschlägt.
    """
    try:
        import re as _re
        import sys as _sys
        _b = str(BASE_DIR)
        if _b not in _sys.path:
            _sys.path.insert(0, _b)

        # v0.9.26: Sink-Hierarchie:
        # 1. aktiver Sink-Input (was gerade läuft)
        # 2. BT A2DP Sink wenn verbunden
        # 3. alsa_output.1.* (Klinke Card 1)
        # 4. Nicht-HDMI ALSA
        sinks_out = (safe_run(PA_ENV + " pactl list sinks short 2>/dev/null").get("stdout","") or "")
        sink = ""
        source_label = ""

        # 1. Welcher Sink hat gerade einen Input?
        sin_out = (safe_run(PA_ENV + " pactl list sink-inputs short 2>/dev/null").get("stdout","") or "")
        active_sink_ids = set()
        for ln in sin_out.splitlines():
            p = ln.split()
            if len(p) >= 2 and p[0].isdigit():
                active_sink_ids.add(p[1])

        # Sink-ID → Name mappen
        sink_id_to_name = {}
        for ln in sinks_out.splitlines():
            p = ln.split()
            if len(p) >= 2:
                sink_id_to_name[p[0]] = p[1]

        for sid in active_sink_ids:
            sname = sink_id_to_name.get(sid, "")
            if sname:
                sink = sname
                source_label = "active_input"
                break

        if not sink:
            # 2. BT A2DP
            for ln in sinks_out.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and "bluez_sink" in parts[1] and "a2dp_sink" in parts[1]:
                    sink = parts[1]; source_label = "bt_sink"; break
        if not sink:
            # 3. Klinke Card 1
            for ln in sinks_out.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and _re.search(r"alsa_output\.1\.", parts[1]):
                    sink = parts[1]; source_label = "alsa_card1"; break
        if not sink:
            # 4. Nicht-HDMI ALSA
            for ln in sinks_out.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and "alsa_output" in parts[1] and not _sink_is_hdmi(parts[1]):
                    sink = parts[1]; source_label = "alsa_fallback"; break

        # Volume aus pactl list sinks (long) parsen — zuverlässig in --system Mode
        vol = ""
        if sink:
            full_out = (safe_run(PA_ENV + " pactl list sinks 2>/dev/null").get("stdout","") or "")
            in_target = False
            for ln in full_out.splitlines():
                if f"Name: {sink}" in ln:
                    in_target = True
                if in_target:
                    if ln.strip().startswith("Volume:") and "%" in ln:
                        m = _re.search(r"(\d+)%", ln)
                        if m:
                            vol = m.group(1) + "%"
                            break
                    # Nächster Sink-Block → Ende
                    if in_target and ln.startswith("    Name:") and sink not in ln:
                        break

        return jsonify({"ok": True, "volume": vol or "–",
                        "sink": sink or "", "source": source_label})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "volume": "–"})


@app.route("/api/dab/scan/last")
def api_dab_scan_last():
    return jsonify({
        "ok": True,
        "data": get_dab_scan_debug(),
        "age": file_age("/tmp/pidrive_dab_scan_debug.json"),
    })


@app.route("/api/spectrum/last")
def api_spectrum_last():
    return jsonify({
        "ok": True,
        "data": get_spectrum_debug(),
        "age": file_age("/tmp/pidrive_spectrum.json"),
        "exists": os.path.exists("/tmp/pidrive_spectrum.json"),
    })


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
    if name not in ("pidrive_core", "pidrive_display", "pidrive_web", "pidrive_avrcp"):
        return jsonify({"ok": False, "error": "Ungültiger Service"}), 400
    return jsonify(safe_run(f"systemctl status {name} --no-pager"))


@app.route("/api/debug/summary")
def api_debug_summary():
    return jsonify({
        "ok": True,
        "version": get_version(),
        "source_state": get_source_state_debug(),
        "dab_scan": get_dab_scan_debug(),
        "spectrum": get_spectrum_debug(),
        "audio": get_audio_debug(),
        "known_bt_devices": read_json(KNOWN_BT_FILE, {"devices": []}),
        "bt_agent": read_json(BT_AGENT_FILE, {}),
    })


@app.route("/api/system/resources")
def api_system_resources():
    """v0.9.28: Systemressourcen für WebUI Debug-Tab."""
    import subprocess as _sp2
    data = {"ok": True}
    try:
        df = _sp2.run("df -h / 2>/dev/null", shell=True, capture_output=True, text=True).stdout
        for ln in df.splitlines():
            p = ln.split()
            if len(p) >= 5 and p[0] != "Filesystem":
                pct_int = int(p[4].rstrip('%')) if p[4].rstrip('%').isdigit() else 0
                data.update({"disk_used": p[2], "disk_avail": p[3],
                             "disk_pct": p[4], "disk_warn": pct_int > 80})
    except Exception: pass
    try:
        fr = _sp2.run("free -m 2>/dev/null", shell=True, capture_output=True, text=True).stdout
        for ln in fr.splitlines():
            if ln.startswith("Mem:"):
                p = ln.split()
                data.update({"ram_total_mb": p[1], "ram_used_mb": p[2], "ram_free_mb": p[3]})
    except Exception: pass
    try:
        data["uptime"] = _sp2.run("uptime -p 2>/dev/null", shell=True,
                                   capture_output=True, text=True).stdout.strip()
    except Exception: pass
    logs = {}
    for lf in ["pidrive.log", "core.log", "display.log"]:
        lp = f"/var/log/pidrive/{lf}"
        if os.path.exists(lp):
            logs[lf] = {"size_kb": round(os.path.getsize(lp) / 1024, 1)}
    data["logs"] = logs
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)