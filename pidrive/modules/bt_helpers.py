#!/usr/bin/env python3
"""bt_helpers.py — Basis-Helfer und Adapter-Steuerung  v0.10.44
Ausgelagert aus bluetooth.py."""

import json
import os
import re
import subprocess
import threading
import select
import time
from typing import Optional

import sys as _sys
_PIDRIVE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PIDRIVE not in _sys.path:
    _sys.path.insert(0, _PIDRIVE)

import ipc
import log

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None


# ── Dateien / Konstanten ─────────────────────────────────────────────────────
KNOWN_BT_FILE = "/tmp/pidrive_bt_known_devices.json"
DISCOVERED_BT_FILE = "/tmp/pidrive_bt_devices.json"
AGENT_STATE_FILE = "/tmp/pidrive_bt_agent.json"
WATCHER_STATE_FILE = "/tmp/pidrive_bt_watcher.json"

PAIRING_BACKUP_FILE = "/tmp/pidrive_bt_pairing_debug.json"

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"

DEFAULT_SCAN_SECONDS = 22
DISCOVERY_REFRESH_SECONDS = 2.0

VISIBLE_TTL_SECONDS = 45          # Gerät gilt für UI kurz als "frisch sichtbar"
RECENT_SEEN_SECONDS = 7 * 24 * 3600
RECONNECT_COOLDOWN = 45
RECONNECT_FAIL_SOFT_LIMIT = 3

A2DP_WAIT_SECONDS = 10
VISIBILITY_WAIT_SECONDS = 20
PAIR_TIMEOUT_SECONDS = 45

_bt_connect_lock = threading.Lock()
_scan_lock = threading.Lock()

_scan_proc = None
_scan_stop_flag = False

_AGENT_PROC = None
_AGENT_LOCK = threading.Lock()

_reconnect_thread = None
_reconnect_stop = False
_reconnect_wakeup = None

_RECONNECT_LAST_TRY = {}
_RECONNECT_FAILS = {}


# ─────────────────────────────────────────────────────────────────────────────
# Basis-Helper
# ─────────────────────────────────────────────────────────────────────────────



# ── Globale Sperren und geteilter Prozess-State ──────────────────────────────
# Diese Objekte werden hier definiert und von bt_connect.py / bt_devices.py
# per `from modules.bt_helpers import _bt_connect_lock, _scan_lock` importiert.
# Da es Lock-Objekte sind (mutable), wird die Referenz korrekt geteilt.

_bt_connect_lock = threading.Lock()
_scan_lock = threading.Lock()

# ── Basis-Helfer ─────────────────────────────────────────────────────────────
def _now() -> int:
    return int(time.time())


def _sleep_s(sec: float):
    try:
        time.sleep(sec)
    except Exception:
        pass


def _write_json_atomic(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log.warn(f"BT json write {path}: {e}")


def _read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _run(cmd, timeout=8):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _btctl(cmd, timeout=12):
    """
    Robuster bluetoothctl-Wrapper mit Logging.
    """
    try:
        r = subprocess.run(
            f"bluetoothctl {cmd} 2>&1",
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        log.info(
            f"BT ctl: {cmd} rc={r.returncode} "
            f"out={out[:220].replace(chr(10), ' | ')}"
        )
        return r.returncode, out
    except subprocess.TimeoutExpired:
        log.warn(f"BT ctl timeout: {cmd}")
        return 124, "timeout"
    except Exception as e:
        log.error(f"BT ctl error: {cmd}: {e}")
        return 1, str(e)


def _bg(cmd):
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def _normalize_mac(mac: str) -> str:
    return (mac or "").strip().upper()


def _valid_mac(mac: str) -> bool:
    return bool(re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", _normalize_mac(mac)))


def _parse_bool_from_info(info_out: str, key: str) -> bool:
    low = (info_out or "").lower()
    return f"{key.lower()}: yes" in low


def _extract_name_from_info(info_out: str, fallback: str = "") -> str:
    name = fallback or ""
    for line in (info_out or "").splitlines():
        s = line.strip()
        if s.lower().startswith("name:"):
            v = s.split(":", 1)[1].strip()
            if v:
                return v
    return name or fallback


def _extract_alias_from_info(info_out: str, fallback: str = "") -> str:
    alias = fallback or ""
    for line in (info_out or "").splitlines():
        s = line.strip()
        if s.lower().startswith("alias:"):
            v = s.split(":", 1)[1].strip()
            if v:
                return v
    return alias or fallback


def _is_public_or_bredr(info_out: str) -> bool:
    low = (info_out or "").lower()
    return (
        "(public)" in low or
        "bredr" in low or
        "br/edr" in low or
        "class:" in low
    )


def _is_audio_device_info(info_out: str) -> bool:
    low = (info_out or "").lower()
    return (
        "0000110b" in low or
        "0000110e" in low or
        "00001108" in low or
        "0000111e" in low or
        "audio sink" in low or
        "headset" in low or
        "headphone" in low or
        "handsfree" in low or
        "a/v remote control" in low or
        "class:" in low
    )


def _bt_adapter_up() -> bool:
    out = _run("hciconfig hci0 2>/dev/null", timeout=4)
    return "UP RUNNING" in out


def _ensure_bt_on(S=None) -> bool:
    """
    Adapter sicher aktivieren.
    """
    try:
        _bg("rfkill unblock bluetooth")
        _bg("hciconfig hci0 up")
        rc, _ = _btctl("power on", timeout=8)
        _sleep_s(1.0)
        ok = _bt_adapter_up() or rc == 0
        if S is not None:
            S["bt_on"] = bool(ok)
            if ok and not S.get("bt"):
                S["bt_status"] = S.get("bt_status") if S.get("bt_status") == "verbunden" else "getrennt"
        return bool(ok)
    except Exception as e:
        log.warn(f"BT ensure on: {e}")
        return False


def _ensure_bt_off():
    try:
        _btctl("scan off", timeout=5)
    except Exception:
        pass
    _bg("bluetoothctl power off")
    _bg("hciconfig hci0 down")
    _sleep_s(1.0)



