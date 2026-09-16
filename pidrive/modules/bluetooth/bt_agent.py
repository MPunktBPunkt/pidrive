#!/usr/bin/env python3
"""bt_agent.py — BT-Agent, Pairing  v0.10.55
Ausgelagert aus bluetooth.py."""

from modules.bluetooth.bt_helpers import (
    _btctl, _run, _bg, _normalize_mac, _valid_mac,
    _write_json_atomic, _read_json, _now, _sleep_s,
    _bt_adapter_up, _ensure_bt_on,
    _parse_bool_from_info, _extract_name_from_info, _extract_alias_from_info,
    _is_public_or_bredr, _is_audio_device_info,
    AGENT_STATE_FILE, PAIRING_BACKUP_FILE, PAIR_TIMEOUT_SECONDS,
)
import threading
import select
import subprocess
import time
import log

# Agent-Prozess und Lock (lokal in diesem Modul)
_AGENT_PROC = None
_AGENT_LOCK = threading.Lock()

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
    """BF-E: stillgelegt — Pairing über pidrive_btagent (D-Bus)."""
    global _AGENT_PROC
    log.info("BT Agent: bluetoothctl-Sitzung stillgelegt (BF-E) — nutze pidrive_btagent")
    # Falls alte Sitzung noch läuft: hart beenden (sonst Streit um DefaultAgent)
    try:
        if _AGENT_PROC is not None and _AGENT_PROC.poll() is None:
            _AGENT_PROC.terminate()
            try:
                _AGENT_PROC.wait(timeout=2)
            except Exception:
                _AGENT_PROC.kill()
    except Exception:
        pass
    _AGENT_PROC = None
    return True


def stop_agent_session():
    """BF-E: no-op (D-Bus-Agent läuft als eigener Dienst)."""
    global _AGENT_PROC
    try:
        if _AGENT_PROC is not None and _AGENT_PROC.poll() is None:
            _AGENT_PROC.terminate()
            try:
                _AGENT_PROC.wait(timeout=2)
            except Exception:
                _AGENT_PROC.kill()
    except Exception:
        pass
    _AGENT_PROC = None
    return True


def start_agent_health_thread():
    """BF-E: stillgelegt — Health übernimmt systemd für pidrive_btagent."""
    log.info("BT Agent health: stillgelegt (BF-E)")
    return None


def agent_healthcheck():
    """BF-E: Status aus D-Bus-Agent-Zustandsdatei."""
    st = read_agent_state()
    return bool(st.get("ready") or st.get("kind") == "dbus")


def _ensure_agent():
    return start_agent_session()


def _drain_agent_stdout(max_lines=80):
    """BF-E: no-op — kein bluetoothctl-Stdout mehr."""
    return


def pair_with_agent(mac, timeout=PAIR_TIMEOUT_SECONDS):
    """
    BF-E: Pairing über BlueZ Device1.Pair(); Bestätigung durch pidrive_btagent.
    """
    mac = _normalize_mac(mac)
    if not _valid_mac(mac):
        return False, "invalid_mac"

    start_agent_session()  # stellt nur sicher, dass alte Sitzung tot ist

    try:
        from modules.bluetooth import bt_agent_dbus as _dab
        _dab.open_pair_window(int(timeout) + 60)
    except Exception:
        pass

    events = []
    try:
        import dbus
        bus = dbus.SystemBus()
        path = "/org/bluez/hci0/dev_" + mac.replace(":", "_").upper()
        # Gerät ggf. zuerst scan/discover — Pair braucht Objekt
        try:
            dev = bus.get_object("org.bluez", path)
        except Exception:
            # Fallback: bluetoothctl pair (Agent antwortet auf D-Bus)
            rc, out = _btctl(f"pair {mac}", timeout=timeout)
            low = (out or "").lower()
            ok = rc == 0 or "already paired" in low or "pairing successful" in low
            _write_json_atomic(PAIRING_BACKUP_FILE, {
                "mac": mac, "ok": ok, "via": "bluetoothctl",
                "lines": (out or "").splitlines()[-30:], "ts": _now(),
            })
            return ok, out or ""

        iface = dbus.Interface(dev, "org.bluez.Device1")
        end = time.time() + float(timeout)
        try:
            iface.Pair()
        except Exception as e:
            err = str(e)
            if "AlreadyExists" in err or "Already Paired" in err:
                _write_json_atomic(PAIRING_BACKUP_FILE, {
                    "mac": mac, "ok": True, "via": "dbus",
                    "lines": [err], "ts": _now(),
                })
                return True, err
            # Pair kann asynchron laufen / Agent ablehnen
            log.warn(f"BT Device1.Pair: {e}")

        while time.time() < end:
            _, info = _btctl(f"info {mac}", timeout=6)
            if _parse_bool_from_info(info, "paired"):
                try:
                    ev = _read_json("/tmp/pidrive_bt_agent_events.json", {})
                    events = (ev.get("events") or [])[-30:]
                except Exception:
                    events = []
                _write_json_atomic(PAIRING_BACKUP_FILE, {
                    "mac": mac, "ok": True, "via": "dbus",
                    "events": events, "ts": _now(),
                })
                return True, "paired"
            _sleep_s(0.5)

        _write_json_atomic(PAIRING_BACKUP_FILE, {
            "mac": mac, "ok": False, "timeout": True,
            "via": "dbus", "events": events, "ts": _now(),
        })
        return False, "pair_timeout"
    except Exception as e:
        _write_json_atomic(PAIRING_BACKUP_FILE, {
            "mac": mac, "ok": False, "error": str(e), "ts": _now(),
        })
        return False, str(e)

