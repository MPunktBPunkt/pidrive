"""web/shared/files.py — JSON, IPC, Datei-Hilfsfunktionen"""
import json
import os
import time
from web.shared.constants import (
    CMD_FILE
)
from web.shared.errors import warn_once


def read_json(path, default=None):
    """Liest JSON; bei Fehler/fehlender Datei default (stumm für Aufrufer)."""
    data, _meta = read_json_meta(path, default=default)
    return data


def read_json_meta(path, default=None, stale_after_s=None):
    """Liest JSON und liefert (data, meta).

    meta:
      ok      — True wenn Datei gelesen und geparst
      reason  — None | "missing" | "corrupt" | "stale"
      age     — Sekunden seit mtime, oder None
    """
    if default is None:
        default = {}
    age = file_age(path)
    if not os.path.exists(path):
        return default, {"ok": False, "reason": "missing", "age": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        warn_once(f"files.read_json:{path}", f"web.shared.files.read_json({path}): {e}")
        return default, {"ok": False, "reason": "corrupt", "age": age}
    reason = None
    if stale_after_s is not None and age is not None and age > stale_after_s:
        reason = "stale"
    return data, {"ok": True, "reason": reason, "age": age}


def write_cmd(cmd):
    """Queue-kompatibel: append statt overwrite."""
    with open(CMD_FILE, "a", encoding="utf-8") as f:
        f.write(cmd.strip() + "\n")

def file_age(path):
    try:
        return round(time.time() - os.path.getmtime(path), 1)
    except Exception:
        return None


# v0.10.55: IP-Cache (30s TTL) — verhindert Socket-Open bei jedem Request
_ip_cache: tuple = ("", 0.0)
