#!/usr/bin/env python3
"""bt_watcher.py — Auto-Reconnect Watcher  v0.10.22
Ausgelagert aus bluetooth.py."""

from modules.bt_helpers import (
    _btctl, _run, _sleep_s, _now, _normalize_mac,
    _write_json_atomic, _read_json,
    _bt_adapter_up, _ensure_bt_on,
    _is_audio_device_info,
    WATCHER_STATE_FILE, RECONNECT_COOLDOWN, RECONNECT_FAIL_SOFT_LIMIT,
)
from modules.bt_devices import _get_known_devices
from modules.bt_audio import get_bt_sink
from modules.bt_connect import (
    connect_device,
    _reconnect_candidates, _should_try_reconnect,
    _mark_reconnect_failure, _mark_reconnect_success,
    _RECONNECT_LAST_TRY, _RECONNECT_FAILS,
    _ensure_device_visible,
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

# Watcher-State (lokal)
_reconnect_thread = None
_reconnect_stop = False
_reconnect_wakeup = None

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