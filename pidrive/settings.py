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
    "music_path":       os.path.expanduser("~/Musik"),
    "audio_output":     "auto",
    "fm_freq":          "98.5",
    "bt_last_mac":      "",
    "bt_last_name":     "",
    "bt_sink_mac":      "",
    "bt_pa_sink":       "",
    "scanner_vhf_freq": 136.000,
    "scanner_uhf_freq": 400.000,
    "volume":           90,
    "last_fm_station":  None,
    "last_dab_station": None,
    "dab_gain":         -1,
    "fm_gain":          -1,
    # v0.8.19: Boot-Resume
    "last_source":      "",     # fm / dab / webradio
    "last_web_station": None,   # dict mit name + url
    # v0.8.18: RTL-SDR Empfangsqualität
    "ppm_correction":   0,     # Frequenzfehler-Korrektur in ppm (0 = deaktiviert)
                               # Gemessener RTL2838-Wert (3 Messläufe): ~52 ppm
                               # Kalibrieren: sudo rtl_test -p (mehrere Minuten laufen lassen)
    "scanner_squelch":  25,    # Squelch-Schwelle (0=immer offen, 25=Standard, 10=empfindlich)
    # v0.9.0: Scanner-Gain + Lautstärke persistent
    "scanner_gain":     -1,    # Scanner HF-Gain (-1=Auto AGC, 0-49=manuell dB)
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
