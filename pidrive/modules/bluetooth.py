"""
modules/bluetooth.py - Bluetooth Modul
PiDrive v0.9.14-final - persistent agent lifecycle + known devices + reconnect

Ziele:
- persistenter bluetoothctl-Agent statt kurzlebiger Einmal-Prozesse
- bekannte Geräte dedupliziert aus:
  - persistenter known-Datei
  - BlueZ-DB (/var/lib/bluetooth)
  - bluetoothctl paired-devices
- Reconnect bekannter Geräte mit Priorität + Cooldown
- BT-Scan speichert bekannte / gepaarte Geräte fortlaufend

Wichtige Hintergrundprobleme:
- bluetoothctl scan on ohne Filter zeigt viele BLE-Geräte mit random MACs,
  die für A2DP irrelevant sind [2]
- der bisherige Agent war nicht persistent genug [2]
"""

import subprocess
import time
import json
import threading
import os
import log
import ipc

# Lock verhindert parallele connect_device()-Calls (repair + connect race)
_bt_connect_lock = threading.Lock()

KNOWN_BT_FILE = "/tmp/pidrive_bt_known_devices.json"
AGENT_STATE_FILE = "/tmp/pidrive_bt_agent.json"

_AGENT_PROC = None
_AGENT_LOCK = threading.Lock()

_RECONNECT_LAST_TRY = {}
_RECONNECT_COOLDOWN = 45  # Sekunden pro Gerät

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

C_BT_BLUE = (30, 144, 255)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _now():
    return int(time.time())


def _write_json_atomic(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log.warn(f"BT json write {path}: {e}")


def _run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _btctl(cmd, timeout=12):
    """Robuster bluetoothctl Wrapper."""
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


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Agent State
# ──────────────────────────────────────────────────────────────────────────────

def _write_agent_state(running=False, ready=False, pid=0, last_error="",
                       started_ts=0, health_ok=False):
    if running and not started_ts:
        started_ts = _now()
    _write_json_atomic(AGENT_STATE_FILE, {
        "running": running,
        "ready": ready,
        "pid": pid,
        "started_ts": started_ts,
        "last_error": last_error,
        "health_ok": health_ok,
        "ts": _now(),
    })


def read_agent_state():
    try:
        with open(AGENT_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def agent_is_alive():
    global _AGENT_PROC
    try:
        return _AGENT_PROC is not None and _AGENT_PROC.poll() is None
    except Exception:
        return False


def start_agent_session():
    """
    Persistente bluetoothctl-Agent-Session.
    Behebt die Architektur-Schwäche aus BTError.md [2].
    """
    global _AGENT_PROC
    with _AGENT_LOCK:
        if agent_is_alive():
            st = read_agent_state()
            _write_agent_state(
                running=True,
                ready=st.get("ready", True),
                pid=_AGENT_PROC.pid,
                last_error=st.get("last_error", ""),
                started_ts=st.get("started_ts", _now()),
                health_ok=True
            )
            return True

        try:
            _AGENT_PROC = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            _AGENT_PROC.stdin.write("agent NoInputNoOutput\n")
            _AGENT_PROC.stdin.write("default-agent\n")
            _AGENT_PROC.stdin.flush()
            time.sleep(1.0)

            _write_agent_state(
                running=True,
                ready=True,
                pid=_AGENT_PROC.pid,
                last_error="",
                started_ts=_now(),
                health_ok=True
            )
            log.info(f"BT agent: persistent session ready pid={_AGENT_PROC.pid}")
            return True

        except Exception as e:
            _AGENT_PROC = None
            _write_agent_state(
                running=False,
                ready=False,
                pid=0,
                last_error=str(e),
                started_ts=0,
                health_ok=False
            )
            log.warn("BT agent start: " + str(e))
            return False


def stop_agent_session():
    global _AGENT_PROC
    with _AGENT_LOCK:
        if _AGENT_PROC:
            try:
                _AGENT_PROC.terminate()
                _AGENT_PROC.wait(timeout=3)
            except Exception:
                try:
                    _AGENT_PROC.kill()
                except Exception:
                    pass
            _AGENT_PROC = None

        _write_agent_state(
            running=False,
            ready=False,
            pid=0,
            last_error="",
            started_ts=0,
            health_ok=False
        )
        log.info("BT agent: session stopped")


def agent_healthcheck():
    """
    Einfacher Health-Check:
    - Prozess lebt?
    - Statusdatei aktualisieren
    """
    alive = agent_is_alive()
    st = read_agent_state()

    if alive:
        _write_agent_state(
            running=True,
            ready=st.get("ready", True),
            pid=_AGENT_PROC.pid if _AGENT_PROC else st.get("pid", 0),
            last_error=st.get("last_error", ""),
            started_ts=st.get("started_ts", _now()),
            health_ok=True
        )
        return True

    _write_agent_state(
        running=False,
        ready=False,
        pid=0,
        last_error=st.get("last_error", "agent_dead"),
        started_ts=0,
        health_ok=False
    )
    return False


def start_agent_health_thread():
    """
    Leichter Health-Check-Thread:
    - prüft alle 20s, ob Agent noch lebt
    - startet Agent bei Bedarf neu
    """
    import threading as _th

    def _loop():
        while True:
            try:
                if not agent_healthcheck():
                    log.warn("BT agent health: dead — restart")
                    start_agent_session()
            except Exception as e:
                log.warn("BT agent health: " + str(e))
            time.sleep(20)

    _th.Thread(target=_loop, daemon=True, name="bt_agent_health").start()


def pair_with_agent(mac, timeout=45):
    global _AGENT_PROC
    if not start_agent_session():
        return False, "agent_start_failed"

    try:
        _AGENT_PROC.stdin.write(f"pair {mac}\n")
        _AGENT_PROC.stdin.flush()

        end = time.time() + timeout
        lines = []

        while time.time() < end:
            line = _AGENT_PROC.stdout.readline()
            if not line:
                time.sleep(0.2)
                continue

            lines.append(line.strip())
            low = line.lower()

            if ("pairing successful" in low or
                "device has been paired" in low or
                "already paired" in low or
                "already exists" in low or
                "successful" in low):
                _write_agent_state(
                    running=True,
                    ready=True,
                    pid=_AGENT_PROC.pid,
                    last_error="",
                    started_ts=read_agent_state().get("started_ts", _now()),
                    health_ok=True
                )
                return True, "\n".join(lines[-25:])

            if "authenticationfailed" in low or "failed" in low:
                _write_agent_state(
                    running=True,
                    ready=False,
                    pid=_AGENT_PROC.pid,
                    last_error=line.strip(),
                    started_ts=read_agent_state().get("started_ts", _now()),
                    health_ok=False
                )
                return False, "\n".join(lines[-25:])

        _write_agent_state(
            running=True,
            ready=False,
            pid=_AGENT_PROC.pid,
            last_error="pair_timeout",
            started_ts=read_agent_state().get("started_ts", _now()),
            health_ok=False
        )
        return False, "\n".join(lines[-25:])

    except Exception as e:
        _write_agent_state(
            running=False,
            ready=False,
            pid=0,
            last_error=str(e),
            started_ts=0,
            health_ok=False
        )
        return False, str(e)


def _ensure_agent():
    return start_agent_session()


# ──────────────────────────────────────────────────────────────────────────────
# Known devices
# ──────────────────────────────────────────────────────────────────────────────

def _read_known_devices():
    try:
        with open(KNOWN_BT_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("devices", [])
    except Exception:
        return []


def _dedupe_devices(devs):
    out = []
    seen = set()
    for d in devs or []:
        mac = (d.get("mac") or "").upper()
        if not mac or mac in seen:
            continue
        seen.add(mac)
        row = dict(d)
        row["mac"] = mac
        out.append(row)
    return out


def _write_known_devices(devs):
    _write_json_atomic(KNOWN_BT_FILE, {
        "devices": _dedupe_devices(devs),
        "ts": _now()
    })


def _load_bluez_db_devices():
    """
    Bekannte Geräte direkt aus /var/lib/bluetooth laden [2].
    """
    base = "/var/lib/bluetooth"
    result = []

    try:
        if not os.path.isdir(base):
            return []

        for adapter in os.listdir(base):
            ap = os.path.join(base, adapter)
            if not os.path.isdir(ap):
                continue

            for mac in os.listdir(ap):
                dp = os.path.join(ap, mac)
                infof = os.path.join(dp, "info")
                if not os.path.isfile(infof):
                    continue

                name = mac
                paired = False
                trusted = False

                try:
                    with open(infof, "r", encoding="utf-8", errors="ignore") as f:
                        txt = f.read()
                    for ln in txt.splitlines():
                        if ln.startswith("Name="):
                            name = ln.split("=", 1)[1].strip() or mac
                        elif ln.startswith("Trusted="):
                            trusted = ln.split("=", 1)[1].strip().lower() == "true"
                    paired = ("[LinkKey]" in txt or
                              "[LongTermKey]" in txt or
                              "SupportedTechnologies=BR/EDR;" in txt)
                except Exception:
                    pass

                result.append({
                    "mac": mac,
                    "name": name,
                    "known": True,
                    "paired": paired,
                    "trusted": trusted,
                    "source": "bluez_db",
                })
    except Exception as e:
        log.warn("BT BlueZ-DB lesen: " + str(e))

    return _dedupe_devices(result)


def _get_known_devices():
    """
    Dedup aus:
    - persistenter known-Datei
    - BlueZ-DB
    - bluetoothctl paired-devices
    """
    result = []
    result.extend(_read_known_devices())
    result.extend(_load_bluez_db_devices())

    try:
        rp = _btctl("paired-devices", timeout=8)[1]
        for ln in rp.splitlines():
            p = ln.strip().split(" ", 2)
            if len(p) >= 2 and p[0] == "Device":
                result.append({
                    "mac": p[1],
                    "name": p[2] if len(p) > 2 else p[1],
                    "known": True,
                    "paired": True,
                    "source": "paired_devices",
                })
    except Exception:
        pass

    result = _dedupe_devices(result)
    _write_known_devices(result)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Scan filters / routing
# ──────────────────────────────────────────────────────────────────────────────

def _is_audio_device_info(info_out: str) -> bool:
    low = (info_out or "").lower()
    return (
        "0000110b" in low or
        "0000110e" in low or
        "audio sink" in low or
        "headset" in low or
        "headphone" in low or
        "a/v remote control" in low or
        "class:" in low
    )


def _is_public_or_bredr(info_out: str) -> bool:
    low = (info_out or "").lower()
    return "(public)" in low or "bredr" in low or "br/edr" in low or "class:" in low


def _set_pulseaudio_sink(sink_name):
    PA_SOCKET = "PULSE_SERVER=unix:/var/run/pulse/native"
    try:
        for _ in range(8):
            r = subprocess.run(
                PA_SOCKET + " pactl list sinks short 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=3
            )
            if sink_name in r.stdout:
                break
            time.sleep(1)

        r = subprocess.run(
            PA_SOCKET + " pactl set-default-sink " + sink_name,
            shell=True, capture_output=True, text=True, timeout=5
        )
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


# ──────────────────────────────────────────────────────────────────────────────
# Public functions
# ──────────────────────────────────────────────────────────────────────────────

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
    ipc.write_progress("Bluetooth", "Scanne Geraete (25s)...", color="blue")
    devices = []
    known_devices = _get_known_devices()
    known_map = {d["mac"].upper(): d for d in known_devices}

    try:
        _btctl("power on", timeout=8)
        _ensure_agent()

        # v0.9.21: Echtes Scan-on/off via bluetoothctl — findet auch neue (ungepairte) Geräte
        # Die printf-Pipe-Methode war unzuverlässig und startete keinen echten Discovery-Scan.
        # Jetzt: scan on → warten → devices → scan off
        subprocess.run(
            "bluetoothctl -- scan on 2>/dev/null &",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log.info("BT scan: Discovery gestartet (25s)")
        time.sleep(25)

        subprocess.run(
            "bluetoothctl -- scan off 2>/dev/null",
            shell=True, capture_output=True, timeout=5
        )
        log.info("BT scan: Discovery beendet")
        time.sleep(1)

        r_paired = subprocess.run("bluetoothctl paired-devices 2>/dev/null",
                                  shell=True, capture_output=True, text=True, timeout=5)
        known = {
            ln.split()[1]
            for ln in r_paired.stdout.splitlines()
            if ln.startswith("Device") and len(ln.split()) >= 2
        }

        r_all = subprocess.run("bluetoothctl devices 2>/dev/null",
                               shell=True, capture_output=True, text=True, timeout=5)

        for line in r_all.stdout.splitlines():
            p = line.strip().split(" ", 2)
            if len(p) >= 2 and p[0] == "Device":
                mac = p[1]
                name = p[2] if len(p) > 2 else mac
                _, info_out = _btctl(f"info {mac}", timeout=6)
                low = info_out.lower()

                if not _is_public_or_bredr(info_out):
                    continue
                if not _is_audio_device_info(info_out):
                    continue

                known_entry = known_map.get(mac.upper(), {})
                devices.append({
                    "mac": mac,
                    "name": name,
                    "known": mac in known or mac.upper() in known_map,
                    "paired": ("paired: yes" in low) or bool(known_entry.get("paired")),
                    "connected": "connected: yes" in low,
                    "trusted": "trusted: yes" in low,
                    "audio_candidate": True,
                    "source": "scan",
                })

    except Exception as e:
        log.error("BT scan: " + str(e))
        ipc.write_progress("BT Scan", "Scan fehlgeschlagen", color="red")
        time.sleep(2)
        ipc.clear_progress()
        return

    _write_known_devices(_dedupe_devices(known_devices + devices))
    ipc.write_json("/tmp/pidrive_bt_devices.json", {"devices": devices})

    ipc.clear_progress()
    msg = f"{len(devices)} Geraet(e) gefunden — Geraete > Verbinden"
    ipc.write_progress("BT Scan fertig", msg, color="green" if devices else "orange")
    time.sleep(3)
    ipc.clear_progress()
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def stop_scan():
    """Stoppt einen laufenden BT-Scan (v0.9.21)."""
    try:
        import subprocess as _sp
        _sp.run("bluetoothctl -- scan off 2>/dev/null",
                shell=True, capture_output=True, timeout=5)
        log.info("BT scan: Discovery gestoppt (Menü verlassen)")
    except Exception as _e:
        log.warn(f"BT stop_scan: {_e}")


def connect_device(mac, S, settings):
    if not _bt_connect_lock.acquire(blocking=False):
        log.warn("BT connect: bereits ein Connect läuft — abgebrochen")
        ipc.write_progress("Bluetooth", "Verbindung läuft bereits...", color="orange")
        time.sleep(2)
        ipc.clear_progress()
        return False

    try:
        return _connect_device_inner(mac, S, settings)
    finally:
        _bt_connect_lock.release()


def _connect_device_inner(mac, S, settings):
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

    if _src_state:
        if _src_state.in_transition():
            log.warn("BT connect: abgebrochen — Quellen-Transition läuft")
            _src_state.set_bt_state("failed")
            ipc.clear_progress()
            return False
        _src_state.set_bt_state("connecting")

    # Scanner stoppen vor Connect [2]
    try:
        from modules import scanner as _scanner
        if S.get("radio_type") == "SCANNER":
            log.info("BT connect: stoppe Scanner vor Connect")
            _scanner.stop(S)
            time.sleep(0.5)
    except Exception as e:
        log.warn("BT connect: scanner stop failed: " + str(e))

    S["bt"] = False
    S["bt_status"] = "verbindet"
    S["menu_rev"] = S.get("menu_rev", 0) + 1

    ok = False

    _btctl("power on", timeout=8)
    _ensure_agent()

    rc_info, out_info = _btctl(f"info {mac}", timeout=6)
    device_known = (rc_info == 0 and "Device" in out_info and "not available" not in out_info)

    if not device_known:
        log.info(f"BT connect: Gerät {mac} unbekannt — Discovery-Scan (max 20s)")
        ipc.write_progress("Bluetooth", "Suche Gerät... (bis 20s)", color="blue")

        proc_scan = subprocess.Popen(
            "printf 'menu scan\ntransport bredr\nback\nscan on\n' | bluetoothctl",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        for _poll in range(10):  # 20s
            time.sleep(2)
            rc_p, out_p = _btctl(f"info {mac}", timeout=5)
            if rc_p == 0 and "Device" in out_p and "not available" not in out_p:
                device_known = True
                log.info(f"BT connect: Gerät {mac} nach {(_poll+1)*2}s gefunden")
                break

        try:
            proc_scan.terminate()
            proc_scan.wait(timeout=2)
        except Exception:
            pass

        if not device_known:
            log.warn(f"BT connect: Gerät {mac} nach 20s Scan nicht gefunden — Abbruch")
            ipc.write_progress(
                "Bluetooth",
                "Nicht gefunden — Pairing-Modus am Kopfhörer aktiv?",
                color="red"
            )
            if _src_state:
                _src_state.set_bt_state("failed")
            time.sleep(4)
            ipc.clear_progress()
            S["bt"] = False
            S["bt_status"] = "getrennt"
            S["menu_rev"] = S.get("menu_rev", 0) + 1
            return False
    else:
        log.info(f"BT connect: Gerät {mac} BlueZ bekannt")

    _btctl(f"disconnect {mac}", timeout=8)
    time.sleep(1)

    _, info_pre = _btctl(f"info {mac}", timeout=6)
    if "paired: no" in info_pre.lower() and "name:" in info_pre.lower():
        log.info(f"BT connect: Paired:no erkannt — remove für Neu-Pairing mac={mac}")
        ipc.write_progress("Bluetooth", "Kopplung erneuern...", color="blue")
        _btctl(f"remove {mac}", timeout=10)
        time.sleep(2)

    attempts = [
        ("trust",   f"trust {mac}",   8),
        ("pair",    None,            45),
        ("connect", f"connect {mac}", 15),
        ("connect", f"connect {mac}", 15),
        ("connect", f"connect {mac}", 20),
    ]

    for step_name, cmd, to in attempts:
        if step_name == "pair":
            ok_pair, out = pair_with_agent(mac, timeout=to)
            rc = 0 if ok_pair else 1
        else:
            rc, out = _btctl(cmd, timeout=to)

        low = out.lower()

        if step_name == "pair":
            if any(x in low for x in [
                "successful", "paired: yes", "alreadyexists",
                "already paired", "device has been paired"
            ]):
                log.info(f"BT connect: PAIR ok mac={mac}")
            elif "authenticationfailed" in low or "authentication failed" in low:
                log.warn(f"BT connect: AuthenticationFailed — Kopfhörer in Pairing-Modus mac={mac}")
                ipc.write_progress("Bluetooth", "Pairing-Modus am Kopfhörer nötig!", color="orange")
                _btctl(f"remove {mac}", timeout=10)
                time.sleep(1)
            else:
                log.warn(f"BT connect: PAIR unsicher mac={mac} out={out[:180]}")

        elif step_name == "trust":
            if any(x in low for x in ["succeeded", "trust succeeded", "changing"]):
                log.info(f"BT connect: TRUST ok mac={mac}")

        elif step_name == "connect":
            if any(x in low for x in [
                "successful", "connection successful",
                "connected: yes", "already connected"
            ]):
                ok = True
                log.info(f"BT connect: CONNECT ok mac={mac}")
                break
            else:
                log.warn(f"BT connect: CONNECT fehlgeschlagen mac={mac} out={out[:180]}")
                time.sleep(2)

    if ok:
        _, info_out = _btctl(f"info {mac}", timeout=8)
        if "connected: yes" not in info_out.lower():
            log.warn(f"BT connect: VERIFY failed mac={mac}")
            ok = False
        else:
            for _ in range(8):
                pa_sink = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
                out = _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null", timeout=4)
                if pa_sink in out:
                    break
                time.sleep(1)
            else:
                log.warn(f"BT connect: A2DP-Sink nicht sichtbar mac={mac}")

    if not ok:
        S["bt"] = False
        S["bt_status"] = "getrennt"
        if _src_state:
            _src_state.set_bt_state("failed")
        ipc.write_progress("Bluetooth", "Verbindung fehlgeschlagen", color="red")
        log.warn(f"BT connect: FAIL mac={mac} name={name}")
        time.sleep(3)
        ipc.clear_progress()
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    S["bt"] = True
    S["bt_device"] = name
    S["bt_status"] = "verbunden"
    S["bt_sink_mac"] = mac
    S["bt_pa_sink"] = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"

    if _src_state:
        _src_state.set_bt_state("connected")
        _src_state.set_audio_route("bt")

    try:
        from modules import bt_backup as _btbak
        res = _btbak.backup()
        if res.get("ok"):
            log.info(f"BT-Backup: nach Connect automatisch gesichert ({res['count']} Dateien)")
    except Exception as _ebb:
        log.warn("BT-Backup nach Connect: " + str(_ebb))

    settings["bt_last_mac"] = mac
    settings["bt_last_name"] = name
    settings["bt_sink_mac"] = mac
    settings["bt_pa_sink"] = S["bt_pa_sink"]

    _write_known_devices(_dedupe_devices(_get_known_devices() + [{
        "mac": mac,
        "name": name,
        "known": True,
        "paired": True,
        "trusted": True,
        "connected": True,
        "source": "connect_success"
    }]))

    settings["audio_output"] = "bt"
    settings["alsa_device"] = "default"

    log.info(f"BT connect: STATE mac={mac} sink={S['bt_pa_sink']}")
    _set_pulseaudio_sink(S["bt_pa_sink"])
    _set_raspotify_device("default")

    if S.get("radio_playing"):
        try:
            now = time.time()
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

    S["bt"] = False
    S["bt_device"] = ""
    S["bt_sink_mac"] = ""
    S["bt_pa_sink"] = ""
    S["bt_status"] = "getrennt"

    if _src_state:
        _src_state.set_bt_state("idle")
        _src_state.set_audio_route("klinke")

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
    _btctl(f"remove {mac}", timeout=10)
    time.sleep(2)

    ok = connect_device(mac, S, settings)
    log.info(f"BT repair: {'OK' if ok else 'FAIL'} mac={mac}")
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    return ok


# ──────────────────────────────────────────────────────────────────────────────
# Reconnect
# ──────────────────────────────────────────────────────────────────────────────

_reconnect_thread = None
_reconnect_stop = False


def start_auto_reconnect(S, settings):
    """
    Hintergrund-Watcher:
    - bleibt als Fallback erhalten
    - reconnect_known_devices() ist die robustere aktive Variante
    """
    global _reconnect_thread, _reconnect_stop
    if _reconnect_thread and _reconnect_thread.is_alive():
        return

    _reconnect_stop = False
    import threading as _th

    def _watcher():
        # v0.9.25: Exponential Backoff — kein Spam bei abgeschaltetem Kopfhörer
        # Intervall-Schema: 12s → 20s → 30s → 60s → 120s → 300s → Stop nach 20min
        _INTERVALS = [12, 12, 20, 20, 30, 60, 120, 300]
        _MAX_RUNTIME = 20 * 60  # 20 Minuten, dann aufhören
        _fail_streak  = 0
        _start_ts     = time.time()

        time.sleep(6)
        while not _reconnect_stop:
            try:
                # Nach MAX_RUNTIME aufhören — Benutzer muss manuell reconnecten
                if time.time() - _start_ts > _MAX_RUNTIME:
                    log.info("BT auto-reconnect: aufgehört nach 20min ohne Erfolg")
                    break

                mac  = settings.get("bt_last_mac", "")
                name = settings.get("bt_last_name", "")
                if mac and not S.get("bt", False):
                    if _src_state and _src_state.in_transition():
                        time.sleep(5)
                        continue
                    rc, out = _btctl(f"info {mac}", timeout=5)
                    low = out.lower()
                    if rc == 0 and "name:" in low and "connected: no" in low:
                        log.info(f"BT auto-reconnect [Watcher]: Gerät sichtbar, versuche Connect mac={mac}")
                        rc2, out2 = _btctl(f"connect {mac}", timeout=15)
                        low2 = out2.lower()
                        if any(x in low2 for x in ["successful", "connected: yes"]):
                            log.info(f"BT auto-reconnect: ERFOLG mac={mac} name={name}")
                            S["bt"] = True
                            S["bt_device"] = name
                            S["bt_status"] = "verbunden"
                            S["bt_sink_mac"] = mac
                            S["bt_pa_sink"] = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
                            if _src_state:
                                _src_state.set_bt_state("connected")
                                _src_state.set_audio_route("bt")
                            settings["audio_output"] = "bt"
                            from modules import audio as _aud
                            _aud.get_mpv_args(settings, source="bt_auto_reconnect")
                            _fail_streak = 0
                            _start_ts = time.time()  # Timer zurücksetzen nach Erfolg
                        else:
                            _fail_streak += 1
                            log.info(f"BT auto-reconnect: fehlgeschlagen #{_fail_streak} mac={mac} ({out2[:60]})")
            except Exception as e:
                log.warn("BT auto-reconnect Watcher: " + str(e))
                _fail_streak += 1

            # Backoff: nach jedem Fehler länger warten (explizit loggen)
            _interval = _INTERVALS[min(_fail_streak, len(_INTERVALS)-1)]
            if not S.get("bt", False) and _fail_streak > 0:
                log.info(f"BT auto-reconnect: nächster Versuch in {_interval}s (Versuch #{_fail_streak})")
            time.sleep(_interval if not S.get("bt", False) else 20)

        log.info("BT auto-reconnect Watcher: beendet (20min Limit oder Stop-Flag)")

    _reconnect_thread = _th.Thread(target=_watcher, daemon=True, name="bt_auto_reconnect")
    _reconnect_thread.start()
    log.info("BT auto-reconnect: Watcher gestartet")


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
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    log.info(f"BT reconnect_last: START mac={mac} name={name}")
    return connect_device(mac, S, settings)


def reconnect_known_devices(S, settings):
    """
    Auto-Reconnect mit Priorität + Cooldown:
    1. letztes Gerät zuerst
    2. dann übrige bekannte/gepaarte Geräte
    """
    devs = _get_known_devices()
    last_mac = (settings.get("bt_last_mac", "") or "").upper()
    if last_mac:
        devs = sorted(devs, key=lambda d: 0 if (d.get("mac", "").upper() == last_mac) else 1)

    for d in devs:
        mac = (d.get("mac", "") or "").upper()
        if not mac:
            continue

        last_try = _RECONNECT_LAST_TRY.get(mac, 0)
        if (_now() - last_try) < _RECONNECT_COOLDOWN:
            continue
        _RECONNECT_LAST_TRY[mac] = _now()

        rc, out = _btctl(f"info {mac}", timeout=6)
        low = out.lower()

        if "connected: yes" in low:
            S["bt"] = True
            S["bt_device"] = d.get("name", mac)
            S["bt_status"] = "verbunden"
            if _src_state:
                _src_state.set_bt_state("connected")
            return True

        if "paired: yes" in low or d.get("paired") or d.get("known"):
            log.info(f"BT reconnect_known: versuche {mac} ({d.get('name','')})")
            if connect_device(mac, S, settings):
                return True
    return False


def get_bt_sink():
    """PulseAudio BT-Sink ermitteln."""
    PA_SOCKET = "PULSE_SERVER=unix:/var/run/pulse/native"
    try:
        r = subprocess.run(
            PA_SOCKET + " pactl list sinks short 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            if "bluez" in line.lower() or "a2dp" in line.lower():
                return line.split()[0] if line.split() else ""
    except Exception:
        pass
    return ""
