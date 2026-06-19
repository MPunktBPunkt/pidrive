#!/usr/bin/env python3
"""bt_audio.py — Audio-Sink und A2DP-Management (PipeWire/PulseAudio)  v0.11.96

Vollständiges A2DP Auto-Routing:
- PipeWire/WirePlumber: BT A2DP automatisch; Legacy-PA: load-module
- Schaltet Card-Profil auf a2dp-sink
- Setzt Default-Sink
- Verschiebt alle laufenden Streams
"""

from modules.bluetooth.bt_helpers import (
    _run, _normalize_mac, _read_json, _now, _sleep_s,
    PA_ENV, A2DP_WAIT_SECONDS, find_bt_sink_for_mac, list_pa_sink_names,
)
import subprocess
import time
import log
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None


# ── Interne Helfer ────────────────────────────────────────────────────────────

def _pa_run(cmd, timeout=4):
    """PA-Kommando mit korrektem PULSE_SERVER ausführen."""
    try:
        r = subprocess.run(PA_ENV + " " + cmd, shell=True,
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _pa_sinks():
    """Liste aller PA-Sinks: [{id, name, state}]"""
    out = _pa_run("pactl list sinks short 2>/dev/null")
    result = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result.append({"id": parts[0], "name": parts[1],
                           "state": parts[4] if len(parts) > 4 else ""})
    return result


def _pa_sink_inputs():
    """Liste aller PA-Sink-Inputs: [{id, sink}]"""
    out = _pa_run("pactl list short sink-inputs 2>/dev/null")
    result = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            result.append({"id": parts[0], "sink": parts[1]})
    return result


def _pa_cards():
    """Roher pactl list cards Output."""
    return _pa_run("pactl list cards 2>/dev/null", timeout=5)


def _normalize_mac(mac: str) -> str:
    return mac.upper().replace("-", ":")


def _expected_pa_sink_for_mac(mac: str) -> str:
    return "bluez_sink." + _normalize_mac(mac).replace(":", "_") + ".a2dp_sink"


def _expected_pa_card_for_mac(mac: str) -> str:
    return "bluez_card." + _normalize_mac(mac).replace(":", "_")


def _is_a2dp_profile_error(text: str) -> bool:
    low = (text or "").lower()
    return any(x in low for x in (
        "profile-unavailable", "protocol not available",
        "br-connection-profile-unavailable",
    ))


def a2dp_stack_ready() -> tuple:
    """WirePlumber muss MediaEndpoint1 bei BlueZ registrieren."""
    out = _run(
        "dbus-send --system --print-reply --dest=org.bluez / "
        "org.freedesktop.DBus.ObjectManager.GetManagedObjects 2>/dev/null",
        timeout=5,
    )
    if "org.bluez.MediaEndpoint1" in (out or ""):
        return True, ""
    return False, "no_media_endpoints"


def wait_for_a2dp_stack(timeout=25, poll=0.5) -> bool:
    """Beim Boot kann WirePlumber Endpoints erst Sekunden nach Start registrieren."""
    deadline = time.time() + max(0, float(timeout))
    while time.time() < deadline:
        ready, _ = a2dp_stack_ready()
        if ready:
            return True
        _sleep_s(poll)
    return False


_RECOVERY_COOLDOWN_S = 90
_last_recovery_ts = 0.0


def _bt_device_connected() -> bool:
    out = _run("bluetoothctl devices Connected 2>/dev/null", timeout=4)
    return bool((out or "").strip())


def try_recover_a2dp_stack(include_bluetooth=False) -> bool:
    """WirePlumber/PipeWire neu starten. Bluetooth nur als letztes Mittel."""
    global _last_recovery_ts
    now = time.time()
    if now - _last_recovery_ts < _RECOVERY_COOLDOWN_S:
        log.info("[BT-AUDIO] A2DP-Recovery übersprungen (Cooldown aktiv)")
        ready, _ = a2dp_stack_ready()
        return ready

    if include_bluetooth and _bt_device_connected():
        log.info("[BT-AUDIO] A2DP-Recovery: BT verbunden — bluetooth-Restart übersprungen")
        include_bluetooth = False

    log.info("[BT-AUDIO] A2DP-Stack Recovery: pipewire → wireplumber"
             + (" → bluetooth" if include_bluetooth else ""))
    # Reihenfolge wichtig: PipeWire zuerst, WirePlumber danach, Bluetooth zuletzt
    services = ["pipewire", "pipewire-pulse", "wireplumber"]
    if include_bluetooth:
        services.append("bluetooth")
    ok_any = False
    failed = []
    for svc in services:
        rc = subprocess.run(
            f"sudo -n systemctl restart {svc}",
            shell=True, capture_output=True, text=True, timeout=25,
        )
        if rc.returncode == 0:
            ok_any = True
        else:
            failed.append(svc)
            err = (rc.stderr or "").strip()[:80]
            log.warn(
                f"[BT-AUDIO] restart {svc}: rc={rc.returncode}"
                + (f" ({err})" if err else "")
            )
    if failed:
        log.warn(f"[BT-AUDIO] sudo fehlgeschlagen für: {', '.join(failed)}"
                 " — auf dem Pi: sudo ~/pidrive/scripts/fix-bt-a2dp.sh")
    if not ok_any:
        return False
    _last_recovery_ts = time.time()
    return wait_for_a2dp_stack(timeout=20)


# ── A2DP Profile erzwingen ────────────────────────────────────────────────────

def _force_a2dp_profile(mac: str) -> bool:
    """
    Schaltet die BT-Card auf A2DP-Sink-Profil um.
    Gibt True zurück wenn erfolgreich oder bereits aktiv.
    """
    card = _expected_pa_card_for_mac(mac)
    cards_out = _pa_cards()

    # Prüfe ob Card überhaupt sichtbar
    if card not in cards_out and card.lower() not in cards_out.lower():
        log.warn(f"[BT-AUDIO] PA-Card nicht gefunden: {card}")
        return False

    # Prüfe ob a2dp-sink bereits aktiv
    if "a2dp-sink" in cards_out or "a2dp_sink" in cards_out:
        log.info(f"[BT-AUDIO] A2DP-Profil bereits aktiv: {card}")
        return True

    # Profile versuchen (unterschiedliche BlueZ-Versionen)
    for profile in ("a2dp-sink", "a2dp_sink", "A2DP"):
        r = subprocess.run(
            PA_ENV + f" pactl set-card-profile {card} {profile} 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            log.info(f"[BT-AUDIO] A2DP-Profil gesetzt: {card} → {profile}")
            return True

    log.warn(f"[BT-AUDIO] Konnte A2DP-Profil nicht setzen: {card}")
    return False


# ── module-bluetooth-discover laden ──────────────────────────────────────────

def _ensure_bt_pa_modules():
    """Lädt BT-PA-Module — nur für Legacy-PulseAudio nötig.
    Mit PipeWire/WirePlumber: BT wird automatisch erkannt, kein load-module.
    """
    # PipeWire erkennen: pactl info zeigt "PulseAudio" oder "PipeWire"
    _info = _pa_run("pactl info 2>/dev/null")
    if "PipeWire" in _info or "pipewire" in _info.lower():
        log.info("[BT-AUDIO] PipeWire erkannt — module-bluetooth-discover nicht nötig")
        return False
    modules_out = _pa_run("pactl list modules short 2>/dev/null")
    changed = False
    for mod in ("module-bluetooth-discover", "module-bluetooth-policy"):
        if mod not in modules_out:
            r = subprocess.run(
                PA_ENV + f" pactl load-module {mod} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                log.info(f"[BT-AUDIO] Modul geladen: {mod}")
                changed = True
            else:
                log.warn(f"[BT-AUDIO] Modul konnte nicht geladen werden: {mod}")
    return changed


# ── Kern: A2DP-Sink sicherstellen ────────────────────────────────────────────

def _ensure_a2dp_sink(mac, timeout=A2DP_WAIT_SECONDS):
    """
    Stellt sicher dass ein A2DP-Sink für mac verfügbar ist.
    Strategie:
      1. BT-PA-Module laden falls nötig
      2. Card-Profil auf a2dp-sink schalten
      3. Warten bis Sink erscheint (timeout Sekunden)
    Gibt (ok, sink_name) zurück.
    """
    deadline = time.time() + timeout
    hint = _expected_pa_sink_for_mac(mac)

    found = find_bt_sink_for_mac(mac, list_pa_sink_names())
    if found:
        return True, found

    _ensure_bt_pa_modules()
    _sleep_s(1.0)
    _force_a2dp_profile(mac)
    _sleep_s(1.5)

    while time.time() < deadline:
        found = find_bt_sink_for_mac(mac, list_pa_sink_names())
        if found:
            log.info(f"[BT-AUDIO] A2DP-Sink erschienen: {found}")
            return True, found
        _sleep_s(1.0)

    log.warn(f"[BT-AUDIO] A2DP-Sink nach {timeout}s nicht verfügbar (erwartet ~{hint})")
    return False, hint


# ── Default-Sink + Stream-Routing ────────────────────────────────────────────

def _set_pulseaudio_sink(sink_name):
    """
    Setzt PA Default-Sink und verschiebt ALLE laufenden Streams.
    """
    if not sink_name:
        return False
    try:
        # Warten bis Sink sichtbar
        for _ in range(8):
            if sink_name in _pa_run("pactl list sinks short 2>/dev/null"):
                break
            _sleep_s(1.0)

        # Default-Sink setzen
        r = subprocess.run(
            PA_ENV + " pactl set-default-sink " + sink_name,
            shell=True, capture_output=True, text=True, timeout=5
        )
        if r.returncode != 0:
            log.warn("[BT-AUDIO] set-default-sink fehlgeschlagen: " + sink_name)
            return False
        log.info("[BT-AUDIO] Default-Sink → " + sink_name)

        # Alle laufenden Streams verschieben
        moved = 0
        for inp in _pa_sink_inputs():
            r2 = subprocess.run(
                PA_ENV + f" pactl move-sink-input {inp['id']} {sink_name}",
                shell=True, capture_output=True, text=True, timeout=3
            )
            if r2.returncode == 0:
                moved += 1
        if moved:
            log.info(f"[BT-AUDIO] {moved} Stream(s) auf {sink_name} verschoben")
        return True

    except Exception as e:
        log.error("[BT-AUDIO] sink-Fehler: " + str(e))
        return False


# ── BT vollständig auf A2DP routen ───────────────────────────────────────────

def bt_audio_autoroute(mac: str, settings=None) -> bool:
    """
    Hauptfunktion: Nach BT-Connect vollständiges A2DP-Routing.
    - Sink sicherstellen (mit Modul-Nachladen + Profil-Wechsel)
    - Default-Sink setzen
    - Alle Streams verschieben
    - settings["audio_output"] = "bt" setzen
    Gibt True zurück wenn A2DP aktiv.
    """
    sink_ok, pa_sink = _ensure_a2dp_sink(mac, timeout=A2DP_WAIT_SECONDS)

    if not sink_ok:
        log.warn(f"[BT-AUDIO] Auto-Route fehlgeschlagen: kein A2DP-Sink für {mac}")
        return False

    _set_pulseaudio_sink(pa_sink)

    # settings aktualisieren
    if settings is not None:
        settings["audio_output"] = "bt"
        settings["bt_last_mac"]  = mac
        try:
            from settings import save_settings as _ss
            _ss(settings)
        except Exception:
            pass

    log.info(f"[BT-AUDIO] Auto-Route OK: {mac} → {pa_sink}")
    return True


def get_bt_sink():
    """Gibt ersten aktiven BT A2DP Sink zurück (oder '')."""
    for s in _pa_sinks():
        low = s["name"].lower()
        if "bluez" in low and "a2dp" in low:
            return s["name"]
    return ""


def _set_raspotify_device(device, restart=True):
    conf = "/etc/raspotify/conf"
    try:
        try:
            with open(conf) as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            # Nur warnen wenn raspotify installiert ist, nicht bei librespot-only Setups
            import os as _os_ra, subprocess as _sp_ra
            _rasp_inst = _sp_ra.run(["systemctl","is-enabled","raspotify"],
                                    capture_output=True, text=True, timeout=2).returncode == 0
            if _rasp_inst:
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
