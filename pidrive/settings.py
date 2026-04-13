"""
settings.py — Zentrales Settings-Modul für PiDrive

Darf von JEDEM Modul importiert werden, auch aus Threads.
Enthält KEINE Signal-Handler, keine pygame, keine Threads.
"""
import json
import os

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR    = os.path.join(BASE_DIR, "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

_DEFAULTS = {
    "music_path":    os.path.expanduser("~/Musik"),
    "audio_output":  "auto",
    "fm_freq":       "98.5",
}


def load_settings() -> dict:
    """settings.json lesen, Defaults zurückgeben wenn Datei fehlt."""
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(_DEFAULTS)


def save_settings(settings: dict) -> None:
    """settings.json atomar schreiben."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SETTINGS_FILE)
    except Exception as e:
        import log
        log.error(f"Settings speichern: {e}")
