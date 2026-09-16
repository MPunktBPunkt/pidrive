#!/usr/bin/env python3
"""bt_watcher.py — Auto-Reconnect Watcher (Feldtest 2026-09-16 Hygiene)

Strategie nach BMW-Test:
  - Fahrzeug-initiierten Connect bevorzugen (Trusted + Bond reicht)
  - nie Pair() im Watcher — nur Connect()
  - BlueZ-Name ≠ Funkreichweite
  - nach Host-down / Page-Timeout lange Pause (kein Storm)
  - Kopfhörer nicht gegen BMW reconnecten
"""

from __future__ import annotations

import threading
import time

import log
from modules.bluetooth.bt_helpers import (
    _btctl,
    _normalize_mac,
    _now,
    _parse_bool_from_info,
    _sleep_s,
    _write_json_atomic,
    HOST_DOWN_PAUSE_SECONDS,
    RECONNECT_OPPORTUNISTIC_SECONDS,
    WATCHER_STATE_FILE,
    _device_type,
    bt_connect_active,
)
from modules.bluetooth.bt_connect import (
    connect_device,
    note_link_event,
    read_link_event,
    _ensure_device_visible,
    _mark_reconnect_failure,
    _mark_reconnect_success,
    _resolve_reconnect_mac,
    _save_bt_last_device,
)

try:
    from modules.bluetooth.bt_agent import start_agent_session as _start_agent_session
    from modules.bluetooth.bt_connect import disconnect_current as _disconnect_current
except Exception:
    _start_agent_session = None
    _disconnect_current = None

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

_reconnect_thread = None
_reconnect_stop = False
_reconnect_wakeup = None


def _pairing_active() -> bool:
    try:
        from modules.bluetooth import bt_connect as bc
        return bool(getattr(bc, "_PAIRING_ACTIVE", False))
    except Exception:
        return False


def _write_watcher_state(**kwargs):
    data = {"ts": _now(), "running": True}
    data.update(kwargs)
    _write_json_atomic(WATCHER_STATE_FILE, data)


def wake_auto_reconnect():
    global _reconnect_wakeup
    if _reconnect_wakeup is not None:
        _reconnect_wakeup.set()
        log.info("BT auto-reconnect: Watcher aufgeweckt")
    else:
        log.warn("BT auto-reconnect: kein Wakeup-Event vorhanden")


def start_auto_reconnect(S, settings):
    """Startet den Hintergrund-Watcher (einmal)."""
    global _reconnect_thread, _reconnect_stop, _reconnect_wakeup

    if _reconnect_thread and _reconnect_thread.is_alive():
        return

    _reconnect_stop = False
    _reconnect_wakeup = threading.Event()

    def _watcher():
        fail_streak = 0
        last_opportunistic = 0

        while not _reconnect_stop:
            try:
                if _pairing_active():
                    _sleep_s(5)
                    continue

                if _reconnect_wakeup is not None and _reconnect_wakeup.is_set():
                    _reconnect_wakeup.clear()
                    fail_streak = 0
                    log.info("BT auto-reconnect [Watcher]: geweckt — Timer zurückgesetzt")

                # Ziel-MAC: bt_last, aber Fahrzeug vor Kopfhörer
                mac, name = _resolve_reconnect_mac(settings)
                if not mac:
                    mac = _normalize_mac(settings.get("bt_last_mac", ""))
                    name = settings.get("bt_last_name", "") or mac
                if not mac:
                    _write_watcher_state(
                        sleeping=True, fail_count=0,
                        last_result="no_bt_last", next_action="wait_pair")
                    _sleep_s(20)
                    continue

                # Schon verbunden laut Status?
                if S.get("bt", False):
                    fail_streak = 0
                    _write_watcher_state(
                        sleeping=False, fail_count=0,
                        last_result="already_connected",
                        next_action="wait", current_mac=mac)
                    _sleep_s(20)
                    continue

                # BlueZ: schon Connected (Fahrzeug hat verbunden)?
                _, info = _btctl(f"info {mac}", timeout=5)
                if _parse_bool_from_info(info, "connected"):
                    S["bt"] = True
                    S["bt_on"] = True
                    S["bt_device"] = name or mac
                    S["bt_status"] = "verbunden"
                    _save_bt_last_device(settings, mac, name or mac)
                    note_link_event(mac, True, name or mac, "vehicle_connected")
                    _mark_reconnect_success(mac)
                    fail_streak = 0
                    if _src_state:
                        _src_state.set_bt_state("connected")
                        _src_state.set_bt_link_state("connected")
                    log.info(f"BT auto-reconnect: Fahrzeug bereits verbunden mac={mac}")
                    _write_watcher_state(
                        sleeping=False, fail_count=0,
                        last_result="vehicle_connected",
                        next_action="wait", current_mac=mac)
                    _sleep_s(15)
                    continue

                # Während Source-Transition / DAB nicht connecten
                if _src_state and _src_state.in_transition():
                    _sleep_s(5)
                    continue
                if S.get("radio_playing") and S.get("radio_type", "").upper() == "DAB":
                    _write_watcher_state(
                        sleeping=False, fail_count=fail_streak,
                        last_result="paused_dab", next_action="wait_dab",
                        current_mac=mac)
                    _sleep_s(10)
                    continue

                # Pause nach Host-down / Page-Timeout
                link = read_link_event()
                link_mac = _normalize_mac(link.get("mac", ""))
                link_reason = (link.get("reason") or "")
                link_age = _now() - int(link.get("ts", 0) or 0)
                if (
                    link_mac == mac
                    and not link.get("connected")
                    and link_reason in ("host_down", "page_timeout", "not_visible")
                    and link_age < HOST_DOWN_PAUSE_SECONDS
                ):
                    remain = HOST_DOWN_PAUSE_SECONDS - link_age
                    _write_watcher_state(
                        sleeping=True, fail_count=fail_streak,
                        last_result=f"pause_{link_reason}",
                        next_action="await_ignition",
                        current_mac=mac)
                    _sleep_s(min(30, max(5, remain)))
                    continue

                from modules.bluetooth.bt_connect import _RECONNECT_FAILS
                fail = _RECONNECT_FAILS.get(mac) or {}
                fr = (fail.get("last_failure_reason") or "")
                ft = int(fail.get("last_failure_ts", 0) or 0)
                if fr in ("host_down", "page_timeout") and ft:
                    age = _now() - ft
                    if age < HOST_DOWN_PAUSE_SECONDS:
                        _sleep_s(min(30, HOST_DOWN_PAUSE_SECONDS - age))
                        continue

                # Kopfhörer als Ziel überspringen, wenn Info klar ist
                if _device_type(info or "") == "headphones":
                    alt_mac, alt_name = _resolve_reconnect_mac(settings)
                    if alt_mac and alt_mac != mac:
                        log.info(
                            f"BT auto-reconnect: wechsle Ziel Kopfhörer→Fahrzeug "
                            f"{mac} → {alt_mac}")
                        mac, name = alt_mac, alt_name
                        _save_bt_last_device(settings, mac, name)

                if bt_connect_active():
                    _sleep_s(5)
                    continue

                # RF-Hinweis? Sonst nur selten opportunistisch Connect
                visible, _ = _ensure_device_visible(mac, timeout=4, require_rf=True)
                now = _now()
                if not visible:
                    if now - last_opportunistic < RECONNECT_OPPORTUNISTIC_SECONDS:
                        _write_watcher_state(
                            sleeping=True, fail_count=fail_streak,
                            last_result="await_vehicle_rf",
                            next_action="await_vehicle",
                            current_mac=mac)
                        _sleep_s(15)
                        continue
                    last_opportunistic = now
                    log.info(
                        f"BT auto-reconnect [Watcher]: opportunistischer Connect "
                        f"mac={mac} name={name}")
                else:
                    log.info(
                        f"BT auto-reconnect [Watcher]: RF ok — Connect "
                        f"mac={mac} name={name}")

                ok = connect_device(
                    mac, S, settings, allow_pair=False, require_rf=False)
                if ok:
                    log.info(f"BT auto-reconnect: ERFOLG mac={mac} name={name}")
                    fail_streak = 0
                    _write_watcher_state(
                        sleeping=False, fail_count=0,
                        last_result="success", next_action="wait",
                        current_mac=mac)
                    _sleep_s(20)
                    continue

                fail_streak += 1
                fr2 = (_RECONNECT_FAILS.get(mac) or {}).get(
                    "last_failure_reason") or "watcher_connect_failed"
                _mark_reconnect_failure(mac, fr2)
                log.info(
                    f"BT auto-reconnect: fehlgeschlagen #{fail_streak} "
                    f"mac={mac} reason={fr2}")

            except Exception as e:
                log.warn("BT auto-reconnect Watcher: " + str(e))
                fail_streak += 1

            if not S.get("bt", False) and fail_streak > 0:
                # Backoff: nach Host-down mindestens HOST_DOWN_PAUSE
                _backoff = min(30 * (2 ** min(fail_streak - 1, 3)), 300)
                fr3 = ""
                try:
                    from modules.bluetooth.bt_connect import _RECONNECT_FAILS as _F
                    fr3 = (_F.get(mac) or {}).get("last_failure_reason") or ""
                except Exception:
                    pass
                if fr3 in ("host_down", "page_timeout"):
                    _backoff = max(_backoff, HOST_DOWN_PAUSE_SECONDS)
                log.info(
                    f"BT auto-reconnect [Watcher]: Fehlschlag #{fail_streak} "
                    f"→ Schlaf {_backoff}s")
                _write_watcher_state(
                    sleeping=True, fail_count=fail_streak,
                    last_result="failed",
                    next_action="await_vehicle|bt_reconnect_last",
                    current_mac=_normalize_mac(settings.get("bt_last_mac", "")))

                _slept = 0
                while not _reconnect_stop and _slept < _backoff:
                    _sleep_s(10)
                    _slept += 10
                    if _reconnect_wakeup is not None and _reconnect_wakeup.is_set():
                        _reconnect_wakeup.clear()
                        fail_streak = 0
                        log.info("BT auto-reconnect [Watcher]: geweckt — erneut")
                        break
            else:
                _sleep_s(15)

        log.info("BT auto-reconnect Watcher: beendet")
        _write_watcher_state(
            running=False, sleeping=False,
            last_result="stopped", next_action="manual_reconnect")

    _reconnect_thread = threading.Thread(
        target=_watcher, daemon=True, name="bt_auto_reconnect")
    _reconnect_thread.start()
    log.info("BT auto-reconnect: Watcher gestartet")


def stop_auto_reconnect():
    global _reconnect_stop
    _reconnect_stop = True


def start_agent():
    """Legacy-Alias — nutzt bt_agent.start_agent_session()"""
    if _start_agent_session:
        return _start_agent_session()


def disconnect_device(S=None, settings=None):
    if S is None:
        S = {}
    if settings is None:
        settings = {}
    if _disconnect_current:
        return _disconnect_current(S, settings)
