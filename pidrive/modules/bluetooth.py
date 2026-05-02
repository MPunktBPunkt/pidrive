"""
modules/bluetooth.py — stark verbesserte Bluetooth-Logik für PiDrive
====================================================================

Ziele:
- robuster Gerätescan
- klare Trennung zwischen:
    * discovered / visible_now
    * known / historical
    * paired / trusted / connected
- modularerer Pair-/Connect-Flow
- vorsichtigerer Einsatz von remove
- besserer Reconnect mit Frische-/Cooldown-Logik
- PiDrive-kompatibel zu main_core.py / webui.py / audio.py / source_state.py

Wichtige Dateien:
- /tmp/pidrive_bt_known_devices.json   -> bekannte/historische Geräte
- /tmp/pidrive_bt_devices.json         -> aktueller Scan / live sichtbar
- /tmp/pidrive_bt_agent.json           -> Agent-Status
- /tmp/pidrive_bt_watcher.json         -> Watcher-Debug

Öffentliche API:
- bt_toggle(S)
- scan_devices(S, settings)
- stop_scan()
- connect_device(mac, S, settings)
- disconnect_current(S, settings)
- repair_device(mac, S, settings)
- reconnect_last(S, settings)
- reconnect_known_devices(S, settings)
- start_auto_reconnect(S, settings)
- stop_auto_reconnect()
- wake_auto_reconnect()
- get_bt_sink()

Hinweis:
Diese Version bleibt bewusst bei bluetoothctl als Backend, ist aber
strenger strukturiert als die bisherige Fassung.
"""

import json
import os
import re
import subprocess
import threading
import select
import time
from typing import Optional

import ipc
import log

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None


# ─────────────────────────────────────────────────────────────────────────────
# Dateien / Konstanten
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_BT_FILE = "/tmp/pidrive_bt_known_devices.json"
DISCOVERED_BT_FILE = "/tmp/pidrive_bt_devices.json"
AGENT_STATE_FILE = "/tmp/pidrive_bt_agent.json"
WATCHER_STATE_FILE = "/tmp/pidrive_bt_watcher.json"

PAIRING_BACKUP_FILE = "/tmp/pidrive_bt_pairing_debug.json"

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"

DEFAULT_SCAN_SECONDS = 22
DISCOVERY_REFRESH_SECONDS = 2.0

VISIBLE_TTL_SECONDS = 45          # Gerät gilt für UI kurz als "frisch sichtbar"
RECENT_SEEN_SECONDS = 7 * 24 * 3600
RECONNECT_COOLDOWN = 45
RECONNECT_FAIL_SOFT_LIMIT = 3

A2DP_WAIT_SECONDS = 10
VISIBILITY_WAIT_SECONDS = 20
PAIR_TIMEOUT_SECONDS = 45

_bt_connect_lock = threading.Lock()
_scan_lock = threading.Lock()

_scan_proc = None
_scan_stop_flag = False

_AGENT_PROC = None
_AGENT_LOCK = threading.Lock()

_reconnect_thread = None
_reconnect_stop = False
_reconnect_wakeup = None

_RECONNECT_LAST_TRY = {}
_RECONNECT_FAILS = {}


# ─────────────────────────────────────────────────────────────────────────────
# Basis-Helper
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> int:
    return int(time.time())


def _sleep_s(sec: float):
    try:
        time.sleep(sec)
    except Exception:
        pass


def _write_json_atomic(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log.warn(f"BT json write {path}: {e}")


def _read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _run(cmd, timeout=8):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _btctl(cmd, timeout=12):
    """
    Robuster bluetoothctl-Wrapper mit Logging.
    """
    try:
        r = subprocess.run(
            f"bluetoothctl {cmd} 2>&1",
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        log.info(
            f"BT ctl: {cmd} rc={r.returncode} "
            f"out={out[:220].replace(chr(10), ' | ')}"
        )
        return r.returncode, out
    except subprocess.TimeoutExpired:
        log.warn(f"BT ctl timeout: {cmd}")
        return 124, "timeout"
    except Exception as e:
        log.error(f"BT ctl error: {cmd}: {e}")
        return 1, str(e)


def _bg(cmd):
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass


def _normalize_mac(mac: str) -> str:
    return (mac or "").strip().upper()


def _valid_mac(mac: str) -> bool:
    return bool(re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", _normalize_mac(mac)))


def _parse_bool_from_info(info_out: str, key: str) -> bool:
    low = (info_out or "").lower()
    return f"{key.lower()}: yes" in low


def _extract_name_from_info(info_out: str, fallback: str = "") -> str:
    name = fallback or ""
    for line in (info_out or "").splitlines():
        s = line.strip()
        if s.lower().startswith("name:"):
            v = s.split(":", 1)[1].strip()
            if v:
                return v
    return name or fallback


def _extract_alias_from_info(info_out: str, fallback: str = "") -> str:
    alias = fallback or ""
    for line in (info_out or "").splitlines():
        s = line.strip()
        if s.lower().startswith("alias:"):
            v = s.split(":", 1)[1].strip()
            if v:
                return v
    return alias or fallback


def _is_public_or_bredr(info_out: str) -> bool:
    low = (info_out or "").lower()
    return (
        "(public)" in low or
        "bredr" in low or
        "br/edr" in low or
        "class:" in low
    )


def _is_audio_device_info(info_out: str) -> bool:
    low = (info_out or "").lower()
    return (
        "0000110b" in low or
        "0000110e" in low or
        "00001108" in low or
        "0000111e" in low or
        "audio sink" in low or
        "headset" in low or
        "headphone" in low or
        "handsfree" in low or
        "a/v remote control" in low or
        "class:" in low
    )


def _bt_adapter_up() -> bool:
    out = _run("hciconfig hci0 2>/dev/null", timeout=4)
    return "UP RUNNING" in out


def _ensure_bt_on(S=None) -> bool:
    """
    Adapter sicher aktivieren.
    """
    try:
        _bg("rfkill unblock bluetooth")
        _bg("hciconfig hci0 up")
        rc, _ = _btctl("power on", timeout=8)
        _sleep_s(1.0)
        ok = _bt_adapter_up() or rc == 0
        if S is not None:
            S["bt_on"] = bool(ok)
            if ok and not S.get("bt"):
                S["bt_status"] = S.get("bt_status") if S.get("bt_status") == "verbunden" else "getrennt"
        return bool(ok)
    except Exception as e:
        log.warn(f"BT ensure on: {e}")
        return False


def _ensure_bt_off():
    try:
        _btctl("scan off", timeout=5)
    except Exception:
        pass
    _bg("bluetoothctl power off")
    _bg("hciconfig hci0 down")
    _sleep_s(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

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
    return _read_json(AGENT_STATE_FILE, {})


def agent_is_alive():
    global _AGENT_PROC
    try:
        return _AGENT_PROC is not None and _AGENT_PROC.poll() is None
    except Exception:
        return False


def start_agent_session():
    """
    Persistente bluetoothctl-Agent-Session.
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

            # Agent initialisieren
            _AGENT_PROC.stdin.write("agent NoInputNoOutput\n")
            _AGENT_PROC.stdin.write("default-agent\n")
            _AGENT_PROC.stdin.flush()
            _sleep_s(1.0)

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


def _ensure_agent():
    return start_agent_session()


def _drain_agent_stdout(max_lines=80):
    """
    Alte Agent-Ausgaben abräumen, damit pair_with_agent()
    nicht auf stale stdout-Zeilen reinfällt.

    v0.10.0: select.select() für echtes non-blocking I/O statt
    blindem readline(), das bei stale stdout dauerhaft blockieren kann.
    """
    global _AGENT_PROC
    if not agent_is_alive():
        return
    try:
        if _AGENT_PROC.stdout is None:
            return
        drained = 0
        start = time.time()
        fd = _AGENT_PROC.stdout.fileno()
        while drained < max_lines and (time.time() - start) < 0.8:
            if _AGENT_PROC.poll() is not None:
                break
            # select mit 50 ms Timeout → kein Blockieren
            ready, _, _ = select.select([fd], [], [], 0.05)
            if not ready:
                break  # nichts mehr verfügbar
            try:
                line = _AGENT_PROC.stdout.readline()
            except Exception:
                break
            if not line:
                break
            drained += 1
        if drained:
            log.info(f"BT agent: stdout drained lines={drained} (non-blocking)")
    except Exception:
        pass


def pair_with_agent(mac, timeout=PAIR_TIMEOUT_SECONDS):
    """
    Pairing über persistente Agent-Session.
    """
    global _AGENT_PROC

    mac = _normalize_mac(mac)
    if not _valid_mac(mac):
        return False, "invalid_mac"

    if not start_agent_session():
        return False, "agent_start_failed"

    _drain_agent_stdout()

    lines = []
    try:
        _AGENT_PROC.stdin.write(f"pair {mac}\n")
        _AGENT_PROC.stdin.flush()

        end = time.time() + timeout
        while time.time() < end:
            line = _AGENT_PROC.stdout.readline()
            if not line:
                _sleep_s(0.2)
                continue

            s = line.strip()
            lines.append(s)
            low = s.lower()

            if (
                "pairing successful" in low or
                "device has been paired" in low or
                "already paired" in low or
                "already exists" in low or
                ("paired" in low and "successful" in low)
            ):
                _write_agent_state(
                    running=True,
                    ready=True,
                    pid=_AGENT_PROC.pid,
                    last_error="",
                    started_ts=read_agent_state().get("started_ts", _now()),
                    health_ok=True
                )
                _write_json_atomic(PAIRING_BACKUP_FILE, {
                    "mac": mac,
                    "ok": True,
                    "lines": lines[-30:],
                    "ts": _now(),
                })
                return True, "\n".join(lines[-30:])

            if (
                "authenticationfailed" in low or
                "authentication failed" in low or
                "failed" in low or
                "not available" in low or
                "canceled" in low
            ):
                _write_agent_state(
                    running=True,
                    ready=False,
                    pid=_AGENT_PROC.pid,
                    last_error=s,
                    started_ts=read_agent_state().get("started_ts", _now()),
                    health_ok=False
                )
                _write_json_atomic(PAIRING_BACKUP_FILE, {
                    "mac": mac,
                    "ok": False,
                    "lines": lines[-30:],
                    "ts": _now(),
                })
                return False, "\n".join(lines[-30:])

        _write_agent_state(
            running=True,
            ready=False,
            pid=_AGENT_PROC.pid,
            last_error="pair_timeout",
            started_ts=read_agent_state().get("started_ts", _now()),
            health_ok=False
        )
        _write_json_atomic(PAIRING_BACKUP_FILE, {
            "mac": mac,
            "ok": False,
            "timeout": True,
            "lines": lines[-30:],
            "ts": _now(),
        })
        return False, "\n".join(lines[-30:])

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


# ─────────────────────────────────────────────────────────────────────────────
# Known / discovered devices
# ─────────────────────────────────────────────────────────────────────────────

def _dedupe_devices(devs):
    out = []
    seen = set()
    for d in devs or []:
        mac = _normalize_mac(d.get("mac", ""))
        if not mac or mac in seen:
            continue
        seen.add(mac)

        row = dict(d)
        row["mac"] = mac
        row.setdefault("name", mac)
        row.setdefault("known", False)
        row.setdefault("paired", False)
        row.setdefault("trusted", False)
        row.setdefault("connected", False)
        row.setdefault("visible_now", False)
        row.setdefault("seen_this_scan", False)
        row.setdefault("audio_candidate", False)
        row.setdefault("last_seen_ts", 0)
        row.setdefault("last_connect_ts", 0)
        row.setdefault("last_failure_ts", 0)
        row.setdefault("last_failure_reason", "")
        row.setdefault("failure_count", 0)
        row.setdefault("source", "")
        out.append(row)
    return out


def _read_known_devices():
    return _read_json(KNOWN_BT_FILE, {}).get("devices", [])


def _write_known_devices(devs):
    _write_json_atomic(KNOWN_BT_FILE, {
        "devices": _dedupe_devices(devs),
        "ts": _now()
    })


def _read_discovered_devices():
    return _read_json(DISCOVERED_BT_FILE, {}).get("devices", [])


def _write_discovered_devices(devs):
    _write_json_atomic(DISCOVERED_BT_FILE, {
        "devices": _dedupe_devices(devs),
        "ts": _now()
    })


def _load_bluez_db_devices():
    """
    Historische bekannte Geräte aus /var/lib/bluetooth.
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

                    paired = (
                        "[LinkKey]" in txt or
                        "[LongTermKey]" in txt or
                        "SupportedTechnologies=BR/EDR;" in txt
                    )
                except Exception:
                    pass

                result.append({
                    "mac": mac,
                    "name": name,
                    "known": True,
                    "paired": paired,
                    "trusted": trusted,
                    "connected": False,
                    "visible_now": False,
                    "seen_this_scan": False,
                    "audio_candidate": True,
                    "source": "bluez_db",
                })
    except Exception as e:
        log.warn("BT BlueZ-DB lesen: " + str(e))

    return _dedupe_devices(result)


def _get_known_devices():
    """
    Historische / gepaarte Geräte.
    Wichtig: NICHT gleichbedeutend mit "jetzt sichtbar".
    """
    result = []
    result.extend(_read_known_devices())
    result.extend(_load_bluez_db_devices())

    try:
        _, rp = _btctl("paired-devices", timeout=8)
        for ln in rp.splitlines():
            p = ln.strip().split(" ", 2)
            if len(p) >= 2 and p[0] == "Device":
                result.append({
                    "mac": p[1],
                    "name": p[2] if len(p) > 2 else p[1],
                    "known": True,
                    "paired": True,
                    "trusted": False,
                    "connected": False,
                    "visible_now": False,
                    "seen_this_scan": False,
                    "audio_candidate": True,
                    "source": "paired_devices",
                })
    except Exception:
        pass

    result = _dedupe_devices(result)
    _write_known_devices(result)
    return result


def _merge_known_update(mac: str, **fields):
    mac = _normalize_mac(mac)
    if not _valid_mac(mac):
        return

    devs = _get_known_devices()
    found = False
    for d in devs:
        if _normalize_mac(d.get("mac", "")) == mac:
            d.update(fields)
            d["mac"] = mac
            found = True
            break

    if not found:
        row = {
            "mac": mac,
            "name": fields.get("name", mac),
            "known": True,
            "paired": False,
            "trusted": False,
            "connected": False,
            "visible_now": False,
            "seen_this_scan": False,
            "audio_candidate": True,
            "last_seen_ts": 0,
            "last_connect_ts": 0,
            "last_failure_ts": 0,
            "last_failure_reason": "",
            "failure_count": 0,
            "source": "merge_known",
        }
        row.update(fields)
        devs.append(row)

    _write_known_devices(devs)


# ─────────────────────────────────────────────────────────────────────────────
# Scan / discovery
# ─────────────────────────────────────────────────────────────────────────────

def _mark_old_discovered_not_visible():
    devs = _read_discovered_devices()
    now = _now()
    for d in devs:
        last_seen = int(d.get("last_seen_ts", 0) or 0)
        if not last_seen or (now - last_seen) > VISIBLE_TTL_SECONDS:
            d["visible_now"] = False
            d["seen_this_scan"] = False
    _write_discovered_devices(devs)


def _get_info_with_retries(mac, tries=4, delay=1.0):
    mac = _normalize_mac(mac)
    last = ""
    for _ in range(max(1, tries)):
        rc, out = _btctl(f"info {mac}", timeout=6)
        last = out or ""
        low = last.lower()
        if rc == 0 and "device" in low and "not available" not in low:
            return last
        _sleep_s(delay)
    return last


def _device_row_from_info(mac, fallback_name="", known_map=None):
    known_map = known_map or {}
    mac = _normalize_mac(mac)
    info_out = _get_info_with_retries(mac, tries=4, delay=0.8)
    low = (info_out or "").lower()

    if not info_out or "not available" in low:
        return None

    if not _is_public_or_bredr(info_out):
        return None

    if not _is_audio_device_info(info_out):
        return None

    name = _extract_name_from_info(info_out, fallback_name or mac)
    alias = _extract_alias_from_info(info_out, name)

    known_entry = known_map.get(mac, {})

    return {
        "mac": mac,
        "name": alias or name or mac,
        "known": True if known_entry else _parse_bool_from_info(info_out, "paired"),
        "paired": _parse_bool_from_info(info_out, "paired") or bool(known_entry.get("paired")),
        "trusted": _parse_bool_from_info(info_out, "trusted") or bool(known_entry.get("trusted")),
        "connected": _parse_bool_from_info(info_out, "connected"),
        "audio_candidate": True,
        "visible_now": True,
        "seen_this_scan": True,
        "last_seen_ts": _now(),
        "source": "scan_live",
    }


def stop_scan():
    """
    Stoppt laufenden Discovery-Scan.
    """
    global _scan_proc, _scan_stop_flag
    with _scan_lock:
        _scan_stop_flag = True
        try:
            _btctl("scan off", timeout=5)
        except Exception:
            pass
        if _scan_proc:
            try:
                _scan_proc.terminate()
                _scan_proc.wait(timeout=2)
            except Exception:
                pass
            _scan_proc = None
        log.info("BT scan: Discovery gestoppt")


def scan_devices(S, settings, scan_seconds=DEFAULT_SCAN_SECONDS):
    """
    Robusterer Scan:
    - discovered_devices nur aus dieser Session
    - known_devices getrennt weiterpflegen
    - info() mit Retries
    - visible_now / seen_this_scan / last_seen_ts
    """
    global _scan_proc, _scan_stop_flag

    with _scan_lock:
        _scan_stop_flag = False

    ipc.write_progress("Bluetooth", f"Scanne Geräte ({scan_seconds}s)...", color="blue")

    try:
        _mark_old_discovered_not_visible()

        known_devices = _get_known_devices()
        known_map = {d.get("mac", "").upper(): d for d in known_devices}

        if not _ensure_bt_on(S):
            ipc.write_progress("Bluetooth", "Adapter nicht bereit", color="red")
            _sleep_s(2)
            ipc.clear_progress()
            return []

        _ensure_agent()

        # Discovery sauber starten
        _btctl("scan off", timeout=5)
        _sleep_s(0.5)
        _scan_proc = subprocess.Popen(
            "bluetoothctl -- scan on 2>/dev/null",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log.info(f"BT scan: gestartet ({scan_seconds}s)")

        deadline = time.time() + int(scan_seconds)
        found = {}

        while time.time() < deadline:
            if _scan_stop_flag:
                log.info("BT scan: vorzeitig gestoppt")
                break

            rc, out = _btctl("devices", timeout=8)
            if rc == 0:
                for line in out.splitlines():
                    p = line.strip().split(" ", 2)
                    if len(p) >= 2 and p[0] == "Device":
                        mac = _normalize_mac(p[1])
                        fallback_name = p[2] if len(p) > 2 else mac

                        # Schon sinnvoll vorhanden? Dann nur last_seen refreshen
                        if mac in found and found[mac].get("name") not in ("", mac):
                            found[mac]["last_seen_ts"] = _now()
                            continue

                        row = _device_row_from_info(mac, fallback_name, known_map)
                        if row:
                            found[mac] = row

            # Zwischenspeichern, damit WebUI schon während/nach Scan konsistent ist
            _write_discovered_devices(list(found.values()))
            _sleep_s(DISCOVERY_REFRESH_SECONDS)

        try:
            _btctl("scan off", timeout=6)
        finally:
            if _scan_proc:
                try:
                    _scan_proc.terminate()
                    _scan_proc.wait(timeout=2)
                except Exception:
                    pass
                _scan_proc = None

        _sleep_s(1.0)

        devices = sorted(found.values(), key=lambda d: (
            0 if d.get("connected") else 1,
            0 if d.get("paired") else 1,
            (d.get("name") or "").lower(),
            d.get("mac") or ""
        ))

        # known separat fortschreiben, aber NICHT die Live-Liste mit stale Geräten mischen
        merged_known = _dedupe_devices(known_devices + [
            {
                "mac": d["mac"],
                "name": d["name"],
                "known": True,
                "paired": d.get("paired", False),
                "trusted": d.get("trusted", False),
                "connected": d.get("connected", False),
                "audio_candidate": True,
                "visible_now": False,       # known-Datei bleibt historisch
                "seen_this_scan": False,
                "last_seen_ts": d.get("last_seen_ts", _now()),
                "source": "scan_seen",
            }
            for d in devices
        ])
        _write_known_devices(merged_known)
        _write_discovered_devices(devices)

        ipc.clear_progress()
        msg = f"{len(devices)} Gerät(e) gefunden — Geräte > Verbinden"
        ipc.write_progress("BT Scan fertig", msg, color="green" if devices else "orange")
        _sleep_s(3)
        ipc.clear_progress()

        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return devices

    except Exception as e:
        log.error("BT scan: " + str(e))
        try:
            _btctl("scan off", timeout=5)
        except Exception:
            pass
        ipc.write_progress("BT Scan", "Scan fehlgeschlagen", color="red")
        _sleep_s(2)
        ipc.clear_progress()
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Audio / sink helper
# ─────────────────────────────────────────────────────────────────────────────

def _set_pulseaudio_sink(sink_name):
    if not sink_name:
        return False
    try:
        # warten bis Sink sichtbar
        for _ in range(8):
            r = subprocess.run(
                PA_ENV + " pactl list sinks short 2>/dev/null",
                shell=True,
                capture_output=True,
                text=True,
                timeout=3
            )
            if sink_name in (r.stdout or ""):
                break
            _sleep_s(1.0)

        r = subprocess.run(
            PA_ENV + " pactl set-default-sink " + sink_name,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if r.returncode == 0:
            log.info("PulseAudio: Default-Sink=" + sink_name)
            return True
        log.warn("PulseAudio sink nicht gefunden/setzbar: " + sink_name)
        return False
    except Exception as e:
        log.error("PulseAudio sink-Fehler: " + str(e))
        return False


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
            subprocess.run(
                ["systemctl", "restart", "raspotify"],
                capture_output=True,
                timeout=10
            )
            log.info("Raspotify: neu gestartet")

    except Exception as e:
        log.error("Raspotify Device-Wechsel fehlgeschlagen: " + str(e))


def get_bt_sink():
    try:
        r = subprocess.run(
            PA_ENV + " pactl list sinks short 2>/dev/null",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in (r.stdout or "").splitlines():
            low = line.lower()
            if "bluez" in low or "a2dp" in low:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass
    return ""


def _expected_pa_sink_for_mac(mac: str) -> str:
    return "bluez_sink." + _normalize_mac(mac).replace(":", "_") + ".a2dp_sink"


def _ensure_a2dp_sink(mac, timeout=A2DP_WAIT_SECONDS):
    pa_sink = _expected_pa_sink_for_mac(mac)
    end = time.time() + timeout
    while time.time() < end:
        out = _run(PA_ENV + " pactl list sinks short 2>/dev/null", timeout=4)
        if pa_sink in out:
            return True, pa_sink
        _sleep_s(1.0)
    return False, pa_sink


# ─────────────────────────────────────────────────────────────────────────────
# Device visibility / bond / pair / connect
# ─────────────────────────────────────────────────────────────────────────────

def _device_visible_in_recent_scan(mac: str) -> bool:
    mac = _normalize_mac(mac)
    now = _now()
    for d in _read_discovered_devices():
        if _normalize_mac(d.get("mac", "")) == mac:
            last_seen = int(d.get("last_seen_ts", 0) or 0)
            if d.get("visible_now") and last_seen and (now - last_seen) <= VISIBLE_TTL_SECONDS:
                return True
    return False


def _ensure_device_visible(mac, timeout=VISIBILITY_WAIT_SECONDS):
    mac = _normalize_mac(mac)

    rc, out = _btctl(f"info {mac}", timeout=5)
    low = (out or "").lower()
    if rc == 0 and "device" in low and "not available" not in low:
        return True, out

    # kurzer aktiver Discovery-Pfad
    _btctl("scan on", timeout=5)
    try:
        end = time.time() + timeout
        while time.time() < end:
            rc, out = _btctl(f"info {mac}", timeout=5)
            low = (out or "").lower()
            if rc == 0 and "device" in low and "not available" not in low:
                return True, out
            _sleep_s(2.0)
        return False, out
    finally:
        _btctl("scan off", timeout=5)


def _ensure_clean_bond_state(mac):
    """
    remove NICHT sofort immer verwenden.
    Nur bei klar inkonsistentem Zustand.
    """
    mac = _normalize_mac(mac)
    _, info = _btctl(f"info {mac}", timeout=6)
    low = (info or "").lower()

    if "name:" in low and "paired: no" in low:
        log.warn(f"BT bond: inkonsistent, remove nötig mac={mac}")
        _btctl(f"disconnect {mac}", timeout=8)
        _btctl(f"remove {mac}", timeout=10)
        return True

    return True


def _ensure_paired(mac, timeout=PAIR_TIMEOUT_SECONDS):
    mac = _normalize_mac(mac)
    _, info = _btctl(f"info {mac}", timeout=6)
    if _parse_bool_from_info(info, "paired"):
        return True, info

    ok, out = pair_with_agent(mac, timeout=timeout)
    if not ok:
        return False, out

    _, verify = _btctl(f"info {mac}", timeout=6)
    return _parse_bool_from_info(verify, "paired"), verify


def _ensure_trusted(mac):
    mac = _normalize_mac(mac)

    _, info = _btctl(f"info {mac}", timeout=6)
    if _parse_bool_from_info(info, "trusted"):
        return True, info

    rc, out = _btctl(f"trust {mac}", timeout=8)
    low = (out or "").lower()

    if any(x in low for x in ["trust succeeded", "succeeded", "changing"]):
        _, verify = _btctl(f"info {mac}", timeout=6)
        return _parse_bool_from_info(verify, "trusted"), verify

    _, verify = _btctl(f"info {mac}", timeout=6)
    return _parse_bool_from_info(verify, "trusted"), verify


def _ensure_connected(mac, retries=3):
    mac = _normalize_mac(mac)

    # Schon verbunden?
    _, info = _btctl(f"info {mac}", timeout=6)
    if _parse_bool_from_info(info, "connected"):
        return True, info

    last_out = ""
    for _ in range(max(1, retries)):
        rc, out = _btctl(f"connect {mac}", timeout=20)
        low = (out or "").lower()
        last_out = out

        if (
            rc == 0 and (
                "successful" in low or
                "connection successful" in low or
                "already connected" in low
            )
        ):
            _, verify = _btctl(f"info {mac}", timeout=8)
            if _parse_bool_from_info(verify, "connected"):
                return True, verify

        _sleep_s(2.0)

    return False, last_out


# ─────────────────────────────────────────────────────────────────────────────
# Reconnect failure memory
# ─────────────────────────────────────────────────────────────────────────────

def _mark_reconnect_failure(mac, reason):
    mac = _normalize_mac(mac)
    row = _RECONNECT_FAILS.get(mac, {
        "failure_count": 0,
        "last_failure_ts": 0,
        "last_failure_reason": "",
    })
    row["failure_count"] = int(row.get("failure_count", 0)) + 1
    row["last_failure_ts"] = _now()
    row["last_failure_reason"] = reason or ""
    _RECONNECT_FAILS[mac] = row

    _merge_known_update(
        mac,
        last_failure_ts=row["last_failure_ts"],
        last_failure_reason=row["last_failure_reason"],
        failure_count=row["failure_count"],
    )


def _mark_reconnect_success(mac):
    mac = _normalize_mac(mac)
    _RECONNECT_FAILS[mac] = {
        "failure_count": 0,
        "last_failure_ts": 0,
        "last_failure_reason": "",
    }
    _merge_known_update(
        mac,
        last_failure_ts=0,
        last_failure_reason="",
        failure_count=0,
        last_connect_ts=_now(),
    )


def _should_try_reconnect(mac, meta):
    mac = _normalize_mac(mac)
    if not mac:
        return False

    last_try = _RECONNECT_LAST_TRY.get(mac, 0)
    if (_now() - last_try) < RECONNECT_COOLDOWN:
        return False

    fail_count = int(meta.get("failure_count", 0) or 0)
    if fail_count >= RECONNECT_FAIL_SOFT_LIMIT:
        last_fail = int(meta.get("last_failure_ts", 0) or 0)
        if last_fail and (_now() - last_fail) < 15 * 60:
            return False

    return True


def _reconnect_candidates(settings):
    """
    Priorität:
    1. bt_last_mac
    2. frisch gesehene bekannte Geräte
    3. sehr wenige stale Geräte als Fallback
    """
    devs = _get_known_devices()
    last_mac = _normalize_mac(settings.get("bt_last_mac", "") or "")

    fresh = []
    stale = []

    for d in devs:
        mac = _normalize_mac(d.get("mac", ""))
        if not mac:
            continue
        last_seen = int(d.get("last_seen_ts", 0) or 0)

        if last_seen and (_now() - last_seen) < RECENT_SEEN_SECONDS:
            fresh.append(d)
        else:
            stale.append(d)

    fresh = sorted(fresh, key=lambda d: (
        0 if _normalize_mac(d.get("mac", "")) == last_mac else 1,
        0 if d.get("paired") else 1,
        (d.get("name") or "").lower()
    ))

    stale = sorted(stale, key=lambda d: (
        0 if _normalize_mac(d.get("mac", "")) == last_mac else 1,
        0 if d.get("paired") else 1,
        (d.get("name") or "").lower()
    ))

    # stale nur sehr konservativ
    return fresh + stale[:1]


# ─────────────────────────────────────────────────────────────────────────────
# Öffentliche BT-Funktionen
# ─────────────────────────────────────────────────────────────────────────────

def bt_toggle(S):
    if S.get("bt_on", False) or S.get("bt", False):
        log.info("BT toggle: OFF")
        stop_scan()
        _ensure_bt_off()
        S["bt"] = False
        S["bt_on"] = False
        S["bt_device"] = ""
        S["bt_status"] = "aus"
        if _src_state:
            _src_state.set_bt_state("idle")
            _src_state.set_bt_link_state("idle")
            _src_state.set_bt_audio_state("no_sink")
    else:
        log.info("BT toggle: ON")
        ok = _ensure_bt_on(S)
        S["bt_on"] = bool(ok)
        if ok and not S.get("bt"):
            S["bt_status"] = "getrennt"

    S["ts"] = 0
    S["menu_rev"] = S.get("menu_rev", 0) + 1


def connect_device(mac, S, settings):
    mac = _normalize_mac(mac)
    if not _valid_mac(mac):
        ipc.write_progress("Bluetooth", "Ungültige MAC", color="red")
        _sleep_s(2)
        ipc.clear_progress()
        return False

    # Watcher ggf. aufwecken
    wake_auto_reconnect()

    if not _bt_connect_lock.acquire(blocking=False):
        log.warn("BT connect: bereits ein Connect läuft — abgebrochen")
        ipc.write_progress("Bluetooth", "Verbindung läuft bereits...", color="orange")
        _sleep_s(2)
        ipc.clear_progress()
        return False

    try:
        return _connect_device_inner(mac, S, settings)
    finally:
        _bt_connect_lock.release()


def _connect_device_inner(mac, S, settings):
    mac = _normalize_mac(mac)
    name = mac

    # Name aus live Scan oder known ableiten
    for d in _read_discovered_devices():
        if _normalize_mac(d.get("mac", "")) == mac:
            name = d.get("name", mac)
            break
    if name == mac:
        for d in _get_known_devices():
            if _normalize_mac(d.get("mac", "")) == mac:
                name = d.get("name", mac)
                break

    ipc.write_progress("Bluetooth", f"Verbinde {name[:20]}...", color="blue")
    log.info(f"BT connect: START mac={mac} name={name}")

    if _src_state:
        if _src_state.in_transition():
            log.warn("BT connect: abgebrochen — Quellen-Transition läuft")
            _src_state.set_bt_state("failed")
            _src_state.set_bt_link_state("failed")
            _src_state.set_bt_audio_state("no_sink")
            ipc.clear_progress()
            return False
        _src_state.set_bt_state("connecting")
        _src_state.set_bt_link_state("connecting")
        _src_state.set_bt_audio_state("pending")

    # Scanner stoppen, falls aktiv
    try:
        from modules import scanner as _scanner
        if S.get("radio_type") == "SCANNER":
            log.info("BT connect: stoppe Scanner vor Connect")
            _scanner.stop(S)
            _sleep_s(0.5)
    except Exception as e:
        log.warn("BT connect: scanner stop failed: " + str(e))

    S["bt"] = False
    S["bt_on"] = True
    S["bt_status"] = "verbindet"
    S["menu_rev"] = S.get("menu_rev", 0) + 1

    if not _ensure_bt_on(S):
        ipc.write_progress("Bluetooth", "Adapter nicht bereit", color="red")
        if _src_state:
            _src_state.set_bt_state("failed")
            _src_state.set_bt_link_state("failed")
            _src_state.set_bt_audio_state("no_sink")
        _sleep_s(2)
        ipc.clear_progress()
        S["bt_status"] = "getrennt"
        return False

    _ensure_agent()

    visible, info = _ensure_device_visible(mac, timeout=VISIBILITY_WAIT_SECONDS)
    if not visible:
        ipc.write_progress("Bluetooth", "Nicht gefunden — Pairing-Modus aktivieren", color="red")
        if _src_state:
            _src_state.set_bt_state("failed")
            _src_state.set_bt_link_state("failed")
            _src_state.set_bt_audio_state("no_sink")
        _mark_reconnect_failure(mac, "not_visible")
        _sleep_s(4)
        ipc.clear_progress()
        S["bt"] = False
        S["bt_status"] = "getrennt"
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    # verbundenen Restzustand vor Neuversuch trennen
    _btctl(f"disconnect {mac}", timeout=8)
    _sleep_s(1.0)

    # nur bei echtem Inkonsistenzfall remove
    _ensure_clean_bond_state(mac)

    paired_ok, pair_info = _ensure_paired(mac, timeout=PAIR_TIMEOUT_SECONDS)
    if not paired_ok:
        low = (pair_info or "").lower()
        if "authenticationfailed" in low or "authentication failed" in low:
            ipc.write_progress("Bluetooth", "Pairing-Modus am Gerät nötig!", color="orange")
            # remove erst als Eskalation nach Auth-Fehler
            _btctl(f"remove {mac}", timeout=10)
        else:
            ipc.write_progress("Bluetooth", "Pairing fehlgeschlagen", color="red")

        if _src_state:
            _src_state.set_bt_state("failed")
            _src_state.set_bt_link_state("failed")
            _src_state.set_bt_audio_state("no_sink")
        _mark_reconnect_failure(mac, "pair_failed")
        _sleep_s(3)
        ipc.clear_progress()
        S["bt"] = False
        S["bt_status"] = "getrennt"
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    trusted_ok, _ = _ensure_trusted(mac)
    if not trusted_ok:
        # kein harter Abbruch, nur Warnung
        log.warn(f"BT connect: trust nicht bestätigt mac={mac}")

    connected_ok, conn_info = _ensure_connected(mac, retries=3)
    if not connected_ok:
        ipc.write_progress("Bluetooth", "Verbindung fehlgeschlagen", color="red")
        if _src_state:
            _src_state.set_bt_state("failed")
            _src_state.set_bt_link_state("failed")
            _src_state.set_bt_audio_state("no_sink")
        _mark_reconnect_failure(mac, "connect_failed")
        _sleep_s(3)
        ipc.clear_progress()
        S["bt"] = False
        S["bt_status"] = "getrennt"
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    sink_ok, pa_sink = _ensure_a2dp_sink(mac, timeout=A2DP_WAIT_SECONDS)
    if not sink_ok:
        log.warn(f"BT connect: Link ok, aber kein A2DP-Sink mac={mac}")

    # Erfolgspfad
    S["bt"] = True
    S["bt_on"] = True
    S["bt_device"] = name
    S["bt_status"] = "verbunden"
    S["bt_sink_mac"] = mac
    S["bt_pa_sink"] = pa_sink

    if _src_state:
        _src_state.set_bt_state("connected")
        _src_state.set_bt_link_state("connected")
        _src_state.set_bt_audio_state("a2dp_ready" if sink_ok else "no_sink")
        _src_state.set_audio_route("bt" if sink_ok else "klinke")

    settings["bt_last_mac"] = mac
    settings["bt_last_name"] = name
    settings["bt_sink_mac"] = mac
    settings["bt_pa_sink"] = pa_sink

    # known device Status aktualisieren
    _merge_known_update(
        mac,
        name=name,
        known=True,
        paired=True,
        trusted=bool(trusted_ok),
        connected=True,
        last_seen_ts=_now(),
        last_connect_ts=_now(),
        failure_count=0,
        last_failure_ts=0,
        last_failure_reason="",
        source="connect_success"
    )
    _mark_reconnect_success(mac)

    # discovered device ebenfalls aktualisieren
    discovered = _read_discovered_devices()
    updated = False
    for d in discovered:
        if _normalize_mac(d.get("mac", "")) == mac:
            d.update({
                "name": name,
                "paired": True,
                "trusted": bool(trusted_ok),
                "connected": True,
                "visible_now": True,
                "seen_this_scan": True,
                "last_seen_ts": _now(),
            })
            updated = True
            break
    if not updated:
        discovered.append({
            "mac": mac,
            "name": name,
            "known": True,
            "paired": True,
            "trusted": bool(trusted_ok),
            "connected": True,
            "visible_now": True,
            "seen_this_scan": True,
            "audio_candidate": True,
            "last_seen_ts": _now(),
            "last_connect_ts": _now(),
            "source": "connect_success",
        })
    _write_discovered_devices(discovered)

    # Nur bei echtem Sink-Erfolg hart auf BT umschalten
    if sink_ok:
        settings["audio_output"] = "bt"
        settings["alsa_device"] = "default"
        _set_pulseaudio_sink(pa_sink)
        _set_raspotify_device("default")

    # BT-Backup nach Erfolg
    try:
        from modules import bt_backup as _btbak
        res = _btbak.backup()
        if res.get("ok"):
            log.info(f"BT-Backup: nach Connect automatisch gesichert ({res['count']} Dateien)")
    except Exception as _ebb:
        log.warn("BT-Backup nach Connect: " + str(_ebb))

    # Laufende Audioquelle ggf. auf BT neu anstoßen
    if S.get("radio_playing") and sink_ok:
        try:
            now = time.time()
            last = getattr(connect_device, "_last_restart_ts", 0)
            if now - last > 5:
                connect_device._last_restart_ts = now
                with open("/tmp/pidrive_cmd", "w", encoding="utf-8") as cf:
                    cf.write("radio_restart_on_bt\n")
                log.info("BT connect: radio_restart_on_bt ausgelöst")
        except Exception as e:
            log.warn(f"BT connect: radio restart failed: {e}")

    ipc.write_progress(
        "Bluetooth",
        f"Verbunden: {name[:22]}" if sink_ok else f"Verbunden ohne A2DP: {name[:16]}",
        color="green" if sink_ok else "orange"
    )
    _sleep_s(2)
    ipc.clear_progress()

    S["menu_rev"] = S.get("menu_rev", 0) + 1
    log.info(f"BT connect: DONE mac={mac} name={name} sink_ok={sink_ok}")
    return True


def disconnect_current(S, settings):
    mac = _normalize_mac(settings.get("bt_last_mac", "") or S.get("bt_sink_mac", ""))
    name = S.get("bt_device", "") or settings.get("bt_last_name", "") or mac or "BT-Gerät"

    ipc.write_progress("Bluetooth", f"Trenne {name[:20]}...", color="orange")
    log.info(f"BT disconnect: START mac={mac} name={name}")

    ok = True
    if mac:
        rc, out = _btctl(f"disconnect {mac}", timeout=12)
        ok = any(x in (out or "").lower() for x in ["successful", "not connected"]) or rc == 0
    else:
        log.warn("BT disconnect: keine MAC, nur Status-Reset")

    S["bt"] = False
    S["bt_device"] = ""
    S["bt_sink_mac"] = ""
    S["bt_pa_sink"] = ""
    S["bt_status"] = "getrennt"

    if _src_state:
        _src_state.set_bt_state("idle")
        _src_state.set_bt_link_state("idle")
        _src_state.set_bt_audio_state("no_sink")
        _src_state.set_audio_route("klinke")

    if settings.get("audio_output") == "bt":
        settings["audio_output"] = "klinke"

    try:
        from modules import audio as _a
        _a.set_output("klinke", settings)
    except Exception as e:
        log.warn(f"BT disconnect: audio fallback: {e}")

    if mac:
        _merge_known_update(mac, connected=False)

    ipc.write_progress("Bluetooth", "Getrennt" if ok else "Getrennt/unbestätigt",
                       color="green" if ok else "orange")
    _sleep_s(2)
    ipc.clear_progress()

    S["menu_rev"] = S.get("menu_rev", 0) + 1
    log.info(f"BT disconnect: DONE mac={mac}")
    return True


def repair_device(mac, S, settings):
    mac = _normalize_mac(mac)
    name = mac

    for d in _read_discovered_devices():
        if _normalize_mac(d.get("mac", "")) == mac:
            name = d.get("name", mac)
            break

    ipc.write_progress("Bluetooth", f"Neu koppeln: {name[:18]}...", color="blue")
    log.info(f"BT repair: START mac={mac} name={name}")

    _ensure_bt_on(S)
    _ensure_agent()
    _btctl(f"disconnect {mac}", timeout=10)
    _btctl(f"remove {mac}", timeout=10)
    _sleep_s(2)

    ok = connect_device(mac, S, settings)
    log.info(f"BT repair: {'OK' if ok else 'FAIL'} mac={mac}")
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    return ok


def reconnect_last(S, settings):
    mac = _normalize_mac(settings.get("bt_last_mac", ""))
    name = settings.get("bt_last_name", "") or mac

    if not mac:
        ipc.write_progress("Bluetooth", "Kein letztes Gerät", color="orange")
        log.warn("BT reconnect_last: keine bt_last_mac")
        _sleep_s(2)
        ipc.clear_progress()
        return False

    wake_auto_reconnect()

    S["bt_status"] = "verbindet"
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    log.info(f"BT reconnect_last: START mac={mac} name={name}")
    return connect_device(mac, S, settings)


def reconnect_known_devices(S, settings):
    """
    Einmaliger aktiver Reconnect:
    - letztes Gerät priorisieren
    - nur frische/sichtbare Kandidaten bevorzugen
    - Cooldown/Fails beachten
    """
    devs = _reconnect_candidates(settings)

    for d in devs:
        mac = _normalize_mac(d.get("mac", ""))
        if not mac:
            continue

        if not _should_try_reconnect(mac, d):
            continue

        _RECONNECT_LAST_TRY[mac] = _now()

        # Schon verbunden?
        rc, out = _btctl(f"info {mac}", timeout=6)
        low = (out or "").lower()
        if rc == 0 and "connected: yes" in low:
            S["bt"] = True
            S["bt_on"] = True
            S["bt_device"] = d.get("name", mac)
            S["bt_status"] = "verbunden"
            if _src_state:
                _src_state.set_bt_state("connected")
                _src_state.set_bt_link_state("connected")
            _mark_reconnect_success(mac)
            return True

        # Sichtbarkeit vor Reconnect hart prüfen
        visible, _ = _ensure_device_visible(mac, timeout=6)
        if not visible:
            log.info(f"BT reconnect_known: überspringe nicht sichtbares Gerät {mac}")
            _mark_reconnect_failure(mac, "not_visible")
            continue

        log.info(f"BT reconnect_known: versuche {mac} ({d.get('name','')})")
        if connect_device(mac, S, settings):
            _mark_reconnect_success(mac)
            return True

        _mark_reconnect_failure(mac, "connect_failed")

    if _src_state:
        _src_state.set_bt_state("failed")
        _src_state.set_bt_link_state("failed")
        _src_state.set_bt_audio_state("no_sink")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Auto reconnect watcher
# ─────────────────────────────────────────────────────────────────────────────

def _write_watcher_state(running=True, sleeping=False, fail_count=0,
                         last_result="", next_action="", current_mac=""):
    _write_json_atomic(WATCHER_STATE_FILE, {
        "running": running,
        "sleeping": sleeping,
        "fail_count": int(fail_count),
        "last_result": last_result,
        "next_action": next_action,
        "current_mac": current_mac,
        "ts": time.time(),
    })


def wake_auto_reconnect():
    global _reconnect_wakeup
    if _reconnect_wakeup is not None:
        _reconnect_wakeup.set()
        log.info("BT auto-reconnect: Watcher aufgeweckt")
    else:
        log.warn("BT auto-reconnect: kein Wakeup-Event vorhanden")


def start_auto_reconnect(S, settings):
    """
    Hintergrund-Watcher:
    - versucht letztes Gerät moderat
    - pausiert bei DAB / Transition
    - geht nach Fehlschlag in Schlafmodus
    """
    global _reconnect_thread, _reconnect_stop, _reconnect_wakeup

    if _reconnect_thread and _reconnect_thread.is_alive():
        return

    _reconnect_stop = False
    _reconnect_wakeup = threading.Event()

    def _watcher():
        _sleep_s(6)
        _write_watcher_state(running=True, sleeping=False, fail_count=0,
                             last_result="started", next_action="observe")

        fail_streak = 0
        start_ts = time.time()
        max_runtime = 20 * 60

        while not _reconnect_stop:
            try:
                if time.time() - start_ts > max_runtime:
                    log.info("BT auto-reconnect: aufgehört nach 20min ohne Erfolg")
                    _write_watcher_state(
                        running=False,
                        sleeping=False,
                        fail_count=fail_streak,
                        last_result="timeout_stop",
                        next_action="manual_reconnect"
                    )
                    break

                mac = _normalize_mac(settings.get("bt_last_mac", ""))
                name = settings.get("bt_last_name", "") or mac

                if not mac:
                    _sleep_s(20)
                    continue

                # Nichts tun wenn schon verbunden
                if S.get("bt", False):
                    fail_streak = 0
                    _write_watcher_state(
                        running=True,
                        sleeping=False,
                        fail_count=0,
                        last_result="already_connected",
                        next_action="wait",
                        current_mac=mac
                    )
                    _sleep_s(20)
                    continue

                # Während Source-Transition nicht connecten
                if _src_state and _src_state.in_transition():
                    _sleep_s(5)
                    continue

                # Während DAB absichtlich pausieren
                if S.get("radio_playing") and S.get("radio_type", "").upper() == "DAB":
                    _write_watcher_state(
                        running=True,
                        sleeping=False,
                        fail_count=fail_streak,
                        last_result="paused_dab",
                        next_action="wait_dab",
                        current_mac=mac
                    )
                    _sleep_s(10)
                    continue

                visible, _ = _ensure_device_visible(mac, timeout=6)
                if visible:
                    log.info(f"BT auto-reconnect [Watcher]: Gerät sichtbar, versuche Connect mac={mac}")
                    ok = connect_device(mac, S, settings)
                    if ok:
                        log.info(f"BT auto-reconnect: ERFOLG mac={mac} name={name}")
                        fail_streak = 0
                        start_ts = time.time()
                        _write_watcher_state(
                            running=True,
                            sleeping=False,
                            fail_count=0,
                            last_result="success",
                            next_action="wait",
                            current_mac=mac
                        )
                        _sleep_s(20)
                        continue
                    else:
                        fail_streak += 1
                        _mark_reconnect_failure(mac, "watcher_connect_failed")
                        log.info(f"BT auto-reconnect: fehlgeschlagen #{fail_streak} mac={mac}")
                else:
                    fail_streak += 1
                    _mark_reconnect_failure(mac, "watcher_not_visible")

            except Exception as e:
                log.warn("BT auto-reconnect Watcher: " + str(e))
                fail_streak += 1

            # Schlafmodus nach Fehlschlag
            if not S.get("bt", False) and fail_streak > 0:
                log.info("BT auto-reconnect [Watcher]: Fehlschlag → Schlafmodus")
                _write_watcher_state(
                    running=True,
                    sleeping=True,
                    fail_count=fail_streak,
                    last_result="failed",
                    next_action="bt_reconnect_last|bt_scan|reboot",
                    current_mac=_normalize_mac(settings.get("bt_last_mac", ""))
                )

                while not _reconnect_stop:
                    _sleep_s(30)
                    if _reconnect_wakeup is not None and _reconnect_wakeup.is_set():
                        _reconnect_wakeup.clear()
                        fail_streak = 0
                        log.info("BT auto-reconnect [Watcher]: geweckt — versuche erneut")
                        _write_watcher_state(
                            running=True,
                            sleeping=False,
                            fail_count=0,
                            last_result="woken",
                            next_action="connect",
                            current_mac=_normalize_mac(settings.get("bt_last_mac", ""))
                        )
                        break

        log.info("BT auto-reconnect Watcher: beendet")
        _write_watcher_state(
            running=False,
            sleeping=False,
            fail_count=0,
            last_result="stopped",
            next_action="manual_reconnect"
        )

    _reconnect_thread = threading.Thread(
        target=_watcher,
        daemon=True,
        name="bt_auto_reconnect"
    )
    _reconnect_thread.start()
    log.info("BT auto-reconnect: Watcher gestartet")


def stop_auto_reconnect():
    global _reconnect_stop
    _reconnect_stop = True


# ─────────────────────────────────────────────────────────────────────────────
# Kompatibilitäts-Aliase
# ─────────────────────────────────────────────────────────────────────────────

def start_agent():
    return start_agent_session()


def disconnect_device(S=None, settings=None):
    if S is None:
        S = {}
    if settings is None:
        settings = {}
    return disconnect_current(S, settings)