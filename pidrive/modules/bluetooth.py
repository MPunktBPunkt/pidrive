"""
modules/bluetooth.py - Bluetooth Modul
PiDrive Project - GPL-v3
"""

import subprocess
import time
import pygame
from ui import Item, show_message, pick_list, C_BT_BLUE

def _run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=8)
        return r.stdout.strip()
    except Exception:
        return ""

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def bt_toggle(S):
    if S["bt"]:
        _bg("hciconfig hci0 down")
    else:
        _bg("rfkill unblock bluetooth; hciconfig hci0 up")
    S["ts"] = 0

def get_bt_audio_label(S):
    if S.get("bt_sink"):
        dev = S.get("bt_connected_dev", "") or "BT Geraet"
        return f"Aktiv: {dev[:18]}"
    return "Kein BT Geraet"

def build_items(screen, S, settings):

    def scan_and_pair():
        show_message(screen, "Bluetooth", "Suche Geraete (5s)...",
                     color=C_BT_BLUE)
        _bg("bluetoothctl scan on")
        t0 = time.time()
        while time.time() - t0 < 5:
            pygame.event.pump()
            time.sleep(0.2)
        _bg("bluetoothctl scan off")

        out = _run("bluetoothctl devices 2>/dev/null")
        devs = []
        for line in out.splitlines():
            p = line.split(" ", 2)
            if len(p) >= 3:
                devs.append({"mac": p[1], "name": p[2]})

        if not devs:
            show_message(screen, "Bluetooth", "Keine Geraete gefunden")
            time.sleep(2)
            return

        names = [d["name"] for d in devs]
        chosen = pick_list(screen, "BT Geraete", names, color=C_BT_BLUE)
        if chosen:
            mac = next((d["mac"] for d in devs if d["name"] == chosen), None)
            if mac:
                show_message(screen, "Bluetooth", f"Koppeln: {chosen}...")
                _bg(f"bluetoothctl pair {mac}; bluetoothctl connect {mac}")
                time.sleep(3)
                S["ts"] = 0

    def set_bt_audio():
        if not S.get("bt_sink"):
            show_message(screen, "Bluetooth", "Kein BT Geraet verbunden")
            time.sleep(2)
            return
        _bg(f"pactl set-default-sink {S['bt_sink']} 2>/dev/null")
        settings["audio_output"] = "Bluetooth"
        show_message(screen, "Bluetooth", "Als Ausgang gesetzt")
        time.sleep(1)

    def disconnect_all():
        out = _run("bluetoothctl devices Connected 2>/dev/null")
        for line in out.splitlines():
            p = line.split(" ", 2)
            if len(p) >= 2:
                _bg(f"bluetoothctl disconnect {p[1]}")
        S["ts"] = 0
        show_message(screen, "Bluetooth", "Alle getrennt")
        time.sleep(1)

    items = [
        Item("Bluetooth",
             sub=lambda: "Eingeschaltet" if S["bt"] else "Ausgeschaltet",
             toggle=lambda: bt_toggle(S),
             state=lambda: S["bt"]),
        Item("Geraete scannen",
             action=scan_and_pair),
        Item("Als Audio-Ausgang",
             sub=lambda: get_bt_audio_label(S),
             action=set_bt_audio),
        Item("Alle trennen",
             action=disconnect_all),
    ]
    return items
