#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes_audio.py — Audio API Endpunkte  v0.10.6
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

audio_bp = Blueprint("audio_bp", __name__)

# Routen: app.route → audio_bp.route
@audio_bp.route("/api/audio")
def api_audio():
    return jsonify({
        "ok": True,
        "data": get_audio_debug(),
    })


@audio_bp.route("/api/gain")
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


@audio_bp.route("/api/volume")
def api_volume():
    return jsonify(get_volume_data())


