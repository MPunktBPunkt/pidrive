"""
modules/bluetooth.py - Bluetooth Modul
PiDrive v0.6.1 — pygame-frei, Status via IPC
"""

import subprocess
import time
import log
import ipc
from ui import Item

C_BT_BLUE = (30, 144, 255)

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
        dev = S.get("bt_connected_dev", "") or "BT Gerät"
        return f"Aktiv: {dev[:18]}"
    return "Kein BT Gerät"

def build_items(screen, S, settings):

    def scan_and_pair():
        ipc.write_progress("Bluetooth", "Suche Geräte (5s)...", color="blue")
        _bg("bluetoothctl scan on")
        for _ in range(25):
            time.sleep(0.2)
        _bg("bluetoothctl scan off")

        out = _run("bluetoothctl devices 2>/dev/null")
        devs = []
        for line in out.splitlines():
            p = line.split(" ", 2)
            if len(p) >= 3:
                devs.append({"mac": p[1], "name": p[2]})

        if not devs:
            ipc.write_progress("Bluetooth", "Keine Geräte gefunden", color="orange")
            time.sleep(2)
            ipc.clear_progress()
            return

        # Geräteliste als IPC-Auswahl schreiben
        # (Display kann liste anzeigen, Auswahl via pick_list wenn Display läuft)
        names = [d["name"] for d in devs]
        ipc.write_progress("BT Geräte",
                           lines=names[:6],
                           color="blue")
        log.info(f"BT Scan: {len(devs)} Geräte: {', '.join(names[:3])}")
        # Verbinde mit erstem Gerät — volle Auswahl kommt mit Display
        if devs:
            first = devs[0]
            ipc.write_progress("Bluetooth",
                               f"Verbinde: {first['name']}...", color="blue")
            _bg(f"bluetoothctl pair {first['mac']}; "
                f"bluetoothctl connect {first['mac']}")
            time.sleep(3)
            S["ts"] = 0
        ipc.clear_progress()

    def set_bt_audio():
        if not S.get("bt_sink"):
            ipc.write_progress("Bluetooth", "Kein BT Gerät verbunden", color="orange")
            time.sleep(2)
            ipc.clear_progress()
            return
        _bg(f"pactl set-default-sink {S['bt_sink']} 2>/dev/null")
        settings["audio_output"] = "Bluetooth"
        ipc.write_progress("Bluetooth", "Als Ausgang gesetzt", color="green")
        time.sleep(1)
        ipc.clear_progress()

    def disconnect_all():
        out = _run("bluetoothctl devices Connected 2>/dev/null")
        for line in out.splitlines():
            p = line.split(" ", 2)
            if len(p) >= 2:
                _bg(f"bluetoothctl disconnect {p[1]}")
        S["ts"] = 0
        ipc.write_progress("Bluetooth", "Alle getrennt", color="green")
        time.sleep(1)
        ipc.clear_progress()

    return [
        Item("Bluetooth",
             sub=lambda: "Eingeschaltet" if S["bt"] else "Ausgeschaltet",
             toggle=lambda: bt_toggle(S),
             state=lambda: S["bt"]),
        Item("Geräte scannen",
             action=scan_and_pair),
        Item("Als Audio-Ausgang",
             sub=lambda: get_bt_audio_label(S),
             action=set_bt_audio),
        Item("Alle trennen",
             action=disconnect_all),
    ]


def scan_devices(S, settings):
    """BT-Geräte scannen via headless_pick."""
    import ipc, time, subprocess
    ipc.write_progress("Bluetooth", "Scanne Geräte (10s) ...", color="blue")
    try:
        subprocess.run(["bluetoothctl","scan","on"], timeout=2,
                       capture_output=True)
        time.sleep(8)
        subprocess.run(["bluetoothctl","scan","off"], timeout=2,
                       capture_output=True)
        r = subprocess.run("bluetoothctl devices | awk '{print $3}'",
                           shell=True, capture_output=True, text=True, timeout=5)
        devices = [d.strip() for d in r.stdout.splitlines() if d.strip()]
    except Exception as e:
        ipc.write_progress("BT Scan", f"Fehler: {e}", color="red")
        time.sleep(2); ipc.clear_progress(); return
    ipc.clear_progress()
    if not devices:
        ipc.write_progress("BT Scan", "Keine Geräte gefunden", color="orange")
        time.sleep(2); ipc.clear_progress()
