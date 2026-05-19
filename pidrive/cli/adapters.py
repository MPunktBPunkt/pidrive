#!/usr/bin/env python3
"""cli_adapters.py — PiDrive CLI: IPC- und HTTP-Adapter"""
import json
import os
import urllib.request
import urllib.error
import time

STATUS_FILE       = "/tmp/pidrive_status.json"
MENU_FILE         = "/tmp/pidrive_menu.json"
SOURCE_STATE_FILE = "/tmp/pidrive_source_state.json"
PROGRESS_FILE     = "/tmp/pidrive_progress.json"
CMD_FILE          = "/tmp/pidrive_cmd"
READY_FILE        = "/tmp/pidrive_ready"
BT_KNOWN_FILE     = "/tmp/pidrive_bt_known_devices.json"
BT_DISC_FILE      = "/tmp/pidrive_bt_devices.json"
DAB_DEBUG_FILE    = "/tmp/pidrive_dab_play_debug.json"


class IPCAdapter:
    """Liest IPC-JSON-Dateien und schreibt in CMD_FILE."""

    def read_json(self, path: str, default=None):
        if default is None:
            default = {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def write_cmd(self, cmd: str) -> bool:
        """Queue-kompatibel: append statt overwrite — verhindert Event-Verlust."""
        try:
            with open(CMD_FILE, "a", encoding="utf-8") as f:
                f.write(cmd.strip() + "\n")
            return True
        except OSError as e:
            raise RuntimeError(f"Trigger-Datei nicht schreibbar ({CMD_FILE}): {e}")

    def core_online(self) -> bool:
        """True wenn status.json vorhanden und frisch (< 5s alt)."""
        if not os.path.exists(STATUS_FILE):
            return False
        try:
            age = time.time() - os.path.getmtime(STATUS_FILE)
            return age < 10.0
        except OSError:
            return False

    def wait_for_ack(self, check_fn, timeout: float = 3.0, interval: float = 0.25) -> bool:
        """Wartet bis check_fn() True zurückgibt."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if check_fn():
                return True
            time.sleep(interval)
        return False


class HTTPAdapter:
    """Optionaler HTTP-Adapter für /api/* Endpunkte."""

    def __init__(self, base: str = "http://127.0.0.1:8080"):
        self.base = base.rstrip("/")

    def get_json(self, path: str, timeout: float = 5.0):
        url = self.base + path
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"WebUI nicht erreichbar: {e}")

    def post_cmd(self, cmd: str, timeout: float = 5.0):
        url = self.base + "/api/cmd"
        data = json.dumps({"cmd": cmd}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"WebUI-API nicht erreichbar: {e}")
