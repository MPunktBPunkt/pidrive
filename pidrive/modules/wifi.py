"""
modules/wifi.py - WiFi Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, time, ipc
from ui import Item

def _run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8).stdout.strip()
    except: return ""

def _bg(cmd):
    try: subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def wifi_toggle(S):
    _bg("rfkill block wifi" if S["wifi"] else "rfkill unblock wifi; ip link set wlan0 up; dhcpcd wlan0")
    S["ts"] = 0

def build_items(screen, S, settings):
    def scan_and_connect():
        ipc.write_progress("WiFi", "Scanne Netzwerke...", color="blue")
        out = _run("iwlist wlan0 scan 2>/dev/null | grep ESSID | sed 's/.*ESSID://;s/\"//g'")
        nets = list(dict.fromkeys([l.strip() for l in out.splitlines() if l.strip()]))
        if not nets:
            ipc.write_progress("WiFi", "Keine Netze gefunden", color="orange"); time.sleep(2); ipc.clear_progress(); return
        chosen = ipc.headless_pick("Netzwerke", nets)
        if chosen:
            ipc.write_progress("WiFi", f"Verbinde: {chosen}...", color="blue"); time.sleep(2); ipc.clear_progress()

    return [
        Item("WiFi", sub=lambda: "Eingeschaltet" if S["wifi"] else "Ausgeschaltet",
             toggle=lambda: wifi_toggle(S), state=lambda: S["wifi"]),
        Item("Verbunden mit", sub=lambda: S["ssid"] if S["conn"] else "Nicht verbunden"),
        Item("Netzwerke scannen", action=scan_and_connect),
    ]
