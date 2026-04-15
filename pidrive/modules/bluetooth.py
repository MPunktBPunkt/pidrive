"""
modules/bluetooth.py - Bluetooth Modul
PiDrive v0.6.1 — pygame-frei, Status via IPC
"""

import subprocess
import time
import log
import ipc

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


def scan_devices(S, settings):
    """BT-Geraete scannen, Ergebnis in JSON speichern (-> Submenu)."""
    import ipc, time, json, subprocess
    ipc.write_progress("Bluetooth", "Scanne Geraete (15s)...", color="blue")
    devices = []
    try:
        # scan on für 15s — explizit als Prozess starten und beenden
        import os, signal as _sig
        _bt_proc = subprocess.Popen(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(15)
        try:
            _bt_proc.terminate()
            _bt_proc.wait(timeout=2)
        except Exception:
            try: _bt_proc.kill()
            except Exception: pass
        # Sicherstellen dass kein bluetoothctl scan hängt
        subprocess.run("pkill -f 'bluetoothctl scan' 2>/dev/null",
                       shell=True, capture_output=True)
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
    """BT-Geraet pairen/trusten/verbinden und Audio-Routing setzen."""
    import ipc, time, subprocess as _sp, json

    name = mac
    try:
        data = json.load(open("/tmp/pidrive_bt_devices.json"))
        for d in data.get("devices", []):
            if d.get("mac") == mac:
                name = d.get("name", mac); break
    except Exception:
        pass

    ipc.write_progress("Bluetooth", f"Verbinde {name[:20]}...", color="blue")
    log.info(f"BT connect: START mac={mac} name={name}")

    ok = False
    _btctl("power on",       timeout=8)
    _btctl("agent on",       timeout=8)
    _btctl("default-agent",  timeout=8)

    for step, cmd, to in [
        ("trust",   f"trust {mac}",   8),
        ("pair",    f"pair {mac}",   25),
        ("connect", f"connect {mac}", 15),
        ("connect", f"connect {mac}", 15),
    ]:
        rc, out = _btctl(cmd, timeout=to)
        low = out.lower()
        if step == "pair":
            if any(x in low for x in ["successful","paired: yes","alreadyexists",
                                       "already paired","device has been paired"]):
                log.info(f"BT connect: PAIR ok mac={mac}")
        elif step == "trust":
            if any(x in low for x in ["succeeded","trust succeeded","changing"]):
                log.info(f"BT connect: TRUST ok mac={mac}")
        elif step == "connect":
            if any(x in low for x in ["successful","connection successful",
                                       "connected: yes","already connected"]):
                ok = True
                log.info(f"BT connect: CONNECT ok mac={mac}"); break
            log.warn(f"BT connect: CONNECT fehlgeschlagen mac={mac} out={out[:120]}")
            time.sleep(2)

    if ok:
        _, info = _btctl(f"info {mac}", timeout=8)
        if "connected: yes" not in info.lower():
            log.warn(f"BT connect: VERIFY failed mac={mac}")
            ok = False

    if not ok:
        ipc.write_progress("Bluetooth", "Verbindung fehlgeschlagen", color="red")
        log.warn(f"BT connect: FAIL mac={mac} name={name}")
        time.sleep(3); ipc.clear_progress()
        return False

    S["bt"]           = True
    S["bt_device"]    = name
    S["bt_sink_mac"]  = mac
    S["bt_pa_sink"]   = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
    settings["bt_last_mac"]  = mac
    settings["bt_last_name"] = name
    settings["bt_sink_mac"]  = mac
    settings["bt_pa_sink"]   = S["bt_pa_sink"]
    settings["audio_output"] = "bt"
    settings["alsa_device"]  = "default"

    log.info(f"BT connect: STATE mac={mac} sink={S['bt_pa_sink']}")
    _set_pulseaudio_sink(S["bt_pa_sink"])
    _set_raspotify_device("default")

    time.sleep(2)
    sinks = _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null")
    if S["bt_pa_sink"] in sinks:
        log.info(f"BT connect: PulseAudio sink aktiv")
    else:
        log.warn(f"BT connect: PulseAudio sink noch nicht sichtbar")

    if S.get("radio_playing"):
        try:
            now = time.time()
            if now - getattr(connect_device, "_last_restart", 0) > 5:
                connect_device._last_restart = now
                with open("/tmp/pidrive_cmd","w") as _cf:
                    _cf.write("radio_restart_on_bt\n")
                log.info("BT connect: radio_restart_on_bt ausgelöst")
        except Exception as e:
            log.warn(f"BT connect: radio restart failed: {e}")

    ipc.write_progress("Bluetooth", f"Verbunden: {name[:22]}", color="green")
    time.sleep(2); ipc.clear_progress()
    log.info(f"BT connect: DONE mac={mac} name={name}")
    return True


def disconnect_current(S, settings):
    """Aktuelles BT-Gerät trennen."""
    import ipc, time
    mac  = settings.get("bt_last_mac","") or S.get("bt_sink_mac","")
    name = S.get("bt_device","") or settings.get("bt_last_name","") or mac or "BT-Gerät"

    ipc.write_progress("Bluetooth", f"Trenne {name[:20]}...", color="orange")
    log.info(f"BT disconnect: START mac={mac} name={name}")

    if mac:
        rc, out = _btctl(f"disconnect {mac}", timeout=12)
        ok = any(x in out.lower() for x in ["successful","not connected"]) or rc == 0
    else:
        ok = True
        log.warn("BT disconnect: keine MAC, nur Status-Reset")

    S["bt_device"]   = ""
    S["bt_sink_mac"] = ""
    S["bt_pa_sink"]  = ""
    if settings.get("audio_output") == "bt":
        settings["audio_output"] = "klinke"
    try:
        from modules import audio as _a
        _a.set_output("klinke", settings)
    except Exception as e:
        log.warn(f"BT disconnect: audio fallback: {e}")

    ipc.write_progress("Bluetooth", "Getrennt" if ok else "Getrennt/unbestätigt",
                       color="green" if ok else "orange")
    time.sleep(2); ipc.clear_progress()
    log.info(f"BT disconnect: DONE mac={mac}")
    return True


def repair_device(mac, S, settings):
    """Gerät entkoppeln und neu verbinden."""
    import ipc, time, json
    name = mac
    try:
        data = json.load(open("/tmp/pidrive_bt_devices.json"))
        for d in data.get("devices",[]):
            if d.get("mac") == mac:
                name = d.get("name", mac); break
    except Exception:
        pass

    ipc.write_progress("Bluetooth", f"Neu koppeln: {name[:18]}...", color="blue")
    log.info(f"BT repair: START mac={mac} name={name}")
    _btctl("power on", timeout=8)
    _btctl(f"disconnect {mac}", timeout=10)
    _btctl(f"remove {mac}", timeout=10)
    time.sleep(2)
    ok = connect_device(mac, S, settings)
    log.info(f"BT repair: {'OK' if ok else 'FAIL'} mac={mac}")
    return ok


def reconnect_last(S, settings):
    """Letztes bekanntes BT-Gerät verbinden."""
    import ipc, time
    mac  = settings.get("bt_last_mac","")
    name = settings.get("bt_last_name","") or mac

    if not mac:
        ipc.write_progress("Bluetooth", "Kein letztes Gerät", color="orange")
        log.warn("BT reconnect_last: keine bt_last_mac")
        time.sleep(2); ipc.clear_progress()
        return False

    log.info(f"BT reconnect_last: START mac={mac} name={name}")
    return connect_device(mac, S, settings)
