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


def _set_pulseaudio_sink(sink_name):
    """PulseAudio Default-Sink setzen (fuer BT A2DP).
    Wechselt automatisch Spotify und Radio auf BT-Kopfhörer."""
    import subprocess, time
    PA_SOCKET = "PULSE_SERVER=unix:/var/run/pulse/native"
    try:
        # Kurz warten bis BT-Sink erscheint
        for _ in range(5):
            r = subprocess.run(
                PA_SOCKET + " pactl list sinks short 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=3)
            if sink_name in r.stdout:
                break
            time.sleep(1)
        # Default-Sink setzen
        r = subprocess.run(
            PA_SOCKET + " pactl set-default-sink " + sink_name,
            shell=True, capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            log.info("PulseAudio: Default-Sink=" + sink_name)
        else:
            log.warn("PulseAudio sink nicht gefunden: " + sink_name)
    except Exception as e:
        log.error("PulseAudio sink-Fehler: " + str(e))


def _set_raspotify_device(device, restart=True):
    """Raspotify LIBRESPOT_DEVICE in /etc/raspotify/conf setzen."""
    conf = "/etc/raspotify/conf"
    try:
        try:
            with open(conf) as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            log.warn("Raspotify: /etc/raspotify/conf nicht gefunden")
            return
        new_lines = []
        replaced = False
        for line in lines:
            if line.startswith("LIBRESPOT_DEVICE="):
                new_lines.append("LIBRESPOT_DEVICE=" + device + "\n")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            new_lines.append("LIBRESPOT_DEVICE=" + device + "\n")
        with open(conf, "w") as fh:
            fh.writelines(new_lines)
        log.info("Raspotify: LIBRESPOT_DEVICE=" + device)
        if restart:
            subprocess.run(["systemctl", "restart", "raspotify"],
                           capture_output=True, timeout=10)
            log.info("Raspotify: neu gestartet")
    except Exception as e:
        log.error("Raspotify Device-Wechsel fehlgeschlagen: " + str(e))

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
    """BT-Geraete scannen, Ergebnis in JSON speichern (-> Submenu)."""
    import ipc, time, json, subprocess
    ipc.write_progress("Bluetooth", "Scanne Geraete (8s)...", color="blue")
    devices = []
    try:
        subprocess.run("timeout 8s bluetoothctl scan on 2>/dev/null || true",
                       shell=True, capture_output=True, timeout=12)
        r_paired = subprocess.run("bluetoothctl paired-devices 2>/dev/null",
                                  shell=True, capture_output=True, text=True, timeout=5)
        known = {ln.split()[1] for ln in r_paired.stdout.splitlines()
                 if ln.startswith("Device") and len(ln.split()) >= 2}
        r_all = subprocess.run("bluetoothctl devices 2>/dev/null",
                               shell=True, capture_output=True, text=True, timeout=5)
        for line in r_all.stdout.splitlines():
            p = line.strip().split(" ", 2)
            if len(p) >= 2 and p[0] == "Device":
                mac = p[1]; name = p[2] if len(p) > 2 else mac
                devices.append({"mac": mac, "name": name, "known": mac in known})
    except Exception as e:
        log.error("BT scan: " + str(e))
        ipc.write_progress("BT Scan", "Scan fehlgeschlagen", color="red")
        time.sleep(2); ipc.clear_progress(); return

    ipc.write_json("/tmp/pidrive_bt_devices.json", {"devices": devices})
    ipc.clear_progress()
    msg = str(len(devices)) + " Geraet(e) — Verbindungen > Geraete"
    ipc.write_progress("BT Scan", msg, color="green" if devices else "orange")
    time.sleep(2); ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def connect_device(mac, S, settings):
    """BT-Geraet verbinden (wird aus Submenu-Aktion aufgerufen)."""
    import ipc, time, subprocess
    name = mac
    try:
        import json
        data = json.load(open("/tmp/pidrive_bt_devices.json"))
        for d in data.get("devices", []):
            if d["mac"] == mac:
                name = d["name"]; break
    except Exception:
        pass

    ipc.write_progress("Verbinde", name[:22] + "...", color="blue")
    log.info("BT: verbinde " + mac + " (" + name + ")")
    ok = False
    for attempt in range(2):
        try:
            if attempt == 1:
                subprocess.run("bluetoothctl pair " + mac,
                               shell=True, capture_output=True, text=True, timeout=20)
                subprocess.run("bluetoothctl trust " + mac,
                               shell=True, capture_output=True, text=True, timeout=5)
            r = subprocess.run("bluetoothctl connect " + mac,
                               shell=True, capture_output=True, text=True, timeout=10)
            ok = "successful" in r.stdout.lower() or "connected" in r.stdout.lower()
            if ok:
                break
        except subprocess.TimeoutExpired:
            pass

    if ok:
        ipc.write_progress("BT", "Verbunden: " + name[:24], color="green")
        log.info("BT: Verbunden " + mac)
        bt_sink = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
        S["bt_sink_mac"]         = mac
        S["bt_pa_sink"]          = bt_sink
        S["bt_device"]           = name
        S["audio_output"]        = "bt"
        settings["audio_output"] = "bt"
        settings["bt_sink_mac"]  = mac
        settings["bt_pa_sink"]   = bt_sink
        settings["alsa_device"]  = "default"
        _set_pulseaudio_sink(bt_sink)
        _set_raspotify_device("default")
        if S.get("radio_playing"):
            try:
                import webradio as _wr, fm as _fm, dab as _dab
                _wr.stop(S); _fm.stop(S); _dab.stop(S)
            except Exception:
                pass
    else:
        ipc.write_progress("BT", "Verbindung fehlgeschlagen", color="red")
        log.warn("BT: Verbindung fehlgeschlagen " + mac)
    time.sleep(2)
    ipc.clear_progress()


