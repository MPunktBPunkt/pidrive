"""
modules/audio.py - Audioausgang Modul
PiDrive Project - GPL-v3
"""

import subprocess
import time
from ui import Item, show_message, pick_list, C_ORANGE

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def set_output(mode, S, settings):
    if mode == "Klinke":
        _bg("amixer -c 0 cset numid=3 1 2>/dev/null")
        settings["audio_output"] = "Klinke"
    elif mode == "HDMI":
        _bg("amixer -c 0 cset numid=3 2 2>/dev/null")
        settings["audio_output"] = "HDMI"
    elif mode == "Bluetooth":
        sink = S.get("bt_sink", "")
        if sink:
            _bg(f"pactl set-default-sink {sink} 2>/dev/null")
            settings["audio_output"] = "BT"
    elif mode == "Alle":
        _bg("pactl load-module module-combine-sink sink_name=combined 2>/dev/null; "
            "pactl set-default-sink combined 2>/dev/null")
        settings["audio_output"] = "Alle"

def build_items(screen, S, settings):

    def select_output():
        options = ["Klinke (3.5mm)", "HDMI", "Bluetooth", "Alle kombiniert"]
        chosen = pick_list(screen, "Audioausgang", options, color=C_ORANGE)
        if chosen:
            mode = chosen.split(" ")[0]
            if mode == "Alle":
                mode = "Alle"
            elif mode == "Bluetooth" and not S.get("bt_sink"):
                show_message(screen, "Audio", "Kein BT verbunden!")
                time.sleep(2)
                return
            set_output(mode, S, settings)
            show_message(screen, "Audio", f"{mode} aktiv")
            time.sleep(1)

    def volume_up():
        _bg("amixer -q sset Master 5%+")

    def volume_down():
        _bg("amixer -q sset Master 5%-")

    items = [
        Item("Ausgang",
             sub=lambda: settings.get("audio_output", "auto"),
             action=select_output),
        Item("Lauter",
             action=volume_up),
        Item("Leiser",
             action=volume_down),
    ]
    return items
