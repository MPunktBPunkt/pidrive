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

from flask import Blueprint, jsonify, request, Response, stream_with_context
from web.shared import *  # noqa: F401,F403

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


@audio_bp.route("/api/audio/listen/status")
def api_audio_listen_status():
    """Monitor-Source auflösen — ohne Stream zu starten."""
    try:
        from web.shared.audio import resolve_listen_monitor_source
        info = resolve_listen_monitor_source()
        info["ffmpeg"] = bool(subprocess.call(
            ["which", "ffmpeg"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ) == 0)
        return jsonify(info)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@audio_bp.route("/api/audio/listen")
def api_audio_listen():
    """
    Live-MP3 vom Pulse/PipeWire-Monitor der aktuellen Default-Senke.
    Ändert kein Audio-Routing — nur Mithören im Browser (WLAN/Dev).
    """
    try:
        from web.shared.audio import (
            resolve_listen_monitor_source,
            build_listen_ffmpeg_cmd,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    info = resolve_listen_monitor_source()
    if not info.get("ok") or not info.get("source"):
        return jsonify({
            "ok": False,
            "error": info.get("error") or "kein Monitor",
            "hint": "Wiedergabe über Klinke/BT/HDMI (Pulse) starten — "
                    "usb_gadget allein liefert oft keinen lokalen Monitor.",
        }), 503

    if subprocess.call(
        ["which", "ffmpeg"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) != 0:
        return jsonify({"ok": False, "error": "ffmpeg fehlt"}), 500

    env = dict(os.environ)
    env["PULSE_SERVER"] = "unix:/var/run/pulse/native"
    monitor_src = info["source"]

    def generate():
        # Bei Pulse/PipeWire-Neustart ffmpeg neu starten (Monitor bleibt nutzbar)
        backoff = 0.4
        while True:
            proc = None
            try:
                # Source ggf. neu auflösen (Default-Sink kann wechseln)
                try:
                    from web.shared.audio import resolve_listen_monitor_source
                    fresh = resolve_listen_monitor_source()
                    src = fresh.get("source") if fresh.get("ok") else monitor_src
                except Exception:
                    src = monitor_src
                if not src:
                    time.sleep(min(backoff, 3.0))
                    backoff = min(backoff * 1.5, 3.0)
                    continue
                proc = subprocess.Popen(
                    build_listen_ffmpeg_cmd(src),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    bufsize=0,
                )
                backoff = 0.4
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    yield chunk
            except GeneratorExit:
                raise
            except Exception:
                pass
            finally:
                if proc is not None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=1.5)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
            time.sleep(min(backoff, 3.0))
            backoff = min(backoff * 1.5, 3.0)

    headers = {
        "Content-Type": "audio/mpeg",
        "Cache-Control": "no-store, no-cache",
        "X-Accel-Buffering": "no",
        "X-PiDrive-Monitor": info.get("source") or "",
    }
    return Response(
        stream_with_context(generate()),
        headers=headers,
        direct_passthrough=True,
    )

