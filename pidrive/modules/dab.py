#!/usr/bin/env python3
"""
modules/dab.py — Public API Facade  v0.10.45

Ausgelagert in:
  dab_helpers.py  — Hilfsfunktionen, Konstanten, Gain-Tabelle, Session
  dab_dls.py      — DLS-Poller (Dynamic Label Segment)
  dab_scan.py     — Suchlauf und Sender-Datenbank
  dab_play.py     — Wiedergabe (play_station, play_by_name, stop)

Backward-kompatibel: alle öffentlichen Funktionen bleiben erreichbar.
"""

from modules.dab_helpers import C_DAB, ERR_FILE, PLAY_DEBUG_FILE, SCAN_DEBUG_FILE
from modules.dab_scan import (
    load_stations, save_stations,
    scan_dab_channels, get_last_scan_diag,
    load_last_scan_diag_file, is_scan_running,
)
from modules.dab_play import (
    play_station, play_by_name, stop,
    play_next, play_prev,
)

__all__ = [
    "play_station", "play_by_name", "stop", "play_next", "play_prev",
    "scan_dab_channels", "load_stations", "save_stations",
    "get_last_scan_diag", "load_last_scan_diag_file",
    "is_scan_running", "C_DAB",
]
