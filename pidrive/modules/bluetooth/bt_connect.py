#!/usr/bin/env python3
"""bt_connect.py — Connect/Disconnect-Logik und Reconnect-State  v0.10.55
Ausgelagert aus bluetooth.py."""

from modules.bluetooth.bt_helpers import (
    _btctl, _run, _bg, _normalize_mac, _valid_mac,
    _write_json_atomic, _read_json, _now, _sleep_s,
    _bt_adapter_up, _ensure_bt_on, _ensure_bt_off,
    _is_public_or_bredr, _is_audio_device_info,
    _parse_bool_from_info, _extract_name_from_info, _extract_alias_from_info,
    KNOWN_BT_FILE, DISCOVERED_BT_FILE,
    RECONNECT_COOLDOWN, RECONNECT_FAIL_SOFT_LIMIT, VISIBILITY_WAIT_SECONDS,
    PAIR_TIMEOUT_SECONDS, A2DP_WAIT_SECONDS, VISIBLE_TTL_SECONDS,
    _bt_connect_lock,
    RECENT_SEEN_SECONDS,
    _is_avrcp_controller, _device_type,
)
from modules.bluetooth.bt_agent import (
    _ensure_agent, pair_with_agent,
    read_agent_state, agent_is_alive,
)
from modules.bluetooth.bt_devices import (
    _get_known_devices, _merge_known_update,
    _get_info_with_retries, stop_scan,
    _mark_old_discovered_not_visible,
    _read_discovered_devices, _write_discovered_devices,
)
from modules.bluetooth.bt_audio import (
    _ensure_a2dp_sink, _set_pulseaudio_sink, bt_audio_autoroute,
    _set_raspotify_device, get_bt_sink,
    a2dp_stack_ready, try_recover_a2dp_stack, _is_a2dp_profile_error,
)
import threading
import subprocess
import time
import log
import ipc
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None

# Reconnect-State (lokal, wird von bt_watcher via Import referenziert)
_RECONNECT_LAST_TRY: dict = {}
_RECONNECT_FAILS: dict = {}

def _device_visible_in_recent_scan(mac: str) -> bool:
    mac = _normalize_mac(mac)
    now = _now()
    for d in _read_discovered_devices():
        if _normalize_mac(d.get("mac", "")) == mac:
            last_seen = int(d.get("last_seen_ts", 0) or 0)
            if d.get("visible_now") and last_seen and (now - last_seen) <= VISIBLE_TTL_SECONDS:
                return True
    return False


def _device_bluez_available(info: str) -> bool:
    low = (info or "").lower()
    return bool(info) and "not available" not in low and "name:" in low


def _bluez_is_paired(mac: str) -> bool:
    mac = _normalize_mac(mac)
    try:
        r = subprocess.run(
            ["bluetoothctl", "info", mac],
            capture_output=True, text=True, timeout=6,
        )
        return "paired: yes" in (r.stdout or "").lower()
    except Exception:
        return False


def _reset_discovery():
    stop_scan()
    for _ in range(3):
        _btctl("scan off", timeout=4)
        _sleep_s(0.4)


def _device_seen_during_scan(mac: str) -> tuple:
    """Prüft info + devices-Liste während aktivem Scan."""
    mac = _normalize_mac(mac)
    rc, info = _btctl(f"info {mac}", timeout=5)
    if rc == 0 and _device_bluez_available(info):
        return True, info
    _, out = _btctl("devices", timeout=5)
    if mac in (out or "").upper().replace("-", ":"):
        rc2, info2 = _btctl(f"info {mac}", timeout=5)
        if rc2 == 0 and _device_bluez_available(info2):
            return True, info2
    return False, info or ""


def _ensure_device_visible(mac, timeout=VISIBILITY_WAIT_SECONDS):
    mac = _normalize_mac(mac)

    rc, out = _btctl(f"info {mac}", timeout=5)
    if rc == 0 and _device_bluez_available(out):
        return True, out

    # Kurzer Discovery ohne scan on/off — nur info abrufen
    # scan on/off erzeugt viele D-Bus-Verbindungen → CPU-Last
    end = time.time() + timeout
    while time.time() < end:
        rc, out = _btctl(f"info {mac}", timeout=5)
        if rc == 0 and _device_bluez_available(out):
            return True, out
        _sleep_s(3.0)
    return False, out


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


def _resolve_reconnect_mac(settings):
    """Letztes BT-Gerät aus settings oder bekannten Audio-Geräten."""
    mac = _normalize_mac(settings.get("bt_last_mac", ""))
    if mac:
        return mac, settings.get("bt_last_name", "") or mac

    candidates = []
    for d in _get_known_devices():
        m = _normalize_mac(d.get("mac", ""))
        if not m or not d.get("paired"):
            continue
        name = (d.get("name") or "").strip()
        score = 0
        if d.get("audio_candidate", True):
            score += 2
        if name and ":" not in name.replace("-", ":")[:8]:
            score += 3
        if d.get("trusted"):
            score += 1
        candidates.append((score, m, name or m))

    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[2].lower()))
        _, mac, name = candidates[0]
        return mac, name
    return "", ""


def _save_bt_last_device(settings, mac, name):
    settings["bt_last_mac"] = mac
    settings["bt_last_name"] = name
    try:
        from settings import save_settings as _ss
        _ss(settings)
    except Exception:
        pass


def _ensure_a2dp_stack_or_recover(*, allow_bluetooth_restart=True):
    ready, reason = a2dp_stack_ready()
    if ready:
        return True
    log.warn(f"BT connect: A2DP-Stack nicht bereit ({reason}) — Recovery")
    return try_recover_a2dp_stack(include_bluetooth=allow_bluetooth_restart)


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
        try:
            from modules.bluetooth.bt_watcher import stop_auto_reconnect as _stop_watcher
            _stop_watcher()
        except Exception:
            pass
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

    # Watcher aufwecken (lazy import verhindert Circular-Import mit bt_watcher)
    try:
        from modules.bluetooth.bt_watcher import wake_auto_reconnect as _wake
        _wake()
    except Exception:
        pass

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


def _ensure_avrcp_player(mac: str, timeout: int = 8) -> bool:
    """
    Fix C: AVRCP-Controller-Profil connecten und warten bis BlueZ
    /player0 erstellt. BMW zeigt erst dann Metadaten im iDrive-Display.
    """
    mac_norm = _normalize_mac(mac)
    dev_path = f"/org/bluez/hci0/dev_{mac_norm.replace(':', '_')}"
    player_path = dev_path + "/player0"

    # Prüfen ob player0 schon da ist
    r = _run(
        f"dbus-send --system --print-reply --dest=org.bluez {dev_path} "
        f"org.freedesktop.DBus.Properties.GetAll string:org.bluez.MediaControl1 2>/dev/null",
        timeout=3
    )
    if "player0" in (r or ""):
        log.info(f"AVRCP player: /player0 bereits vorhanden für {mac}")
        return True

    # avrcp-controller Profil explizit connecten
    log.info(f"AVRCP player: Verbinde avrcp-controller Profil für {mac}")
    _run(
        f"bluetoothctl -- connect {mac_norm} 2>/dev/null",
        timeout=5
    )

    # Auf /player0 warten
    import time as _t
    deadline = _t.time() + timeout
    while _t.time() < deadline:
        r2 = _run(
            f"dbus-send --system --print-reply --dest=org.bluez / "
            f"org.freedesktop.DBus.ObjectManager.GetManagedObjects 2>/dev/null",
            timeout=3
        )
        if r2 and "player0" in r2:
            log.info(f"AVRCP player: /player0 erschienen für {mac}")
            return True
        _t.sleep(1.0)

    log.warn(f"AVRCP player: /player0 nicht erschienen nach {timeout}s für {mac}")
    return False


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
        from modules.radio import scanner as _scanner
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

    _save_bt_last_device(settings, mac, name)

    visible, info = _ensure_device_visible(mac, timeout=VISIBILITY_WAIT_SECONDS)
    if not visible:
        ipc.write_progress("Bluetooth", "Nicht gefunden — Gerät einschalten", color="red")
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

    if not _ensure_a2dp_stack_or_recover():
        log.warn("BT connect: A2DP-Stack nicht bereit — sudo systemctl restart wireplumber")

    connected_ok, conn_info = _ensure_connected(mac, retries=3)
    if not connected_ok:
        if _is_a2dp_profile_error(conn_info):
            ipc.write_progress(
                "Bluetooth",
                "A2DP fehlt — Audio-Stack neu starten (kein Pairing)",
                color="orange",
            )
            try_recover_a2dp_stack()
            _mark_reconnect_failure(mac, "a2dp_unavailable")
        else:
            ipc.write_progress("Bluetooth", "Verbindung fehlgeschlagen", color="red")
            _mark_reconnect_failure(mac, "connect_failed")
        if _src_state:
            _src_state.set_bt_state("failed")
            _src_state.set_bt_link_state("failed")
            _src_state.set_bt_audio_state("no_sink")
        _sleep_s(3)
        ipc.clear_progress()
        S["bt"] = False
        S["bt_status"] = "getrennt"
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    sink_ok, pa_sink = _ensure_a2dp_sink(mac, timeout=A2DP_WAIT_SECONDS)
    if not sink_ok:
        log.warn(f"BT connect: Link ok, aber kein A2DP-Sink mac={mac}")
    else:
        # A2DP-Sink aktiv → als Default setzen + alle Streams verschieben
        _set_pulseaudio_sink(pa_sink)
        settings["audio_output"] = "bt"
        try:
            from settings import save_settings as _ss_bt; _ss_bt(settings)
        except Exception: pass

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
        # v0.10.55: PA-Sink-Cache nach BT-Connect invalidieren
        try:
            from modules import audio as _aud_bt; _aud_bt.invalidate_sink_cache()
        except Exception: pass
        _src_state.set_audio_route("bt" if sink_ok else "klinke")
        # Audio-Decision-File aktualisieren — damit status/audio status korrekt
        try:
            from modules import audio as _aud2
            _decision = _aud2.decide_audio_route(settings)
            _aud2.apply_audio_route(_decision)
        except Exception as _ae:
            log.warn(f"BT-Connect: audio route update: {_ae}")

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
        # Fix C: AVRCP-Player nur für AVRCP-Controller (BMW), nicht Kopfhörer
        try:
            _info = _btctl(f"info {mac}", timeout=5)[1] or ""
            _dtype = _device_type(_info)
            log.info(f"BT connect: Geräteklasse: {_dtype} mac={mac}")
            if _dtype == "avrcp_controller":
                _ensure_avrcp_player(mac)
            else:
                log.info(f"BT connect: AVRCP-Player übersprungen ({_dtype})")
        except Exception as _dce:
            log.warn(f"BT connect: device_type: {_dce}")

    # BT-Backup nach Erfolg
    try:
        from modules.bluetooth import bt_backup as _btbak
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
                import ipc as _bipc; _bipc.append_trigger("radio_restart_on_bt")
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
    stop_scan()
    _reset_discovery()

    # Schritt 1: Alten Bond entfernen (behebt "BT bond: inkonsistent")
    _btctl(f"disconnect {mac}", timeout=6)
    _btctl(f"remove {mac}", timeout=6)
    log.info(f"BT repair: alter Bond entfernt mac={mac}")
    _sleep_s(1)

    remaining = [
        d for d in _read_discovered_devices()
        if _normalize_mac(d.get("mac", "")) != mac
    ]
    _write_discovered_devices(remaining)

    # Schritt 2: Scan starten und warten bis Gerät sichtbar
    ipc.write_progress("Bluetooth", f"Suche {name[:16]}... (Pairing-Modus!)", color="blue")
    log.info(f"BT repair: Scan — warte auf Gerät (Pairing-Modus noetig!)")
    _btctl("scan on", timeout=3)
    _device_visible = False
    _info = ""
    for _attempt in range(45):
        _sleep_s(1)
        seen, _info = _device_seen_during_scan(mac)
        if not seen:
            for d in _read_discovered_devices():
                if _normalize_mac(d.get("mac", "")) == mac:
                    seen = True
                    name = d.get("name", name)
                    break
        if seen:
            _device_visible = True
            if _info and "Name:" in _info:
                for line in _info.splitlines():
                    if line.strip().startswith("Name:"):
                        name = line.split("Name:", 1)[1].strip() or name
                        break
            log.info(f"BT repair: Gerät sichtbar nach {_attempt+1}s")
            break
        if _attempt in (4, 14, 24):
            _run("(echo 'scan on'; sleep 6) | bluetoothctl 2>/dev/null", timeout=10)
        ipc.write_progress("Bluetooth",
            f"Warte auf {name[:14]}... ({_attempt+1}/45s)", color="blue")

    if not _device_visible:
        log.warn(f"BT repair: Gerät nicht sichtbar — Pairing-Modus aktiv?")
        ipc.write_progress("Bluetooth", f"Gerät nicht gefunden — Pairing-Modus?", color="red")
        _btctl("scan off", timeout=3)
        _sleep_s(2)
        ipc.clear_progress()
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    # Schritt 3: Pair (Scan bleibt an — manche Headsets brauchen das)
    paired_ok, pair_info = _ensure_paired(mac, timeout=PAIR_TIMEOUT_SECONDS)
    _btctl("scan off", timeout=3)
    if not paired_ok:
        ipc.write_progress("Bluetooth", "Pairing fehlgeschlagen", color="red")
        _sleep_s(3)
        ipc.clear_progress()
        S["menu_rev"] = S.get("menu_rev", 0) + 1
        return False

    _merge_known_update(mac, name=name, known=True, paired=True, trusted=True, source="repair")
    ok = connect_device(mac, S, settings)
    log.info(f"BT repair: {'OK' if ok else 'FAIL'} mac={mac}")
    S["menu_rev"] = S.get("menu_rev", 0) + 1
    return ok


def reconnect_last(S, settings):
    mac, name = _resolve_reconnect_mac(settings)

    if not mac:
        ipc.write_progress("Bluetooth", "Kein letztes Gerät", color="orange")
        log.warn("BT reconnect_last: keine bt_last_mac und kein Kandidat")
        _sleep_s(2)
        ipc.clear_progress()
        return False

    _save_bt_last_device(settings, mac, name)

    try:
        from modules.bluetooth.bt_watcher import wake_auto_reconnect as _wake
        _wake()
    except Exception:
        pass

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


