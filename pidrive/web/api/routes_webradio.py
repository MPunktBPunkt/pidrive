#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes_webradio.py — Webradio API Endpunkte  v0.10.6
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

webradio_bp = Blueprint("webradio_bp", __name__)

# Routen: app.route → webradio_bp.route
@webradio_bp.route("/api/webradio/stations")
def api_webradio_stations():
    data = _load_stations_file()
    return jsonify({"ok": True, "stations": data.get("stations", [])})


@webradio_bp.route("/api/webradio/add", methods=["POST"])
def api_webradio_add():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    url  = (body.get("url")  or "").strip()
    genre = (body.get("genre") or "").strip()
    if not name or not url:
        return jsonify({"ok": False, "error": "name und url sind Pflichtfelder"}), 400

    data = _load_stations_file()
    stations = data.get("stations", [])

    # ID aus Name ableiten (URL-safe)
    import re as _re
    base_id = "web_" + _re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    sid = base_id
    existing_ids = {s.get("id") for s in stations}
    counter = 2
    while sid in existing_ids:
        sid = f"{base_id}_{counter}"
        counter += 1

    stations.append({
        "id": sid,
        "name": name,
        "url": url,
        "genre": genre or "Sonstige",
        "favorite": False,
        "enabled": True,
    })
    data["stations"] = stations
    try:
        _save_stations_file(data)
        return jsonify({"ok": True, "id": sid, "station_count": len(stations)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@webradio_bp.route("/api/webradio/delete", methods=["POST"])
def api_webradio_delete():
    body = request.get_json(silent=True) or {}
    sid = (body.get("id") or "").strip()
    if not sid:
        return jsonify({"ok": False, "error": "id fehlt"}), 400

    data = _load_stations_file()
    before = len(data.get("stations", []))
    data["stations"] = [s for s in data.get("stations", []) if s.get("id") != sid]
    after = len(data["stations"])
    if before == after:
        return jsonify({"ok": False, "error": f"Station nicht gefunden: {sid}"}), 404
    try:
        _save_stations_file(data)
        return jsonify({"ok": True, "removed": sid, "station_count": after})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@webradio_bp.route("/api/webradio/toggle", methods=["POST"])
def api_webradio_toggle():
    body = request.get_json(silent=True) or {}
    sid = (body.get("id") or "").strip()
    if not sid:
        return jsonify({"ok": False, "error": "id fehlt"}), 400

    data = _load_stations_file()
    for s in data.get("stations", []):
        if s.get("id") == sid:
            s["enabled"] = not s.get("enabled", True)
            try:
                _save_stations_file(data)
                return jsonify({"ok": True, "id": sid, "enabled": s["enabled"]})
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": False, "error": f"Station nicht gefunden: {sid}"}), 404


