"""
core_callbacks.py — Scan- und Quellwechsel-Callbacks für PiDrive Core.
Extrahiert aus main_core.py (Prio C Architektur-Cleanup v0.11.21).

Importiert und registriert von main_core._init_dispatcher().
"""

import time
from log import get_logger
log = get_logger("core")

def _scan_begin(source):
    with _SCAN_LOCK:
        if _SCAN_STATE["active"]:
            return False
        _SCAN_STATE.update({
            "active": True,
            "source": source,
            "started_ts": int(time.time())
        })
        return True


def _scan_end():
    with _SCAN_LOCK:
        _SCAN_STATE.update({"active": False, "source": "", "started_ts": 0})


def _scan_info():
    with _SCAN_LOCK:
        return dict(_SCAN_STATE)


# ── Globaler Source-Switch-Lock ──────────────────────────────────────────────

import threading as _src_threading

_SOURCE_SWITCH_LOCK  = _src_threading.Lock()
_SOURCE_SWITCH_STATE = {"active": False, "owner": "", "started_ts": 0.0}



def _source_switch_begin(owner="unknown", blocking=False):
    ok = _SOURCE_SWITCH_LOCK.acquire(blocking=blocking)
    if not ok:
        return False
    _SOURCE_SWITCH_STATE["active"]     = True
    _SOURCE_SWITCH_STATE["owner"]      = owner
    _SOURCE_SWITCH_STATE["started_ts"] = _time_mod.time() if "_time_mod" in dir() else 0.0
    return True


def _source_switch_end():
    try:
        if _SOURCE_SWITCH_LOCK.locked():
            _SOURCE_SWITCH_STATE["active"]     = False
            _SOURCE_SWITCH_STATE["owner"]      = ""
            _SOURCE_SWITCH_STATE["started_ts"] = 0.0
            _SOURCE_SWITCH_LOCK.release()
    except RuntimeError:
        pass


def _source_switch_info():
    return dict(_SOURCE_SWITCH_STATE)


# ── Trigger-Entprellung ──────────────────────────────────────────────────────

import time as _time_mod

_LAST_TRIGGER_TS: dict = {}
_TRIGGER_DEBOUNCE = {
    "enter":    0.35,
    "fm_next":  0.5,
    "fm_prev":  0.5,
    "dab_next": 0.5,
    "dab_prev": 0.5,
}




def _debounced(cmd: str) -> bool:
    now   = _time_mod.time()
    limit = _TRIGGER_DEBOUNCE.get(cmd)
    if not limit:
        return False
    last = _LAST_TRIGGER_TS.get(cmd, 0.0)
    if now - last < limit:
        log.info(f"TRIGGER debounce: {cmd}")
        return True
    _LAST_TRIGGER_TS[cmd] = now
    return False


# ── BT-Agent früh starten ────────────────────────────────────────────────────
