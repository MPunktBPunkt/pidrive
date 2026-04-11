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
    """BT-Geräte scannen: timeout-basiert, kein interaktiver bluetoothctl."""
    import ipc, time, subprocess, log
    ipc.write_progress("Bluetooth", "Scanne Geräte (8s) ...", color="blue")
    try:
        # scan on via timeout (nicht interaktiver Modus)
        subprocess.run(
            "timeout 8s bluetoothctl scan on 2>/dev/null || true",
            shell=True, capture_output=True, timeout=12)
        # Gefundene Geräte auflesen
        r = subprocess.run(
            "bluetoothctl devices 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5)
        devices = []
        for line in r.stdout.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) >= 3 and parts[0] == "Device":
                mac  = parts[1]
                name = parts[2] if len(parts) > 2 else mac
                devices.append(f"{name}  ({mac})")
    except Exception as e:
        log.error(f"BT scan: {e}")
        ipc.write_progress("BT Scan", "Scan fehlgeschlagen", color="red")
        time.sleep(2); ipc.clear_progress(); return

    ipc.clear_progress()
    if not devices:
        ipc.write_progress("BT Scan", "Keine Geräte gefunden", color="orange")
        time.sleep(2); ipc.clear_progress(); return

    chosen = ipc.headless_pick("BT Geraete", devices)
    if chosen:
        mac  = chosen.split("(")[-1].rstrip(")")
        name = chosen.split("  (")[0].strip()
        ipc.write_progress("Verbinde", f"{name}...", color="blue")
        log.info(f"BT: verbinde {mac} ({name})")
        ok = False
        try:
            # Erst connect versuchen (bereits gepaart?)
            r = subprocess.run(f"bluetoothctl connect {mac}",
                               shell=True, capture_output=True,
                               text=True, timeout=10)
            ok = "successful" in r.stdout.lower() or "connected" in r.stdout.lower()
        except subprocess.TimeoutExpired:
            pass
        if not ok:
            try:
                # Neu paaren und dann verbinden
                ipc.write_progress("Paare", f"{name}...", color="blue")
                subprocess.run(f"bluetoothctl pair {mac}",
                               shell=True, capture_output=True,
                               text=True, timeout=20)
                r = subprocess.run(f"bluetoothctl connect {mac}",
                                   shell=True, capture_output=True,
                                   text=True, timeout=10)
                ok = "successful" in r.stdout.lower() or "connected" in r.stdout.lower()
            except subprocess.TimeoutExpired:
                pass
        if ok:
            ipc.write_progress("BT", f"Verbunden: {name[:24]}", color="green")
            log.info(f"BT: Verbunden {mac}")
            # Audio automatisch auf BT umschalten
            S["bt_sink_mac"]          = mac
            S["audio_output"]         = "bt"
            settings["audio_output"]  = "bt"
            settings["bt_sink_mac"]   = mac
            settings["alsa_device"]   = f"bluealsa:DEV={mac},PROFILE=a2dp"
            # Laufendes Radio stoppen (wird mit BT-Device neu gestartet)
            if S.get("radio_playing"):
                import webradio as _wr, fm as _fm, dab as _dab
                _wr.stop(S); _fm.stop(S); _dab.stop(S)
                ipc.write_progress("BT", "Radio stoppt — bitte Sender erneut wählen", color="blue")
                log.info("BT: Radio gestoppt für BT-Neustart")
        else:
            ipc.write_progress("BT", "Verbindung fehlgeschlagen", color="red")
            log.warn(f"BT: Verbindung fehlgeschlagen {mac}")
        time.sleep(2)
    ipc.clear_progress()
