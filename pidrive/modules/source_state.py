"""
modules/source_state.py — Zustandsspiegel (kein Regler)  v0.10.55
Aufrufer: alle modules/*, main_core.py, webui.py, ipc.py
Schreibt: /tmp/pidrive_source_state.json

v0.10.55 Verbesserungen:
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
    "source_previous": "idle",   # v0.10.55: letzte Quelle vor aktuellem Wechsel
    "source_target":   "",
    "transition":      False,
    "owner":           "",
    "since":           0.0,
    "audio_route":     "",
    "bt_state":        "idle",
    "bt_link_state":   "idle",
    "bt_audio_state":  "no_sink",
    "boot_phase":      "cold_start",
    "transition_count": 0,        # v0.10.55: Gesamtzahl Transitionen (für Diagnose)
    "stale_cleared":    0,        # v0.10.55: Zähler für automatisch abgeräumte Stale-Transitions
    "dab_playback_state": "idle",   # idle | starting | locked | no_lock | failed
    "playback_epoch": 0,
    "play_gen": 0,               # Invalidiert in-flight play_*/stop-Threads
    "history": [],               # W7/Z10: letzte Übergänge (Ringpuffer)
}

_HISTORY_MAX = 20


# ── Stale-Transition-Watchdog ────────────────────────────────────────────────

def _append_history(entry: dict):
    """Ringpuffer der letzten Übergänge (W7/Z10)."""
    hist = STATE.setdefault("history", [])
    hist.append(entry)
    if len(hist) > _HISTORY_MAX:
        del hist[0:len(hist) - _HISTORY_MAX]


def _check_stale_transition() -> bool:
    """
    v0.10.55: Räumt hängende Transition auf ohne auf begin_transition() zu warten.
    Wird von commit_source(), end_transition() und der Core-Hauptschleife aufgerufen.
    Gibt True zurück wenn eine Stale-Transition aufgeräumt wurde.
    """
    if not STATE["transition"]:
        return False
    age = time.time() - STATE["since"]
    if age < STALE_TIMEOUT_S:
        return False
    owner = STATE["owner"]
    target = STATE["source_target"]
    log.warn(
        f"SOURCE stale-watchdog: transition von owner={owner!r} "
        f"läuft seit {age:.1f}s — automatisch abgeräumt"
    )
    STATE["transition"]    = False
    STATE["owner"]         = ""
    STATE["source_target"] = ""
    STATE["since"]         = 0.0
    STATE["stale_cleared"] = STATE.get("stale_cleared", 0) + 1
    _append_history({
        "ts": time.time(),
        "owner": owner,
        "target": target,
        "result": "stale_cleared",
        "duration_s": round(age, 2),
    })
    _write_state_file()
    return True


def check_stale_transition() -> bool:
    """Öffentlicher Einstieg für die Core-Hauptschleife (W7/Z3)."""
    with _LOCK:
        return _check_stale_transition()


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
                _append_history({
                    "ts": time.time(),
                    "owner": owner,
                    "target": target,
                    "result": "rejected",
                    "blocked_by": STATE["owner"],
                    "duration_s": 0,
                })
                _write_state_file()
                return False
            log.warn(
                f"SOURCE stale transition ({age:.1f}s) — "
                f"override: {STATE['owner']!r} → {owner!r}"
            )
            STATE["stale_cleared"] = STATE.get("stale_cleared", 0) + 1
            _append_history({
                "ts": time.time(),
                "owner": STATE["owner"],
                "target": STATE["source_target"],
                "result": "stale_override",
                "duration_s": round(age, 2),
            })

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
        owner = STATE["owner"]
        since = STATE["since"]
        if old != source_name:
            STATE["source_previous"] = old
            STATE["playback_epoch"] = STATE.get("playback_epoch", 0) + 1
        STATE["source_current"] = source_name
        if auto_end and STATE["transition"]:
            duration = time.time() - since if since else 0
            STATE["source_target"] = ""
            STATE["transition"]    = False
            STATE["owner"]         = ""
            STATE["since"]         = 0.0
            _append_history({
                "ts": time.time(),
                "owner": owner,
                "target": source_name,
                "result": "ok",
                "from": old,
                "duration_s": round(duration, 2),
            })
            log.info(f"SOURCE commit+end: {old} → {source_name} dt={duration:.2f}s")
        else:
            log.info(f"SOURCE commit: {old} → {source_name}")
        _write_state_file()
        # Play-History wird von Quellmodulen mit echtem Sendernamen geschrieben


def end_transition():
    """Schließt eine Transition ab."""
    with _LOCK:
        _check_stale_transition()
        duration = time.time() - STATE["since"] if STATE["since"] else 0
        owner = STATE["owner"]
        current = STATE["source_current"]
        log.info(
            f"SOURCE end: owner={owner} "
            f"current={current} dt={duration:.2f}s"
        )
        if STATE["transition"] or owner:
            _append_history({
                "ts": time.time(),
                "owner": owner,
                "target": current,
                "result": "ended",
                "duration_s": round(duration, 2),
            })
        STATE["source_target"] = ""
        STATE["transition"]    = False
        STATE["owner"]         = ""
        STATE["since"]         = 0.0
        _write_state_file()


def force_end_transition(reason: str = "error"):
    """
    v0.10.55: Erzwingt Ende der Transition unabhängig vom aktuellen State.
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


def bump_play_gen(reason: str = "") -> int:
    """Neue User-Intention (play/stop) — alte bg-Threads sollen nicht mehr committen."""
    with _LOCK:
        STATE["play_gen"] = int(STATE.get("play_gen", 0) or 0) + 1
        gen = STATE["play_gen"]
        _write_state_file()
        if reason:
            log.info(f"SOURCE play_gen={gen} ({reason})")
        return gen


def is_play_gen(gen: int) -> bool:
    with _LOCK:
        return int(STATE.get("play_gen", 0) or 0) == int(gen)


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


def set_dab_playback_state(state: str):
    """Spiegel für dab_playback_state (idle|starting|locked|no_lock|failed)."""
    with _LOCK:
        old = STATE.get("dab_playback_state", "idle")
        STATE["dab_playback_state"] = state or "idle"
        if old != STATE["dab_playback_state"]:
            log.info(f"SOURCE dab_playback_state: {old} → {STATE['dab_playback_state']}")
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
    """v0.10.55: Letzte Quelle vor dem aktuellen Wechsel."""
    with _LOCK:
        return STATE.get("source_previous", "idle")


def in_transition() -> bool:
    with _LOCK:
        if not STATE["transition"]:
            return False
        age = time.time() - STATE["since"]
        if age >= STALE_TIMEOUT_S:
            # W7/Z3: Speicher und Datei bereinigen — nicht nur False vortäuschen
            _check_stale_transition()
            return False
        return True


def refresh_transition(owner: str | None = None) -> bool:
    """
    Verlängert eine laufende Transition (Watchdog-Schutz).
    Für Holds länger als STALE_TIMEOUT_S (z.B. PMR-Monitor Autotune).
    owner=None → jede aktive Transition; sonst nur bei Owner-Match (Prefix ok).
    """
    with _LOCK:
        if not STATE["transition"]:
            return False
        cur = str(STATE.get("owner") or "")
        if owner is not None:
            own = str(owner)
            if cur != own and not cur.startswith(own) and not own.startswith(cur):
                return False
        STATE["since"] = time.time()
        _write_state_file()
        return True


def rtl_capture_gate(check_monitor: bool = True) -> tuple[bool, str]:
    """
    Darf ein Spektrum-/rtl_sdr-Capture jetzt den Stick nutzen?
    Ändert den Spiegel nicht — nur Lesen + optional Monitor-Check.
    Monitor: Status-Datei (CLI/Web sind eigene Prozesse, kein Thread-Zugriff).
    """
    if in_transition():
        snap = snapshot()
        return False, (
            f"Quelle wechselt (owner={snap.get('owner') or '?'} "
            f"→ {snap.get('source_target') or '?'})"
        )
    cur = (current_source() or "idle").lower()
    if cur in ("dab", "fm", "scanner"):
        return False, f"RTL-Quelle aktiv: {cur} — zuerst stoppen"
    if check_monitor:
        mon_running = False
        try:
            from modules.radio import scanner as _sc
            mon_running = bool(_sc.is_pmr_monitor_running())
        except Exception:
            mon_running = False
        if not mon_running:
            try:
                with open("/tmp/pidrive_pmr_monitor.json", "r", encoding="utf-8") as f:
                    mon = json.load(f)
                mon_running = bool(mon.get("running"))
            except Exception:
                pass
        if mon_running:
            return False, "PMR-Monitor aktiv — zuerst: pidrivectl scanner monitor stop"
    return True, ""


def history(n: int = _HISTORY_MAX) -> list:
    """Letzte n Übergänge (W7/Z10)."""
    with _LOCK:
        hist = list(STATE.get("history") or [])
        return hist[-n:] if n else hist


def memory_matches_file() -> bool:
    """True wenn in_transition()-Sicht und Datei übereinstimmen (W7/Z3)."""
    snap = load_snapshot_file()
    with _LOCK:
        mem_t = bool(STATE["transition"]) and (time.time() - STATE["since"]) < STALE_TIMEOUT_S
    file_t = bool(snap.get("transition"))
    if file_t and snap.get("since"):
        try:
            file_t = (time.time() - float(snap["since"])) < STALE_TIMEOUT_S
        except Exception:
            pass
    return mem_t == file_t and STATE.get("source_current") == snap.get("source_current", STATE.get("source_current"))


def bt_connected() -> bool:
    with _LOCK:
        return STATE["bt_state"] == "connected"
