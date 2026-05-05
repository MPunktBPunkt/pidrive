#!/usr/bin/env python3
"""
menu_model.py — Public API Facade  v0.10.35

Ausgelagert in:
  menu_state.py    — MenuNode, MenuState
  station_store.py — StationStore
  menu_builder.py  — build_tree()

Diese Datei re-exportiert alle Klassen/Funktionen für Backward-Kompatibilität.
"""

from menu_state import MenuNode, MenuState
from station_store import StationStore
from menu_builder import build_tree

__all__ = ["MenuNode", "MenuState", "StationStore", "build_tree"]
