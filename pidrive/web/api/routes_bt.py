#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes_bt.py — Bluetooth API Endpunkte  v0.10.6
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

bt_bp = Blueprint("bt_bp", __name__)

# Routen: app.route → bt_bp.route
@bt_bp.route("/api/bt/known")
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


@bt_bp.route("/api/bt/connect_known", methods=["POST"])
def api_bt_connect_known():
    data = request.get_json(silent=True) or {}
    mac = (data.get("mac") or "").strip()
    if not mac:
        return jsonify({"ok": False, "error": "mac fehlt"}), 400
    write_cmd("bt_connect:" + mac)
    return jsonify({"ok": True, "cmd": "bt_connect:" + mac})


@bt_bp.route("/api/bt/agent")
def api_bt_agent():
    return jsonify({"ok": True, "data": read_json(BT_AGENT_FILE, {})})


@bt_bp.route("/api/bt/watcher")
def api_bt_watcher():
    wf = "/tmp/pidrive_bt_watcher.json"
    if not os.path.exists(wf):
        return jsonify({"ok": True, "data": None, "exists": False})
    try:
        with open(wf) as _f:
            return jsonify({
                "ok": True,
                "data": json.load(_f),
                "age": file_age(wf),
                "exists": True
            })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


