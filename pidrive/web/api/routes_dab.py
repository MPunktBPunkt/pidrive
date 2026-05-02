#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes_dab.py — DAB+ API Endpunkte  v0.10.6
Blueprint ausgelagert aus webui.py
"""

import os
import sys
import time
import json
import subprocess
BASE_DIR_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR_API)

from flask import Blueprint, jsonify, request
from webui_shared import *  # noqa: F401,F403

dab_bp = Blueprint("dab_bp", __name__)

# Routen: app.route → dab_bp.route
@dab_bp.route("/api/dab/diag")
def api_dab_diag():
    """
    v0.10.4: welle-cli Webinterface starten (Spektrum + Antenne + Sender).
    ?channel=11D  Kanal (Pflicht)
    ?port=7979    HTTP-Port für welle-cli Webinterface
    """
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

    # Laufendes Radio stoppen + welle-cli beenden
    write_cmd("radio_stop")
    time.sleep(1.5)
    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
    time.sleep(0.5)

    # welle-cli mit Web-Interface starten
    # -w PORT = HTTP-Server für Spektrum + Service-Übersicht + Statistiken
    cmd = (f"welle-cli -c {channel} -C 1 -w {port} "
           f"2>/tmp/pidrive_dab_webui.log &")
    try:
        _sp.Popen(cmd, shell=True, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    ip = get_ip()
    url = f"http://{ip}:{port}/"
    return jsonify({
        "ok":      True,
        "channel": channel,
        "port":    port,
        "ip":      ip,
        "url":     url,
        "note":    f"welle-cli Webinterface auf Port {port} — im Browser öffnen: {url}",
        "log":     "/tmp/pidrive_dab_webui.log",
    })


@dab_bp.route("/api/dab/diag/stop")
def api_dab_diag_stop():
    import subprocess as _sp
    _sp.run("pkill -f 'welle-cli.*-w' 2>/dev/null", shell=True, capture_output=True)
    return jsonify({"ok": True, "note": "welle-cli Webserver gestoppt"})


@dab_bp.route("/api/dab/diag/status")
def api_dab_diag_status():
    """Prüft ob welle-cli Webinterface läuft."""
    import subprocess as _sp
    r = _sp.run("pgrep -a welle-cli 2>/dev/null", shell=True,
                capture_output=True, text=True, timeout=3)
    lines = [l.strip() for l in r.stdout.splitlines() if "-w" in l]
    running = bool(lines)
    port = None
    if running:
        import re as _re
        m = _re.search(r"-w +(\d+)", lines[0])
        if m: port = int(m.group(1))
    ip = get_ip()
    return jsonify({
        "ok": True,
        "running": running,
        "port": port,
        "url": f"http://{ip}:{port}/" if (running and port) else None,
        "ip": ip,
        "process": lines[0] if lines else None,
    })


@dab_bp.route("/api/dab/scan/settings", methods=["GET", "POST"])
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


@dab_bp.route("/api/dab/scan/last")
def api_dab_scan_last():
    return jsonify({
        "ok": True,
        "data": get_dab_scan_debug(),
        "age": file_age("/tmp/pidrive_dab_scan_debug.json"),
    })


@dab_bp.route("/api/dab/status")
def api_dab_status():
    data = get_dab_status_debug()
    return jsonify({
        "ok": True,
        "data": data if data else None,
        "age": file_age(DAB_DEBUG_FILE),
        "exists": os.path.exists(DAB_DEBUG_FILE)
    })



