"""
modules/favorites.py - Favoritenliste
PiDrive - GPL-v3

Unterstuetzt: FM, DAB+, Webradio, Scanner-Kanaele
Gespeichert in config/favorites.json
"""

import json
import os
import ipc
import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAV_FILE = os.path.join(BASE_DIR, "config", "favorites.json")


def _load():
    try:
        with open(FAV_FILE) as f:
            d = json.load(f)
        return d.get("favorites", [])
    except Exception:
        return []


def _save(favs):
    try:
        os.makedirs(os.path.dirname(FAV_FILE), exist_ok=True)
        with open(FAV_FILE, "w") as f:
            json.dump({"version": 1, "favorites": favs}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error("Favoriten speichern: " + str(e))


def get_all():
    """Alle Favoriten laden."""
    return _load()


def is_favorite(station_id):
    """Prüfen ob eine Station als Favorit markiert ist."""
    return any(f.get("id") == station_id for f in _load())


def add(station: dict):
    """Station als Favorit hinzufügen.
    station = {"id": ..., "name": ..., "source": "fm"|"dab"|"webradio"|"scanner", "meta": {...}}
    """
    favs = _load()
    sid = station.get("id", "")
    if not sid or any(f.get("id") == sid for f in favs):
        return False   # Bereits vorhanden
    favs.append(station)
    _save(favs)
    log.info("Favorit hinzugefügt: " + station.get("name", sid))
    ipc.write_progress("Favorit", station.get("name","")[:24] + " gespeichert ★", color="green")
    import time; time.sleep(1); ipc.clear_progress()
    return True


def remove(station_id: str):
    """Favorit entfernen."""
    favs = _load()
    name = next((f.get("name","") for f in favs if f.get("id") == station_id), station_id)
    favs = [f for f in favs if f.get("id") != station_id]
    _save(favs)
    log.info("Favorit entfernt: " + name)
    ipc.write_progress("Favorit", name[:24] + " entfernt", color="orange")
    import time; time.sleep(1); ipc.clear_progress()


def toggle(station: dict):
    """Favorit hinzufügen oder entfernen."""
    sid = station.get("id","")
    if is_favorite(sid):
        remove(sid)
        return False
    else:
        add(station)
        return True
