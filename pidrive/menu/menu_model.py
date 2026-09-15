#!/usr/bin/env python3
"""
menu_model.py — Public API Facade  v0.11.127

Ausgelagert in:
  menu_state.py     — MenuNode, MenuState
  station_store.py  — StationStore
  menu_builder.py   — build_tree() (Inhalt)
  menu_annotate.py  — path_id / uid / skip_on_nav (M1 Post-Processing)

Diese Datei re-exportiert alle Klassen/Funktionen für Backward-Kompatibilität.
"""

from menu.menu_state import MenuNode, MenuState
from menu.station_store import StationStore
from menu.menu_builder import build_tree as _build_tree_raw
from menu.menu_annotate import annotate_tree


def build_tree(store, S, settings):
    """Baut den Menübaum und annotiert path_id/uid/skip_on_nav."""
    return annotate_tree(_build_tree_raw(store, S, settings))


__all__ = ["MenuNode", "MenuState", "StationStore", "build_tree"]
