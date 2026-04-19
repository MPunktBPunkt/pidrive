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
    "rtlsdr_reset",
    "bt_backup", "bt_restore",
    "rtlsdr_reset",
    "bt_backup", "bt_restore",
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
                "fm_gain:", "dab_gain:", "ppm:", "squelch:")
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


@app.route("/api/rtlsdr/reset", methods=["POST"])
def api_rtlsdr_reset():
    """RTL-SDR USB-Reset via Core-Trigger (v0.8.16). Kein Reboot nötig."""
    try:
        write_cmd("rtlsdr_reset")
        return jsonify({"ok": True, "msg": "RTL-SDR Reset gestartet — dauert ~5s"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



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
    """Gibt aktuelle Gain + PPM + Squelch Einstellungen zurück (v0.8.18)."""
    try:
        import sys
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from settings import load_settings as _ls
        s = _ls()
        return jsonify({
            "ok": True,
            "fm_gain":        s.get("fm_gain",        -1),
            "dab_gain":       s.get("dab_gain",       -1),
            "ppm_correction": s.get("ppm_correction",  0),
            "scanner_squelch":s.get("scanner_squelch",25),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/rtlsdr/calibrate")
def api_rtlsdr_calibrate():
    """
    PPM-Kalibrierung via rtl_test -p (v0.8.25).

    rtl_test -p gibt aus:
      real sample rate: 2047943 current PPM: -28 cumulative PPM: -28

    Methode 1: "cumulative PPM: N" direkt aus rtl_test (zuverlässigste Methode)
    Methode 2: Samplerate-Berechnung als Fallback
    """
    import re as _re
    result = safe_run("timeout 32s rtl_test -p 2>&1")
    stdout = result.get("stdout", "") or ""

    ppm = None
    method = "nicht erkannt"
    lines = stdout.splitlines()

    # Methode 1 (beste): "cumulative PPM: N" — rtl_test gibt dies nach ~30s aus
    # Zeile sieht aus: "real sample rate: 2047943 current PPM: -28 cumulative PPM: -28"
    cum_ppms = []
    for ln in lines:
        m = _re.search(r'cumulative PPM[: ]+([-+]?[0-9]+)', ln, _re.I)
        if m:
            try:
                cum_ppms.append(int(m.group(1)))
            except Exception:
                pass

    if cum_ppms:
        # Letzten kumulativen PPM-Wert nehmen (stabilstes Ergebnis)
        ppm = cum_ppms[-1]
        method = f"cumulative PPM aus rtl_test ({len(cum_ppms)} Messungen, letzter Wert)"

    # Methode 2: "current PPM: N" wenn kein kumulativer Wert
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
            # Median der aktuellen PPM-Werte (robuster als letzter Wert)
            cur_ppms.sort()
            ppm = cur_ppms[len(cur_ppms)//2]
            method = f"current PPM Median aus {len(cur_ppms)} Werten"

    # Methode 3: Samplerate-Berechnung
    if ppm is None:
        for ln in lines:
            m = _re.search(r'real sample rate[: ]+([\d.]+)', ln, _re.I)
            if m:
                try:
                    measured = float(m.group(1))
                    nominal  = 2048000.0
                    ppm_raw  = (measured - nominal) / nominal * 1e6
                    ppm      = round(ppm_raw)
                    method   = f"Samplerate-Berechnung ({measured:.0f} S/s)"
                except Exception:
                    pass
                break

    # Hinweise
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
        "ok":            True,
        "stdout":        stdout[-1000:],
        "suggested_ppm": ppm,
        "method":        method,
        "hints":         hints,
    })


@app.route("/api/volume")
def api_volume():
    """Gibt aktuelle PulseAudio-Lautstärke zurück (v0.8.16: Default + BT-Sink)."""
    try:
        PA = "PULSE_SERVER=unix:/var/run/pulse/native "
        # Default Sink Volume
        r = safe_run(PA + "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null")
        txt = r.get("stdout", "") or ""
        vol = ""
        for part in txt.split():
            if part.endswith("%"):
                vol = part
                break
        # Fallback: pactl list sinks für aktuellen Sink
        if not vol:
            sinks_r = safe_run(PA + "pactl list sinks 2>/dev/null")
            sinks_txt = sinks_r.get("stdout", "") or ""
            in_default = False
            for ln in sinks_txt.splitlines():
                if "* index:" in ln or "State: RUNNING" in ln:
                    in_default = True
                if in_default and "Volume:" in ln and "%" in ln:
                    for part in ln.split():
                        if part.endswith("%"):
                            vol = part
                            break
                    if vol:
                        break
        return jsonify({"ok": True, "volume_raw": txt.strip(), "volume": vol or "–"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)