#!/usr/bin/env python3
"""
modules/bluetooth.py — Public API Facade  v0.10.15

Ausgelagert in:
  bt_helpers.py   — Basis-Helfer, Konstanten, Adapter-Steuerung
  bt_agent.py     — BT-Agent, Pairing
  bt_devices.py   — Geräte-Datenbank, Scan
  bt_audio.py     — PulseAudio-Sink, A2DP-Management
  bt_connect.py   — Connect/Disconnect-Logik, Reconnect-State
  bt_watcher.py   — Auto-Reconnect Watcher

Diese Datei re-exportiert alle öffentlichen Funktionen für
Backward-Kompatibilität — Aufrufer müssen NICHTS ändern.
"""

# ── Alle öffentlichen Funktionen re-exportieren ───────────────────────────────

from modules.bt_helpers import (
    _bt_adapter_up, _ensure_bt_on, _ensure_bt_off,
    _normalize_mac, _valid_mac,
    _write_json_atomic, _read_json,
    _btctl, _run, _bg,
    _bt_connect_lock, _scan_lock,
    # Konstanten
    KNOWN_BT_FILE, DISCOVERED_BT_FILE, AGENT_STATE_FILE, WATCHER_STATE_FILE,
    PA_ENV, DEFAULT_SCAN_SECONDS, A2DP_WAIT_SECONDS,
    RECONNECT_COOLDOWN,
)

from modules.bt_agent import (
    read_agent_state, agent_is_alive,
    start_agent_session, stop_agent_session,
    agent_healthcheck, start_agent_health_thread,
    pair_with_agent,
    _ensure_agent,
    _AGENT_PROC, _AGENT_LOCK,
)

from modules.bt_devices import (
    _get_known_devices, _merge_known_update,
    _get_info_with_retries, _device_row_from_info,
    _load_bluez_db_devices, _dedupe_devices,
    _read_known_devices, _write_known_devices,
    stop_scan, scan_devices,
)

from modules.bt_audio import (
    get_bt_sink,
    _ensure_a2dp_sink, _set_pulseaudio_sink,
    _expected_pa_sink_for_mac,
)

from modules.bt_connect import (
    bt_toggle,
    connect_device, disconnect_current,
    repair_device, reconnect_last, reconnect_known_devices,
    _connect_device_inner,
    _reconnect_candidates, _should_try_reconnect,
    _mark_reconnect_failure, _mark_reconnect_success,
    _RECONNECT_LAST_TRY, _RECONNECT_FAILS,
)

from modules.bt_watcher import (
    wake_auto_reconnect,
    start_auto_reconnect, stop_auto_reconnect,
)

# ── Legacy-Aliase (für Code der alte Namen nutzt) ─────────────────────────────
start_agent     = start_agent_session
disconnect_device = disconnect_current

__all__ = [
    # Public API
    "bt_toggle",
    "scan_devices", "stop_scan",
    "connect_device", "disconnect_current", "disconnect_device",
    "repair_device", "reconnect_last", "reconnect_known_devices",
    "start_auto_reconnect", "stop_auto_reconnect", "wake_auto_reconnect",
    "get_bt_sink",
    "pair_with_agent",
    "read_agent_state", "agent_is_alive",
    "start_agent_session", "stop_agent_session",
    "agent_healthcheck", "start_agent_health_thread", "start_agent",
    # Interne Hilfsfunktionen (von webui.py / diagnose.py genutzt)
    "_get_known_devices", "_write_known_devices", "_normalize_mac", "_btctl",
    "_get_info_with_retries", "_load_bluez_db_devices",
]
