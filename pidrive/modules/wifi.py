"""
modules/wifi.py - WiFi Modul
PiDrive Project - GPL-v3
"""

import subprocess
import time
from ui import Item, show_message, pick_list, C_BLUE

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

def wifi_toggle(S):
    if S["wifi"]:
        _bg("rfkill block wifi")
    else:
        _bg("rfkill unblock wifi; ip link set wlan0 up; dhcpcd wlan0")
    S["ts"] = 0

def build_items(screen, S, settings):

    def scan_and_connect():
        show_message(screen, "WiFi", "Scanne Netzwerke...", color=C_BLUE)
        try:
            out = _run("iwlist wlan0 scan 2>/dev/null | grep ESSID | "
                       "sed 's/.*ESSID://;s/\"//g'")
            nets = list(dict.fromkeys(
                [l.strip() for l in out.splitlines() if l.strip()]))
        except Exception:
            nets = []
        if not nets:
            show_message(screen, "WiFi", "Keine Netze gefunden")
            time.sleep(2)
            return
        chosen = pick_list(screen, "Netzwerke", nets, color=C_BLUE)
        if chosen:
            show_message(screen, "WiFi", f"Verbinde: {chosen}...")
            # Hier koennte wpa_cli verwendet werden
            # _bg(f'wpa_cli -i wlan0 ...')

    items = [
        Item("WiFi",
             sub=lambda: "Eingeschaltet" if S["wifi"] else "Ausgeschaltet",
             toggle=lambda: wifi_toggle(S),
             state=lambda: S["wifi"]),
        Item("Verbunden mit",
             sub=lambda: S["ssid"] if S["conn"] else "Nicht verbunden"),
        Item("Netzwerke scannen",
             action=scan_and_connect),
    ]
    return items
