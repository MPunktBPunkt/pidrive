#!/usr/bin/env python3
"""routes_music.py — Medienbibliothek Web-API  v0.11.127"""

import os
import sys

BASE_DIR_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(BASE_DIR_API))

from flask import Blueprint, jsonify, request

from modules import music_library as lib
from web.shared import write_cmd

music_bp = Blueprint("music_bp", __name__)

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB pro Datei


def _settings():
    try:
        from settings import load_settings
        return load_settings()
    except Exception:
        return {}


@music_bp.route("/api/music/info")
def api_music_info():
    settings = _settings()
    root = lib.get_music_root(settings)
    listing = lib.list_dir("", settings)
    return jsonify({
        "ok": True,
        "root": root,
        "total_bytes": listing.get("total_bytes", 0),
        "formats": lib.AUDIO_EXT_LIST,
    })


@music_bp.route("/api/music/list")
def api_music_list():
    rel = request.args.get("path", "")
    try:
        data = lib.list_dir(rel, _settings())
        return jsonify({"ok": True, **data})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "Pfad nicht gefunden"}), 404
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@music_bp.route("/api/music/mkdir", methods=["POST"])
def api_music_mkdir():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    rel = (body.get("path") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name fehlt"}), 400
    try:
        new_rel = lib.mkdir(rel, name, _settings())
        return jsonify({"ok": True, "path": new_rel})
    except FileExistsError:
        return jsonify({"ok": False, "error": "Ordner existiert bereits"}), 409
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@music_bp.route("/api/music/upload", methods=["POST"])
def api_music_upload():
    rel_dir = (request.form.get("path") or "").strip()
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Keine Datei (file)"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Leerer Upload"}), 400
    data = f.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({"ok": False, "error": f"Max. {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"}), 413
    try:
        saved = lib.save_upload(rel_dir, f.filename, data, _settings())
        return jsonify({"ok": True, "path": saved, "size": len(data)})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@music_bp.route("/api/music/delete", methods=["POST"])
def api_music_delete():
    body = request.get_json(silent=True) or {}
    rel = (body.get("path") or "").strip()
    if not rel:
        return jsonify({"ok": False, "error": "path fehlt"}), 400
    try:
        lib.delete_path(rel, _settings())
        return jsonify({"ok": True, "deleted": rel})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "Nicht gefunden"}), 404


@music_bp.route("/api/music/rename", methods=["POST"])
def api_music_rename():
    body = request.get_json(silent=True) or {}
    rel = (body.get("path") or "").strip()
    new_name = (body.get("new_name") or "").strip()
    if not rel or not new_name:
        return jsonify({"ok": False, "error": "path und new_name nötig"}), 400
    try:
        new_rel = lib.rename_entry(rel, new_name, _settings())
        return jsonify({"ok": True, "path": new_rel})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@music_bp.route("/api/music/tags")
def api_music_tags_get():
    rel = request.args.get("path", "").strip()
    if not rel:
        return jsonify({"ok": False, "error": "path fehlt"}), 400
    try:
        tags = lib.read_tags(rel, _settings())
        return jsonify({"ok": True, "tags": tags})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "Datei nicht gefunden"}), 404


@music_bp.route("/api/music/tags", methods=["PUT", "POST"])
def api_music_tags_put():
    body = request.get_json(silent=True) or {}
    rel = (body.get("path") or "").strip()
    if not rel:
        return jsonify({"ok": False, "error": "path fehlt"}), 400
    updates = {k: body.get(k, "") for k in (
        "title", "artist", "album", "genre", "tracknumber", "date"
    ) if k in body}
    try:
        tags = lib.write_tags(rel, updates, _settings())
        return jsonify({"ok": True, "tags": tags})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@music_bp.route("/api/music/play", methods=["POST"])
def api_music_play():
    body = request.get_json(silent=True) or {}
    rel = (body.get("path") or "").strip()
    shuffle = bool(body.get("shuffle"))
    if not rel:
        return jsonify({"ok": False, "error": "path fehlt"}), 400
    try:
        abs_path = lib.resolve_in_library(rel, _settings())
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    cmd = f"local_play:{abs_path}" + ("|shuffle" if shuffle else "")
    write_cmd(cmd)
    return jsonify({"ok": True, "cmd": cmd})
