"""web/shared/files.py — JSON, IPC, Datei-Hilfsfunktionen"""
import json
import os
import time

from web.shared.system import CMD_FILE

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


# v0.10.53: IP-Cache (30s TTL) — verhindert Socket-Open bei jedem Request
_ip_cache: tuple = ("", 0.0)
