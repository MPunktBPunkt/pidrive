"""
settings.py — Zentrales Settings-Modul für PiDrive

v0.8.9: fehlende Schlüssel werden mit Defaults aufgefüllt (merge)
"""

import json
import os

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR    = os.path.join(BASE_DIR, "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

_DEFAULTS = {
    # Gerät
    "device_name":        "PiDrive",
    "display_brightness": 100,
    "theme":              "dark",
    # Quellen
    "spotify_enabled":    True,
    "webradio_enabled":   True,
    "dabfm_enabled":      True,
    # Audio
    "music_path":         os.path.expanduser("~/Musik"),
    "audio_output":       "auto",        # auto | klinke | bt | hdmi
    "volume":             90,
    # FM
    "fm_freq":            "98.5",
    "fm_gain":            -1,            # -1 = Auto AGC, 0–49 = dB
    # DAB
    "dab_gain":           -1,            # -1 = Auto AGC, gültige RTL-Stufe
    # Scanner
    "scanner_vhf_freq":   136.000,
    "scanner_uhf_freq":   400.000,
    "scanner_gain":       -1,            # -1 = Auto AGC
    "scanner_squelch":    25,            # 0=offen 10=empfindlich 25=standard 35=hart
    # RTL-SDR
    "ppm_correction":     0,             # Quarzfehler-Korrektur (gemessener ~52 ppm)
    # Bluetooth
    "bt_last_mac":        "",
    "bt_last_name":       "",
    "bt_sink_mac":        "",
    "bt_pa_sink":         "",
    # Boot-Resume
    "last_source":        "",            # fm | dab | webradio
    "last_fm_station":    None,
    "last_dab_station":   None,
    "last_web_station":   None,
}


def load_settings() -> dict:
    """settings.json lesen, Defaults mergen wenn Datei fehlt oder unvollständig."""
    merged = dict(_DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            merged.update(data)
    except Exception:
        pass
    return merged


def save_settings(settings: dict) -> None:
    """settings.json atomar schreiben (Defaults als Basis)."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        merged = dict(_DEFAULTS)
        if isinstance(settings, dict):
            merged.update(settings)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SETTINGS_FILE)
    except Exception as e:
        try:
            import log
            log.error(f"Settings speichern: {e}")
        except Exception:
            pass

def ensure_settings_file() -> None:
    """
    Schreibt eine vollständige settings.json mit allen Defaults wenn die Datei
    fehlt oder veraltete/fehlende Keys hat (v0.9.2).
    """
    try:
        current = load_settings()
        save_settings(current)
    except Exception:
        pass

