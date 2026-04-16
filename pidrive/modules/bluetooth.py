"""
modules/bluetooth.py - Bluetooth Modul
PiDrive - pygame-frei, Status via IPC

v0.8.8:
- _btctl() endlich definiert (war fehlend → NameError bei connect/repair)
- connect_device(): robusters Trust/Pair/Connect mit 3 Versuchen + Verify
- repair_device(): nutzt jetzt _btctl korrekt
- disconnect_current(): setzt Audio-Routing zurück
- scan_devices(): Zombie-Fix mit Popen/terminate
"""

import subprocess
import time
import json
import log
import ipc

C_BT_BLUE = (30, 144, 255)


def _run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _btctl(cmd, timeout=12):
    """Robuster bluetoothctl Wrapper — v0.8.8: endlich definiert."""
    try:
        r = subprocess.run(
            f"bluetoothctl {cmd} 2>&1",
            shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        log.info(f"BT ctl: {cmd} rc={r.returncode} out={out[:180].replace(chr(10), ' | ')}")
        return r.returncode, out
    except subprocess.TimeoutExpired:
        log.warn(f"BT ctl timeout: {cmd}")
        return 124, "timeout"
    except Exception as e:
        log.error(f"BT ctl error: {cmd}: {e}")
        return 1, str(e)


def _ensure_agent():
    """
    Bluetooth-Agent robust initialisieren — v0.8.10.
    Wichtig für Pairing / Default-Agent beim Verbinden im Auto.
    """
    tried = [
        ("agent NoInputNoOutput", 8),
        ("default-agent",         8),
    ]
    ok = False
    last_out = ""
    for cmd, to in tried:
        rc, out = _btctl(cmd, timeout=to)
        last_out = out
        low = out.lower()
        if rc == 0 or "successful" in low or "default agent request successful" in low:
            ok = True
        elif "no agent is registered" in low and cmd.startswith("default-agent"):
            ok = False
            break
    if not ok:
        # Fallback: ältere BlueZ-Variante
        _btctl("agent on", timeout=8)
        rc2, out2 = _btctl("default-agent", timeout=8)
        low2 = out2.lower()
        if rc2 == 0 or "successful" in low2:
            ok = True
            last_out = out2
    if ok:
        log.info("BT agent: bereit")
    else:
        log.warn(f"BT agent: nicht sauber initialisiert: {last_out[:180]}")
    return ok


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _set_pulseaudio_sink(sink_name):
    PA_SOCKET = "PULSE_SERVER=unix:/var/run/pulse/native"
    try:
        for _ in range(8):
            r = subprocess.run(
                PA_SOCKET + " pactl list sinks short 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=3)
            if sink_name in r.stdout:
                break
            time.sleep(1)
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


def bt_toggle(S):
    if S.get("bt"):
        log.info("BT toggle: OFF")
        _bg("bluetoothctl power off; hciconfig hci0 down")
        S["bt"] = False
        S["bt_device"] = ""
        S["bt_status"] = "aus"
    else:
        log.info("BT toggle: ON")
        _bg("rfkill unblock bluetooth; hciconfig hci0 up; bluetoothctl power on")
        S["bt_status"] = "getrennt"
    S["ts"] = 0
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def scan_devices(S, settings):
    ipc.write_progress("Bluetooth", "Scanne Geraete (15s)...", color="blue")
    devices = []
    try:
        _btctl("power on", timeout=8)
        _ensure_agent()

        # Zombie-Fix: Popen/terminate statt kill %1
        bt_proc = subprocess.Popen(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(15)
        try:
            bt_proc.terminate()
            bt_proc.wait(timeout=2)
        except Exception:
            try:
                bt_proc.kill()
            except Exception:
                pass

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
                mac  = p[1]
                name = p[2] if len(p) > 2 else mac
                _, info_out = _btctl(f"info {mac}", timeout=6)
                low = info_out.lower()
                devices.append({
                    "mac":       mac,
                    "name":      name,
                    "known":     mac in known,
                    "paired":    "paired: yes" in low,
                    "connected": "connected: yes" in low,
                    "trusted":   "trusted: yes" in low,
                })
    except Exception as e:
        log.error("BT scan: " + str(e))
        ipc.write_progress("BT Scan", "Scan fehlgeschlagen", color="red")
        time.sleep(2)
        ipc.clear_progress()
        return

    ipc.write_json("/tmp/pidrive_bt_devices.json", {"devices": devices})
    ipc.clear_progress()
    msg = str(len(devices)) + " Geraet(e) — Verbindungen > Geraete"
    ipc.write_progress("BT Scan", msg, color="green" if devices else "orange")
    time.sleep(2)
    ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def connect_device(mac, S, settings):
    name = mac
    try:
        data = json.load(open("/tmp/pidrive_bt_devices.json"))
        for d in data.get("devices", []):
            if d.get("mac") == mac:
                name = d.get("name", mac)
                break
    except Exception:
        pass

    ipc.write_progress("Bluetooth", f"Verbinde {name[:20]}...", color="blue")
    log.info(f"BT connect: START mac={mac} name={name}")

    S["bt"] = False
    S["bt_status"] = "verbindet"
    S["menu_rev"] = S.get("menu_rev", 0) + 1

    ok = False

    _btctl("power on", timeout=8)
    _ensure_agent()

    # Trust → Pair → Connect (3 Versuche)
    attempts = [
        ("trust",   f"trust {mac}",   8),
        ("pair",    f"pair {mac}",   30),
        ("connect", f"connect {mac}", 15),
        ("connect", f"connect {mac}", 15),
        ("connect", f"connect {mac}", 20),
    ]

    for step_name, cmd, to in attempts:
        rc, out = _btctl(cmd, timeout=to)
        low = out.lower()

        if step_name == "pair":
            if any(x in low for x in ["successful", "paired: yes",
                                       "alreadyexists", "already paired",
                                       "device has been paired"]):
                log.info(f"BT connect: PAIR ok mac={mac}")
            else:
                log.warn(f"BT connect: PAIR unsicher mac={mac} out={out[:180]}")

        elif step_name == "trust":
            if any(x in low for x in ["succeeded", "trust succeeded", "changing"]):
                log.info(f"BT connect: TRUST ok mac={mac}")

        elif step_name == "connect":
            if any(x in low for x in ["successful", "connection successful",
                                       "connected: yes", "already connected"]):
                ok = True
                log.info(f"BT connect: CONNECT ok mac={mac}")
                break
            else:
                log.warn(f"BT connect: CONNECT fehlgeschlagen mac={mac} out={out[:180]}")
                time.sleep(2)

    # Verify
    if ok:
        _, info_out = _btctl(f"info {mac}", timeout=8)
        if "connected: yes" not in info_out.lower():
            log.warn(f"BT connect: VERIFY failed mac={mac}")
            ok = False

    if not ok:
        S["bt"] = False
        S["bt_status"] = "getrennt"
        ipc.write_progress("Bluetooth", "Verbindung fehlgeschlagen", color="red")
        log.warn(f"BT connect: FAIL mac={mac} name={name}")
        time.sleep(3)
        ipc.clear_progress()
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    # Erfolg
    S["bt"]         = True
    S["bt_device"]  = name
    S["bt_status"]  = "verbunden"
    S["bt_sink_mac"] = mac
    S["bt_pa_sink"]  = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"

    settings["bt_last_mac"]  = mac
    settings["bt_last_name"] = name
    settings["bt_sink_mac"]  = mac
    settings["bt_pa_sink"]   = S["bt_pa_sink"]
    settings["audio_output"] = "bt"
    settings["alsa_device"]  = "default"

    log.info(f"BT connect: STATE mac={mac} sink={S['bt_pa_sink']}")
    _set_pulseaudio_sink(S["bt_pa_sink"])
    _set_raspotify_device("default")

    # Radio nach BT-Connect neu starten
    if S.get("radio_playing"):
        try:
            now  = time.time()
            last = getattr(connect_device, "_last_restart_ts", 0)
            if now - last > 5:
                connect_device._last_restart_ts = now
                with open("/tmp/pidrive_cmd", "w") as cf:
                    cf.write("radio_restart_on_bt\n")
                log.info("BT connect: radio_restart_on_bt ausgelöst")
        except Exception as e:
            log.warn(f"BT connect: radio restart failed: {e}")

    ipc.write_progress("Bluetooth", f"Verbunden: {name[:22]}", color="green")
    time.sleep(2)
    ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    log.info(f"BT connect: DONE mac={mac} name={name}")
    return True


def disconnect_current(S, settings):
    mac  = settings.get("bt_last_mac", "") or S.get("bt_sink_mac", "")
    name = S.get("bt_device", "") or settings.get("bt_last_name", "") or mac or "BT-Gerät"

    ipc.write_progress("Bluetooth", f"Trenne {name[:20]}...", color="orange")
    log.info(f"BT disconnect: START mac={mac} name={name}")

    if mac:
        rc, out = _btctl(f"disconnect {mac}", timeout=12)
        ok = any(x in out.lower() for x in ["successful", "not connected"]) or rc == 0
    else:
        ok = True
        log.warn("BT disconnect: keine MAC, nur Status-Reset")

    S["bt"]         = False
    S["bt_device"]  = ""
    S["bt_sink_mac"] = ""
    S["bt_pa_sink"]  = ""
    S["bt_status"]   = "getrennt"

    if settings.get("audio_output") == "bt":
        settings["audio_output"] = "klinke"

    try:
        from modules import audio as _a
        _a.set_output("klinke", settings)
    except Exception as e:
        log.warn(f"BT disconnect: audio fallback: {e}")

    ipc.write_progress("Bluetooth", "Getrennt" if ok else "Getrennt/unbestätigt",
                       color="green" if ok else "orange")
    time.sleep(2)
    ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    log.info(f"BT disconnect: DONE mac={mac}")
    return True


def repair_device(mac, S, settings):
    name = mac
    try:
        data = json.load(open("/tmp/pidrive_bt_devices.json"))
        for d in data.get("devices", []):
            if d.get("mac") == mac:
                name = d.get("name", mac)
                break
    except Exception:
        pass

    ipc.write_progress("Bluetooth", f"Neu koppeln: {name[:18]}...", color="blue")
    log.info(f"BT repair: START mac={mac} name={name}")

    _btctl("power on", timeout=8)
    _ensure_agent()
    _btctl(f"disconnect {mac}", timeout=10)
    _btctl(f"remove {mac}",     timeout=10)
    time.sleep(2)

    ok = connect_device(mac, S, settings)
    log.info(f"BT repair: {'OK' if ok else 'FAIL'} mac={mac}")
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    return ok


def reconnect_last(S, settings):
    mac  = settings.get("bt_last_mac", "")
    name = settings.get("bt_last_name", "") or mac

    if not mac:
        ipc.write_progress("Bluetooth", "Kein letztes Gerät", color="orange")
        log.warn("BT reconnect_last: keine bt_last_mac")
        time.sleep(2)
        ipc.clear_progress()
        return False

    S["bt_status"] = "verbindet"
    S["menu_rev"]  = S.get("menu_rev", 0) + 1
    log.info(f"BT reconnect_last: START mac={mac} name={name}")
    return connect_device(mac, S, settings)


def get_bt_sink():
    """PulseAudio BT-Sink ermitteln."""
    PA_SOCKET = "PULSE_SERVER=unix:/var/run/pulse/native"
    try:
        r = subprocess.run(
            PA_SOCKET + " pactl list sinks short 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "bluez" in line.lower() or "a2dp" in line.lower():
                return line.split()[0] if line.split() else ""
    except Exception:
        pass
    return ""
