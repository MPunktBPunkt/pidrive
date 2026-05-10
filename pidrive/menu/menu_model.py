#!/usr/bin/env python3
"""
menu_model.py — Public API Facade  v0.10.55

Ausgelagert in:
  menu_state.py    — MenuNode, MenuState
  station_store.py — StationStore
  menu_builder.py  — build_tree()

Diese Datei re-exportiert alle Klassen/Funktionen für Backward-Kompatibilität.
"""

from menu.menu_state import MenuNode, MenuState
from menu.station_store import StationStore
from menu.menu_builder import build_tree

__all__ = ["MenuNode", "MenuState", "StationStore", "build_tree"]
