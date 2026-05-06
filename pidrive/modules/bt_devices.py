#!/usr/bin/env python3
"""bt_devices.py — Geräte-Datenbank und Scan  v0.10.43
Ausgelagert aus bluetooth.py."""

from modules.bt_helpers import (
    _btctl, _run, _bg, _normalize_mac, _valid_mac,
    _write_json_atomic, _read_json, _now, _sleep_s,
    _bt_adapter_up, _ensure_bt_on, _ensure_bt_off,
    _is_public_or_bredr, _is_audio_device_info,
    _parse_bool_from_info, _extract_name_from_info, _extract_alias_from_info,
    KNOWN_BT_FILE, DISCOVERED_BT_FILE,
    DEFAULT_SCAN_SECONDS, DISCOVERY_REFRESH_SECONDS,
    VISIBLE_TTL_SECONDS, RECENT_SEEN_SECONDS,
    _scan_lock,
)
import os
import threading
import subprocess
import time
import log
import ipc
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

# Scan-Prozess (lokal in diesem Modul)
_scan_proc = None
_scan_stop_flag = False

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
        _, rp = _btctl("devices Paired", timeout=8)
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



