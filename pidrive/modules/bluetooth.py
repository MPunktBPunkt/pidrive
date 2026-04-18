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
    Bluetooth-Agent via einzigem persistenten bluetoothctl-Prozess — v0.8.14.

    Problem vorher (v0.8.13): _btctl() startet pro Befehl einen neuen Subprocess.
    Agent wird in Subprocess A registriert, ist aber in Subprocess B nicht mehr da.
    → "No agent is registered" bei default-agent im nächsten _btctl()-Call.

    Fix: agent-Registrierung + default-agent in einem einzigen Prozess via stdin-pipe.
    """
    try:
        proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        cmds = "agent NoInputNoOutput\ndefault-agent\n"
        try:
            out, _ = proc.communicate(input=cmds, timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            out = ""

        low = out.lower()
        if "default agent request successful" in low or "default agent" in low:
            log.info("BT agent: bereit (persistenter Prozess)")
            return True
        # Fallback: agent on statt NoInputNoOutput
        proc2 = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            out2, _ = proc2.communicate(input="agent on\ndefault-agent\n", timeout=10)
        except subprocess.TimeoutExpired:
            proc2.kill()
            out2 = ""
        if "default agent" in out2.lower():
            log.info("BT agent: bereit (fallback agent on)")
            return True
        log.warn("BT agent: default-agent nicht bestätigt — Verbindung trotzdem versuchen")
        return True  # weiter versuchen, auch wenn Agent unsicher
    except Exception as e:
        log.warn("BT agent: Fehler: " + str(e))
        return False


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

    # v0.8.13: Scanner stoppen vor Connect — verhindert RTL-/Status-Kollision
    try:
        from modules import scanner as _scanner
        if S.get("radio_type") == "SCANNER":
            log.info("BT connect: stoppe Scanner vor Connect")
            _scanner.stop(S)
            import time as _t; _t.sleep(0.5)
    except Exception as e:
        log.warn("BT connect: scanner stop failed: " + str(e))

    S["bt"] = False
    S["bt_status"] = "verbindet"
    S["menu_rev"] = S.get("menu_rev", 0) + 1

    ok = False

    _btctl("power on", timeout=8)
    _ensure_agent()

    # v0.8.14: Prüfen ob BlueZ das Gerät kennt — sonst kurzen Discovery-Scan starten
    # "Device not available" tritt auf wenn BlueZ die MAC nicht in seiner Datenbank hat
    rc_info, out_info = _btctl(f"info {mac}", timeout=6)
    device_known = (rc_info == 0 and "Device" in out_info and "not available" not in out_info)

    if not device_known:
        log.info(f"BT connect: Gerät {mac} unbekannt — kurzer Discovery-Scan (10s)")
        ipc.write_progress("Bluetooth", "Suche Gerät...", color="blue")
        # Kurzen Scan starten damit BlueZ das Gerät findet
        proc_scan = subprocess.Popen(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import time as _ts; _ts.sleep(10)
        try:
            proc_scan.terminate()
        except Exception:
            pass
        # Nochmal prüfen
        rc_info2, out_info2 = _btctl(f"info {mac}", timeout=6)
        device_known = (rc_info2 == 0 and "Device" in out_info2 and "not available" not in out_info2)
        if device_known:
            log.info(f"BT connect: Gerät {mac} nach Scan gefunden")
        else:
            log.warn(f"BT connect: Gerät {mac} auch nach Scan nicht bekannt — Pairing nötig")
            ipc.write_progress("Bluetooth", "Gerät nicht gefunden — Pairing-Modus nötig", color="orange")
            import time as _tw; _tw.sleep(3)
            ipc.clear_progress()
            # Trotzdem versuchen — vielleicht klappt pair
    else:
        log.info(f"BT connect: Gerät {mac} BlueZ bekannt")

    # v0.8.13: sauberer Zustand vor Connect — alten Verbindungsstatus aufräumen
    _btctl(f"disconnect {mac}", timeout=8)
    import time as _t2; _t2.sleep(1)

    # v0.8.15: Paired-Status prüfen — bei Paired:no erst remove, dann frisch pairen
    # AuthenticationFailed tritt auf wenn Pi keine Keys hat, Kopfhörer aber schon
    _, info_pre = _btctl(f"info {mac}", timeout=6)
    if "paired: no" in info_pre.lower() and "name:" in info_pre.lower():
        log.info(f"BT connect: Paired:no erkannt — entferne Gerät für sauberes Neu-Pairing mac={mac}")
        ipc.write_progress("Bluetooth", "Kopplung erneuern...", color="blue")
        _btctl(f"remove {mac}", timeout=10)
        time.sleep(2)

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
            elif "authenticationfailed" in low or "authentication failed" in low:
                # v0.8.15: AuthenticationFailed → Keys inkompatibel → remove + Hinweis
                log.warn(f"BT connect: AuthenticationFailed — Kopfhörer in Pairing-Modus bringen mac={mac}")
                ipc.write_progress("Bluetooth", "Pairing-Modus am Kopfhörer nötig!", color="orange")
                _btctl(f"remove {mac}", timeout=10)
                time.sleep(1)
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


# ── Auto-Reconnect Watcher ───────────────────────────────────────────────────

_reconnect_thread = None
_reconnect_stop   = False


def start_auto_reconnect(S, settings):
    """
    Startet einen Hintergrund-Watcher der alle 30s prüft ob das letzte
    BT-Gerät erreichbar ist und ggf. automatisch verbindet.
    Phase 3 Feature: "Kopfhörer wird eingeschaltet → PiDrive verbindet"
    """
    global _reconnect_thread, _reconnect_stop
    if _reconnect_thread and _reconnect_thread.is_alive():
        return
    _reconnect_stop = False
    import threading as _th

    def _watcher():
        import time as _t
        _t.sleep(15)  # Kurze Startpause
        while not _reconnect_stop:
            try:
                mac  = settings.get("bt_last_mac", "")
                name = settings.get("bt_last_name", "")
                if mac and not S.get("bt", False):
                    rc, out = _btctl(f"info {mac}", timeout=5)
                    low = out.lower()
                    if rc == 0 and "name:" in low and "connected: no" in low:
                        log.info(f"BT auto-reconnect: Gerät sichtbar, versuche Connect mac={mac}")
                        # Kein aggressives repair — nur connect versuchen
                        rc2, out2 = _btctl(f"connect {mac}", timeout=15)
                        low2 = out2.lower()
                        if any(x in low2 for x in ["successful", "connected: yes"]):
                            log.info(f"BT auto-reconnect: ERFOLG mac={mac} name={name}")
                            S["bt"]         = True
                            S["bt_device"]  = name
                            S["bt_status"]  = "verbunden"
                            S["bt_sink_mac"] = mac
                            S["bt_pa_sink"]  = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
                            settings["audio_output"] = "bt"
                            from modules import audio as _aud
                            _aud.get_mpv_args(settings, source="bt_auto_reconnect")
                        else:
                            log.info(f"BT auto-reconnect: fehlgeschlagen mac={mac} ({out2[:80]})")
            except Exception as e:
                log.warn("BT auto-reconnect Watcher: " + str(e))
            _t.sleep(30)

    _reconnect_thread = _th.Thread(target=_watcher, daemon=True, name="bt_auto_reconnect")
    _reconnect_thread.start()
    log.info("BT auto-reconnect: Watcher gestartet (30s Intervall)")


def stop_auto_reconnect():
    global _reconnect_stop
    _reconnect_stop = True


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
