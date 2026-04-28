"""
modules/source_state.py — Zustandsspiegel (kein Regler)
Aufrufer: alle modules/*, main_core.py, webui.py, ipc.py
Schreibt: /tmp/pidrive_source_state.json
Hinweis: source_state steuert NICHT — er spiegelt nur. Audio/BT über audio.py/bluetooth.py ändern.
"""


import os
import json
import threading
import time
import log

_LOCK = threading.RLock()
STATE_FILE = "/tmp/pidrive_source_state.json"

STATE = {
    "source_current": "idle",   # aktive Quelle
    "source_target":  "",       # Ziel-Quelle bei laufender Transition
    "transition":     False,    # True = Quellenwechsel läuft
    "owner":          "",       # wer die Transition gestartet hat
    "since":          0.0,      # Timestamp Start der Transition
    "audio_route":    "",       # klinke | bt | hdmi | none
    "bt_state":       "idle",   # BT-Link-State
    "boot_phase":     "cold_start",  # cold_start | restore_bt | restore_source | steady
}



def _write_state_file():
    """Shared-State atomar in /tmp schreiben (prozessübergreifend)."""
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATE, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        log.warn("SOURCE state file write: " + str(e))


def load_snapshot_file() -> dict:
    """Shared-State aus Datei lesen."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def snapshot() -> dict:
    """Atomare Kopie des aktuellen States."""
    with _LOCK:
        return dict(STATE)


def begin_transition(owner: str, target: str, timeout_s: float = 8.0) -> bool:
    """
    Startet eine Quellen-Transition. Gibt False zurück wenn bereits eine läuft.
    Bei Timeout (hängende Transition) wird die alte überschrieben.
    """
    with _LOCK:
        if STATE["transition"]:
            age = time.time() - STATE["since"]
            if age < timeout_s:
                log.warn(f"SOURCE begin blocked: owner={owner} active={STATE['owner']} age={age:.1f}s")
                return False
            else:
                log.warn(f"SOURCE stale transition ({age:.1f}s) — override by {owner}")

        STATE["transition"]     = True
        STATE["owner"]          = owner
        STATE["source_target"]  = target
        STATE["since"]          = time.time()
        _write_state_file()
        log.info(f"SOURCE begin: owner={owner} target={target}")
        return True


def commit_source(source_name: str):
    """Setzt die aktuelle Quelle nach erfolgreichem Start."""
    with _LOCK:
        old = STATE["source_current"]
        STATE["source_current"] = source_name
        _write_state_file()
        log.info(f"SOURCE commit: {old} → {source_name}")


def set_audio_route(route: str):
    """Setzt den aktiven Audio-Ausgabepfad."""
    with _LOCK:
        STATE["audio_route"] = route
        _write_state_file()
        log.info(f"SOURCE audio_route={route}")


def set_bt_state(bt_state: str):
    """Setzt den BT-Link-State."""
    with _LOCK:
        old = STATE["bt_state"]
        STATE["bt_state"] = bt_state
        _write_state_file()
        if old != bt_state:
            log.info(f"SOURCE bt_state: {old} → {bt_state}")


def set_boot_phase(phase: str):
    """Setzt die Boot-Phase."""
    with _LOCK:
        STATE["boot_phase"] = phase
        _write_state_file()
        log.info(f"SOURCE boot_phase={phase}")


def end_transition():
    """Schließt eine Transition ab."""
    with _LOCK:
        duration = time.time() - STATE["since"] if STATE["since"] else 0
        log.info(f"SOURCE end: owner={STATE['owner']} current={STATE['source_current']} dt={duration:.2f}s")
        STATE["source_target"] = ""
        STATE["transition"]    = False
        STATE["owner"]         = ""
        STATE["since"]         = 0.0
        _write_state_file()


def current_source() -> str:
    with _LOCK:
        return STATE["source_current"]


def in_transition() -> bool:
    with _LOCK:
        return STATE["transition"]


def bt_connected() -> bool:
    with _LOCK:
        return STATE["bt_state"] == "connected"
