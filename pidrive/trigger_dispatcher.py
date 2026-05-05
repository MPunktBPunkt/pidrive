#!/usr/bin/env python3
"""
trigger_dispatcher.py — PiDrive Trigger-Dispatcher  v0.10.32

Ausgelagert aus main_core.py. handle_trigger() delegiert an:
  td_nav.py       — Navigation, Menü-Aktionen, _execute_node
  td_hardware.py  — Spotify, Audio, WiFi/BT, Gain/PPM, RTL-SDR
  td_radio.py     — DAB/FM Suchlauf, Webradio, FM/DAB next/prev
  td_scanner.py   — Scanner-Steuerung
  td_system.py    — Bibliothek, System-Kommandos, radio_stop

Importiert von: main_core.py
"""

import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import log, ipc
from settings import save_settings

import td_nav
import td_hardware
import td_radio
import td_scanner
import td_system

from td_nav import _execute_node, _fm_manual


# ── Guards (von main_core initialisiert) ─────────────────────────────────────

_source_switch_begin = None
_source_switch_end   = None
_source_switch_info  = None
_scan_begin          = None
_scan_end            = None
_scan_info           = None

def _set_guards(begin_fn, end_fn, info_fn, sc_begin, sc_end, sc_info):
    global _source_switch_begin, _source_switch_end, _source_switch_info
    global _scan_begin, _scan_end, _scan_info
    _source_switch_begin = begin_fn
    _source_switch_end   = end_fn
    _source_switch_info  = info_fn
    _scan_begin          = sc_begin
    _scan_end            = sc_end
    _scan_info           = sc_info


# ── Entpreller ────────────────────────────────────────────────────────────────

_DEBOUNCE: dict = {}
_DEBOUNCE_MS: int = 350

def _debounced(cmd: str) -> bool:
    now = _time_mod.time()
    last = _DEBOUNCE.get(cmd, 0.0)
    if now - last < _DEBOUNCE_MS / 1000:
        return True
    _DEBOUNCE[cmd] = now
    return False

_LAST_NODE_EXEC_TS = 0.0
_LAST_NODE_EXEC_ID = ""


# ── Haupt-Dispatcher ──────────────────────────────────────────────────────────

def handle_trigger(cmd, menu_state, store, S, settings):
    """
    Zentrale Trigger-Verarbeitung — delegiert an thematische Sub-Dispatcher.
    Reihenfolge: Navigation → Hardware → Radio → Scanner → System
    """
    rebuild = False

    if _debounced(cmd):
        return False

    def bg(fn, name="bg_trigger"):
        def _safe_runner():
            try:
                fn()
            except Exception as _e:
                log.error(f"BG-Thread {name} Fehler: {_e}")
        threading.Thread(target=_safe_runner, daemon=True, name=name).start()

    handled = (
        td_nav.handle(cmd, menu_state, store, S, settings, bg) or
        td_hardware.handle(cmd, menu_state, store, S, settings, bg) or
        td_radio.handle(cmd, menu_state, store, S, settings, bg) or
        td_scanner.handle(cmd, menu_state, store, S, settings, bg) or
        td_system.handle(cmd, menu_state, store, S, settings, bg)
    )
    if not handled:
        log.info(f"TRIGGER unbekannt: {cmd!r}")
        return False

    log.trigger_received(cmd)

    # Nur echte Menüstruktur-Änderungen brauchen rebuild_tree().
    # Reine Navigation (up/down/enter/back/left/right) ändert MenuState direkt —
    # ein sofortiger Rebuild danach setzt den Cursor auf 0 zurück!
    rebuild_cmds = {
        "dab_scan", "dab_scan_replace",
        "fm_scan",
        "lib_browse",
        "bt_scan", "wifi_scan",
    }
    rebuild = (
        cmd in rebuild_cmds
        or cmd.startswith("reload_stations:")
        or cmd.startswith("dab_scan_channels:")
        or cmd.startswith("fav_toggle:")
        or cmd.startswith("cat:")
    )
    return rebuild

