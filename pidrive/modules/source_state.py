"""
modules/source_state.py — Zustandsspiegel (kein Regler)  v0.10.31
Aufrufer: alle modules/*, main_core.py, webui.py, ipc.py
Schreibt: /tmp/pidrive_source_state.json

v0.10.31 Verbesserungen:
  - previous_source: Rückkehr nach Fehler möglich
  - Stale-Transition-Watchdog: räumt hängendes transition=True automatisch auf
  - commit_source() optional mit auto-end (spart vergessene end_transition()-Aufrufe)
  - force_end_transition(): für Fehler-Recovery in except-Blöcken
  - begin_transition() loggt Warnung wenn Aufrufer Rückgabewert ignoriert
  - Transitions-Zähler für Diagnose
"""

import os
import json
import threading
import time
import log

_LOCK = threading.RLock()
STATE_FILE = "/tmp/pidrive_source_state.json"

# Timeout bevor eine hängende Transition automatisch abgebrochen wird
STALE_TIMEOUT_S = 12.0

STATE = {
    "source_current":  "idle",
    "source_previous": "idle",   # v0.10.31: letzte Quelle vor aktuellem Wechsel
    "source_target":   "",
    "transition":      False,
    "owner":           "",
    "since":           0.0,
    "audio_route":     "",
    "bt_state":        "idle",
    "bt_link_state":   "idle",
    "bt_audio_state":  "no_sink",
    "boot_phase":      "cold_start",
    "transition_count": 0,        # v0.10.31: Gesamtzahl Transitionen (für Diagnose)
    "stale_cleared":    0,        # v0.10.31: Zähler für automatisch abgeräumte Stale-Transitions
}


# ── Stale-Transition-Watchdog ────────────────────────────────────────────────

def _check_stale_transition() -> bool:
    """
    v0.10.31: Räumt hängende Transition auf ohne auf begin_transition() zu warten.
    Wird von commit_source() und end_transition() aufgerufen.
    Gibt True zurück wenn eine Stale-Transition aufgeräumt wurde.
    """
    if not STATE["transition"]:
        return False
    age = time.time() - STATE["since"]
    if age < STALE_TIMEOUT_S:
        return False
    log.warn(
        f"SOURCE stale-watchdog: transition von owner={STATE['owner']!r} "
        f"läuft seit {age:.1f}s — automatisch abgeräumt"
    )
    STATE["transition"]    = False
    STATE["owner"]         = ""
    STATE["source_target"] = ""
    STATE["since"]         = 0.0
    STATE["stale_cleared"] = STATE.get("stale_cleared", 0) + 1
    _write_state_file()
    return True


# ── Datei-I/O ────────────────────────────────────────────────────────────────

def _write_state_file():
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATE, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        log.warn("SOURCE state file write: " + str(e))


def load_snapshot_file() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def snapshot() -> dict:
    """Atomare Kopie des aktuellen States."""
    with _LOCK:
        return dict(STATE)


# ── Transition-Protokoll ─────────────────────────────────────────────────────

def begin_transition(owner: str, target: str, timeout_s: float = STALE_TIMEOUT_S) -> bool:
    """
    Startet eine Quellen-Transition.
    Gibt False zurück wenn bereits eine AKTIVE (nicht-stale) Transition läuft.
    Bei Stale (abgelaufener Timeout) wird automatisch überschrieben.
    """
    with _LOCK:
        if STATE["transition"]:
            age = time.time() - STATE["since"]
            if age < timeout_s:
                log.warn(
                    f"SOURCE begin blocked: owner={owner!r} "
                    f"active={STATE['owner']!r} age={age:.1f}s — "
                    f"Aufrufer muss Rückgabewert False beachten!"
                )
                return False
            log.warn(
                f"SOURCE stale transition ({age:.1f}s) — "
                f"override: {STATE['owner']!r} → {owner!r}"
            )
            STATE["stale_cleared"] = STATE.get("stale_cleared", 0) + 1

        STATE["transition"]      = True
        STATE["owner"]           = owner
        STATE["source_target"]   = target
        STATE["since"]           = time.time()
        STATE["transition_count"] = STATE.get("transition_count", 0) + 1
        _write_state_file()
        log.info(f"SOURCE begin: owner={owner} target={target} "
                 f"(#{STATE['transition_count']})")
        return True


def commit_source(source_name: str, auto_end: bool = False):
    """
    Setzt die aktuelle Quelle nach erfolgreichem Start.
    auto_end=True: schließt die Transition automatisch ab (erspart end_transition()-Aufruf).
    previous_source wird immer gesichert.
    """
    with _LOCK:
        _check_stale_transition()
        old = STATE["source_current"]
        if old != source_name:
            STATE["source_previous"] = old
        STATE["source_current"] = source_name
        if auto_end and STATE["transition"]:
            duration = time.time() - STATE["since"] if STATE["since"] else 0
            STATE["source_target"] = ""
            STATE["transition"]    = False
            STATE["owner"]         = ""
            STATE["since"]         = 0.0
            log.info(f"SOURCE commit+end: {old} → {source_name} dt={duration:.2f}s")
        else:
            log.info(f"SOURCE commit: {old} → {source_name}")
        _write_state_file()


def end_transition():
    """Schließt eine Transition ab."""
    with _LOCK:
        _check_stale_transition()
        duration = time.time() - STATE["since"] if STATE["since"] else 0
        log.info(
            f"SOURCE end: owner={STATE['owner']} "
            f"current={STATE['source_current']} dt={duration:.2f}s"
        )
        STATE["source_target"] = ""
        STATE["transition"]    = False
        STATE["owner"]         = ""
        STATE["since"]         = 0.0
        _write_state_file()


def force_end_transition(reason: str = "error"):
    """
    v0.10.31: Erzwingt Ende der Transition unabhängig vom aktuellen State.
    Für except-Blöcke und Fehler-Recovery.
    """
    with _LOCK:
        if STATE["transition"]:
            log.warn(
                f"SOURCE force_end: reason={reason} "
                f"owner={STATE['owner']!r} current={STATE['source_current']}"
            )
        STATE["source_target"] = ""
        STATE["transition"]    = False
        STATE["owner"]         = ""
        STATE["since"]         = 0.0
        _write_state_file()


# ── Audio-Route ──────────────────────────────────────────────────────────────

def set_audio_route(route: str):
    with _LOCK:
        STATE["audio_route"] = route
        _write_state_file()
        log.info(f"SOURCE audio_route={route}")


# ── BT-State ─────────────────────────────────────────────────────────────────

def set_bt_state(bt_state: str):
    with _LOCK:
        old = STATE["bt_state"]
        STATE["bt_state"] = bt_state
        _write_state_file()
        if old != bt_state:
            log.info(f"SOURCE bt_state: {old} → {bt_state}")


def set_bt_link_state(state: str):
    with _LOCK:
        old = STATE.get("bt_link_state", "")
        STATE["bt_link_state"] = state
        if old != state:
            log.info(f"SOURCE bt_state: {old} → {state}")
        _write_state_file()


def set_bt_audio_state(state: str):
    with _LOCK:
        old = STATE.get("bt_audio_state", "")
        STATE["bt_audio_state"] = state
        if old != state:
            log.info(f"SOURCE bt_audio_state: {old} → {state}")
        _write_state_file()


def get_bt_link_state() -> str:
    return STATE.get("bt_link_state", "idle")


def get_bt_audio_state() -> str:
    return STATE.get("bt_audio_state", "no_sink")


# ── Boot-Phase ───────────────────────────────────────────────────────────────

def set_boot_phase(phase: str):
    with _LOCK:
        STATE["boot_phase"] = phase
        _write_state_file()
        log.info(f"SOURCE boot_phase={phase}")


# ── Lesezugriffe ─────────────────────────────────────────────────────────────

def current_source() -> str:
    with _LOCK:
        return STATE["source_current"]


def previous_source() -> str:
    """v0.10.31: Letzte Quelle vor dem aktuellen Wechsel."""
    with _LOCK:
        return STATE.get("source_previous", "idle")


def in_transition() -> bool:
    with _LOCK:
        # v0.10.31: Stale-Transitions nicht als aktiv melden
        if not STATE["transition"]:
            return False
        age = time.time() - STATE["since"]
        if age >= STALE_TIMEOUT_S:
            return False  # Stale → gilt als beendet
        return True


def bt_connected() -> bool:
    with _LOCK:
        return STATE["bt_state"] == "connected"
