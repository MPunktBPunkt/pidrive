#!/usr/bin/env python3
"""dab_play.py — DAB+ Wiedergabe via welle-cli  v0.10.23"""

from modules.dab_helpers import (
    _write_json_atomic, _read_json, _run, _truncate_file, _normalize_station,
    _new_session_id, _set_session, _get_session, _clear_session,
    _write_play_debug, _reset_runtime_dls_fields, _set_dab_status_fields,
    _parse_welle_status_line, _append_play_debug_line, _get_dab_gain,
    _err_file_for_session,
    ERR_FILE, PLAY_DEBUG_FILE, C_DAB,
    _player_proc, _scan_running,
    _rtlsdr, _src_state, _audio,
)
from modules.dab_dls import _stop_dls_thread, _start_dls_thread
from modules.dab_scan import load_stations, is_scan_running
import os, re, json, time, shlex, threading, subprocess
import log, ipc

def play_station(station, S, settings=None):
    global _player_proc

    stop(S)

    if settings is not None:
        settings["last_source"] = "dab"
        settings["last_dab_station"] = {
            "name": station.get("name", ""),
            "channel": station.get("channel", ""),
            "service_id": station.get("service_id", ""),
            "ensemble": station.get("ensemble", ""),
            "url_mp3": station.get("url_mp3", ""),
        }
        try:
            from settings import save_settings as _save_s
            _save_s(settings)
        except Exception as e:
            log.warn(f"DAB: save_settings failed: {e}")

    ch = station.get("channel", "")
    name = station.get("name", "")
    sid = str(station.get("service_id", "") or "").strip()

    if not ch:
        log.error(f"DAB play: kein channel station={station!r}")
        return

    try:
        if (S.get("radio_playing")
                and S.get("radio_type") == "DAB"
                and S.get("radio_name") == name):
            log.info(f"DAB play: bereits aktiv — kein Neustart name={name!r}")
            return
    except Exception:
        pass

    if _rtlsdr:
        if not _rtlsdr.detect_usb().get("present"):
            S["radio_playing"] = False
            S["radio_station"] = "RTL-SDR nicht gefunden"
            log.error("DAB: kein RTL-SDR")
            return
        if _rtlsdr.is_busy():
            S["radio_playing"] = False
            S["radio_station"] = "RTL-SDR belegt"
            log.warn(f"DAB: RTL-SDR belegt vor play {name} [{ch}]")
            return

    session_id = _new_session_id()
    _set_session(session_id)
    _stop_dls_thread()
    _sess_err_file = _err_file_for_session(session_id)
    _truncate_file(_sess_err_file)
    _reset_runtime_dls_fields(S)

    _set_dab_status_fields(
        S,
        dab_session_id=session_id,
        dab_state="starting",
        dab_sync_ok=False,
        dab_last_error="",
        dab_channel=ch,
        dab_service_id=sid,
        dab_ensemble=station.get("ensemble", ""),
        dab_audio_ready=False,
        dab_pcm_seen=False,
        dab_sync_seen=False,
        dab_superframe_seen=False,
    )

    _write_play_debug({
        "session_id": session_id,
        "name": name,
        "channel": ch,
        "service_id": sid,
        "ensemble": station.get("ensemble", ""),
        "started_ts": time.time(),
        "state": "starting",
        "recent_lines": [],
        "last_dls_raw": "",
        "last_dls_artist": "",
        "last_dls_track": "",
    })

    try:
        from modules import audio as _audio
        _mpv_raw = _audio.get_mpv_args(settings, source="dab")
        _adec = _audio.get_last_decision()

        _gain = _get_dab_gain(settings)
        _ppm_val = int(settings.get("ppm_correction", 0)) if settings else 0
        _name_q = shlex.quote(name)

        if _adec.get("reason") == "pulseaudio_inactive" or _adec.get("effective") == "none":
            log.info("DAB: PulseAudio inaktiv — kein Abbruch (ALSA-direkt)")

        _welle_cmd = (
            "welle-cli -c " + ch + " -g " + _gain +
            " -p " + _name_q +
            " < /dev/null" +
            " 2>" + _sess_err_file
        )

        # ── v0.10.23: Saubere ALSA-Umgebung für welle-cli ────────────────────
        # Problem: pidrive_core.service hat Environment=PULSE_SERVER=...
        #          → wird von welle-cli geerbt
        #          → PulseAudio ALSA-Plugin (pcm.!default {type pulse})
        #            fängt ALSA-Calls ab → falscher Sink → kein Ton
        # Fix: PULSE_SERVER aus der Kindprozess-Umgebung entfernen,
        #      damit ALSA direkt auf die Hardware-Karte (Card 1 = Klinke) geht.
        # ── v0.10.23 (korrigiert): ALSA→PulseAudio-Routing für welle-cli ────────
        # PULSE_SERVER BEHALTEN: welle-cli nutzt ALSA default = PA-Plugin → System-PA
        # PA-Default-Sink wurde von get_mpv_args() auf Klinke gesetzt (s.o.)
        # PULSE_SINK ENTFERNEN: verhindert PA-Init-Timing-Konflikt mit RTL-SDR
        #   (war der echte Sync-Bug aus v0.9.30, nicht PULSE_SERVER selbst)
        _welle_env = dict(os.environ)
        # v0.10.23: PULSE_SERVER entfernt — welle-cli läuft ALSA-direkt (stabiler)
        for _k in ("PULSE_SERVER", "PULSE_SINK", "PULSE_AUDIO"):
            _welle_env.pop(_k, None)
        # PULSE_SERVER entfernt → welle-cli nutzt ALSA default direkt (wie Konsolenstart)

        # /etc/asound.conf prüfen und bei Bedarf korrigieren
        # (ohne asound.conf → ALSA default = Card 0 = HDMI → kein Ton)
        try:
            _hpcard = _audio._get_headphone_card()
            _asound_ok_line = f"defaults.pcm.card {_hpcard}"
            _asound_path = "/etc/asound.conf"
            _asound_exists = os.path.exists(_asound_path)
            _asound_ok = _asound_ok_line in (
                open(_asound_path).read() if _asound_exists else ""
            )
            if not _asound_ok:
                _asound_content = (
                    "# PiDrive: ALSA Default auf Klinke\n"
                    f"defaults.pcm.card {_hpcard}\n"
                    f"defaults.ctl.card {_hpcard}\n"
                    "defaults.pcm.device 0\n"
                )
                with open(_asound_path, "w") as _af:
                    _af.write(_asound_content)
                log.info(f"DAB: /etc/asound.conf geschrieben → card {_hpcard} (Klinke)")
            else:
                log.info(f"DAB: /etc/asound.conf OK (card {_hpcard})")
        except Exception as _ae:
            log.warn(f"DAB: asound.conf check/write: {_ae}")

        # v0.10.23: Audio-Routing-Debug beim Start
        _pa_default = ""
        try:
            import subprocess as _sppa
            _pa_default = _sppa.run(
                "PULSE_SERVER=unix:/var/run/pulse/native pactl get-default-sink 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=2
            ).stdout.strip()
        except Exception:
            pass

        _write_play_debug({
            "audio_decision": _adec,
            "welle_cmd": _welle_cmd,
            "pulse_server_in_env": "PULSE_SERVER" in _welle_env,
            "pulse_sink_in_env": "PULSE_SINK" in _welle_env,
            "pa_default_sink_before_start": _pa_default,
            "ppm": _ppm_val,
            "gain": _gain,
            "sess_err_file": _sess_err_file,
        })

        log.info(
            f"DAB play: START name={name!r} channel={ch} sid={sid!r} gain={_gain} "            f"session={session_id} | "            f"PULSE_SERVER={'✓' if 'PULSE_SERVER' in _welle_env else '✗'} "            f"PA_Default={_pa_default or '(nicht gesetzt)'}"
        )

        if _rtlsdr:
            try:
                _player_proc = _rtlsdr.start_process(
                    _welle_cmd,
                    owner="dab_play",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=_welle_env,   # ← ohne PULSE_SINK (Timing-Fix), mit PULSE_SERVER
                )
            except Exception as e:
                _set_dab_status_fields(
                    S,
                    dab_state="start_failed",
                    dab_last_error=str(e),
                    radio_playing=False,
                )
                _write_play_debug({
                    "state": "start_failed",
                    "error": str(e),
                })
                log.error("DAB: RTL-SDR Lock/Start: " + str(e))
                return
        else:
            _player_proc = subprocess.Popen(
                _welle_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_welle_env,   # ← ohne PULSE_SINK (Timing-Fix), mit PULSE_SERVER
            )

        lock_wait_max = 12
        sync_ok = False
        pcm_seen = False
        sync_seen = False
        superframe_seen = False
        last_err = ""

        for _ in range(lock_wait_max):
            time.sleep(1.0)
            if _get_session() != session_id:
                log.warn(f"DAB play: session changed during lock wait {session_id}")
                return

            # v0.10.23: _sess_err_file statt globalem ERR_FILE (Session-Isolation)
            _err_path = _sess_err_file if os.path.exists(_sess_err_file) else ERR_FILE
            if not os.path.exists(_err_path):
                continue

            try:
                with open(_err_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [ln.strip() for ln in f.readlines()[-30:] if ln.strip()]

                for ln in lines[-12:]:
                    parsed = _parse_welle_status_line(ln)
                    if parsed:
                        _append_play_debug_line(parsed[0], parsed[1])

                    low = ln.lower()
                    if "found sync" in low and not sync_seen:
                        sync_seen = True
                        log.info(f"DAB lock: ✓ found sync — {ln[:80]}")
                    if "superframe sync succeeded" in low and not superframe_seen:
                        superframe_seen = True
                        log.info(f"DAB lock: ✓ superframe sync — {ln[:80]}")
                    if "pcm name:" in low and not pcm_seen:
                        pcm_seen = True
                        log.info(f"DAB lock: ✓ PCM bereit — {ln[:80]}")
                    if any(x in low for x in ["failed", "lost coarse", "cannot open",
                                               "permission denied", "xrun", "error"]):
                        if ln[:180] != last_err:
                            last_err = ln[:180]
                            log.warn(f"DAB stderr: {ln[:100]}")

                if sync_seen and superframe_seen:
                    sync_ok = True

                if sync_ok or pcm_seen:
                    break

            except Exception as e:
                last_err = str(e)

        dab_state = "locked" if sync_ok else ("pcm_only" if pcm_seen else "no_lock")
        _err_short = last_err[:60] if last_err else "OK"
        log.info(f"DAB lock-wait done: state={dab_state} sync={sync_ok} pcm={pcm_seen} err={_err_short!r}")
        _set_dab_status_fields(
            S,
            dab_state=dab_state,
            dab_sync_ok=sync_ok,
            dab_last_error=last_err,
            dab_pcm_seen=pcm_seen,
            dab_sync_seen=sync_seen,
            dab_superframe_seen=superframe_seen,
            dab_audio_ready=bool(pcm_seen),
        )

        _write_play_debug({
            "state": dab_state,
            "sync_ok": sync_ok,
            "pcm_seen": pcm_seen,
            "sync_seen": sync_seen,
            "superframe_seen": superframe_seen,
            "last_error_line": last_err,
            "lock_wait_seconds": lock_wait_max,
        })

        # Nur als "läuft" markieren wenn tatsächlich Sync oder PCM vorhanden
        if sync_ok or pcm_seen:
            S["radio_playing"] = True
            if not pcm_seen:
                log.warn("DAB: no_lock aber sync vorhanden — Audio möglicherweise instabil")
        else:
            # no_lock: DAB läuft noch (welle-cli), aber Status ehrlich halten
            S["radio_playing"] = False
            log.warn(f"DAB: no_lock — radio_playing=False, welle-cli läuft weiter (session={session_id})")
        S["radio_station"] = "DAB: " + name
        S["radio_name"] = name
        S["radio_type"] = "DAB"
        S["control_context"] = "radio_dab"

        _start_dls_thread(session_id, name, S)
        log.action("DAB", f"Wiedergabe: {name} ({ch}, sid={sid or '-'}) session={session_id}")

    except Exception as e:
        S["radio_playing"] = False
        S["radio_station"] = "DAB Fehler"
        _set_dab_status_fields(S, dab_state="exception", dab_last_error=str(e))
        _write_play_debug({
            "state": "exception",
            "error": str(e),
        })
        log.error(f"DAB play Fehler: {e}")


def stop(S):
    global _player_proc, _scan_running

    log.info("DAB stop: requested")
    _scan_running = False

    _stop_dls_thread()
    _clear_session()

    if _player_proc:
        try:
            _player_proc.terminate()
            _player_proc.wait(timeout=2)
        except Exception:
            pass

    if _rtlsdr:
        try:
            _rtlsdr.stop_process()
        except Exception:
            pass

    import subprocess as _sp
    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, timeout=3, capture_output=True)

    _player_proc = None

    if S.get("radio_type") == "DAB":
        S["radio_playing"] = False
        S["radio_station"] = ""
        # v0.10.23: Clear DLS/artist/track fields on stop to avoid stale display
        S["artist"] = ""
        S["track"] = ""
        S["dls_text"] = ""
        S["radio_name"] = ""

    _set_dab_status_fields(
        S,
        dab_state="stopped",
        dab_sync_ok=False,
        dab_audio_ready=False,
        dab_dls_text="",
    )

    time.sleep(1.0)
    log.info("DAB stop: done")


def play_by_name(name, S, settings=None, service_id=""):
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        stations = data.get("stations", data) if isinstance(data, dict) else data
        service_id = str(service_id or "").strip().lower()

        if service_id:
            for s in stations:
                sid = str(s.get("service_id", "") or "").strip().lower()
                if sid and sid == service_id:
                    log.info(f"DAB play_by_name service_id match name={name!r} sid={service_id}")
                    play_station(_normalize_station(s), S, settings=settings)
                    return

        for s in stations:
            if s.get("name", "") == name:
                log.info(f"DAB play_by_name fallback name={name!r}")
                play_station(_normalize_station(s), S, settings=settings)
                return

        log.warn(f"DAB play_by_name: Station nicht gefunden name={name!r} sid={service_id!r}")

    except Exception as e:
        log.error(f"DAB play_by_name: {e}")


def play_next(S, stations):
    if not stations:
        return
    current = S.get("radio_name", "") or S.get("radio_station", "")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name", "") == current or current.endswith(s.get("name", "")):
            idx = (i + 1) % len(stations)
            break
    play_station(_normalize_station(stations[idx]), S)


def play_prev(S, stations):
    if not stations:
        return
    current = S.get("radio_name", "") or S.get("radio_station", "")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name", "") == current or current.endswith(s.get("name", "")):
            idx = (i - 1) % len(stations)
            break
    play_station(_normalize_station(stations[idx]), S)
