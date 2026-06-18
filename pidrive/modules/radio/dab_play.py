import re
#!/usr/bin/env python3
"""dab_play.py — DAB+ Wiedergabe via welle-cli  v0.10.55"""

from modules.radio.dab_helpers import (
    _write_json_atomic, _read_json, _run, _truncate_file, _normalize_station,
    _new_session_id, _set_session, _get_session, _clear_session,
    _write_play_debug, _reset_runtime_dls_fields, _set_dab_status_fields,
    _parse_welle_status_line, _append_play_debug_line, _get_dab_gain,
    _err_file_for_session, _is_welle_noise_line, _dab_play_lock,
    _read_welle_log_tail, _welle_line_flags,
    ERR_FILE, STDOUT_FILE, PLAY_DEBUG_FILE, C_DAB,
    _player_proc, _scan_running,
    _rtlsdr, _src_state, _audio,
)
from modules.radio.dab_dls import _stop_dls_thread, _start_dls_thread
from modules.radio.dab_scan import load_stations, is_scan_running
try:
    from modules.platform import CAPS as _CAPS
except ImportError:
    _CAPS = {}

import os, re, json, time, shlex, threading, subprocess
import log, ipc

# Fatale Fehler — RTL-SDR nicht verfügbar, sofort abbrechen
_DAB_FATAL_PATTERNS = [
    "no valid device found",
    "opening rtl-sdr failed",
    "usb_open error",
    "rtlsdr_open() failed",
    "error: no supported",
    "could not load soapysdr",
    "device is busy",
]



# ── Recovery Monitor ─────────────────────────────────────────────────────────
import threading as _threading


def _feed_welle_programme(proc, name: str, reason: str = "") -> bool:
    """Sendet Sendernamen an welle-cli stdin (non-TTY braucht das trotz -p)."""
    try:
        if proc and proc.stdin and proc.poll() is None:
            proc.stdin.write((name + "\n").encode("utf-8"))
            proc.stdin.flush()
            log.info(f"DAB: welle stdin → {name!r} ({reason or 'feed'})")
            return True
    except Exception as e:
        log.warn(f"DAB welle stdin feed: {e}")
    return False


def _start_welle_stdin_feeder(proc, name: str, session_id: str):
    """Hintergrund: Sendernamen senden wenn welle-cli danach fragt."""
    def _run():
        fed = False
        err_pos = out_pos = 0
        start = time.time()
        while _get_session() == session_id and proc and proc.poll() is None:
            for path in (ERR_FILE, STDOUT_FILE):
                pos = err_pos if path == ERR_FILE else out_pos
                chunk, new_pos = _read_welle_log_tail(path, pos)
                if path == ERR_FILE:
                    err_pos = new_pos
                else:
                    out_pos = new_pos
                for ln in chunk:
                    fl = _welle_line_flags(ln)
                    if fl["programme_prompt"] or fl.get("trying_tune"):
                        if _feed_welle_programme(proc, name, "prompt"):
                            fed = True
                            return
            if not fed and time.time() - start > 20:
                if _feed_welle_programme(proc, name, "timeout20s"):
                    return
            time.sleep(0.5)

    _threading.Thread(
        target=_run, daemon=True, name=f"dab_stdin_{session_id[:8]}"
    ).start()

_recovery_thread = None
_recovery_stop   = threading.Event() if False else None  # wird unten initialisiert

def _start_recovery_monitor(session_id, station_name, S, settings):
    """Hintergrund-Thread: Sync/PCM/DLS überwachen solange welle-cli läuft."""
    global _recovery_thread, _recovery_stop
    if _recovery_stop:
        _recovery_stop.set()
    _recovery_stop = _threading.Event()

    def _monitor():
        import time as _t, os as _os
        err_file = _err_file_for_session(session_id)
        err_pos = 0
        out_pos = 0
        log.info(f"DAB Runtime-Monitor: start session={session_id}")
        _lock_found = bool(S.get("dab_sync_seen"))
        _pcm_found = bool(S.get("dab_pcm_seen"))

        _mon_start = _t.time()
        while not _recovery_stop.is_set():
            _elapsed = _t.time() - _mon_start
            _timeout = 1800 if _lock_found else 300
            if _elapsed > _timeout:
                log.warn(
                    f"DAB Runtime-Monitor: {_timeout // 60}min Timeout "
                    f"(sync={_lock_found} pcm={_pcm_found}) — gebe RTL-SDR frei"
                )
                _sp2 = __import__("subprocess")
                _sp2.run("pkill -f welle-cli 2>/dev/null",
                         shell=True, timeout=3, capture_output=True)
                S["dab_playback_state"] = "idle"
                S["dab_attempting"] = False
                S["radio_playing"] = False
                break
            if _get_session() != session_id:
                log.info("DAB Runtime-Monitor: session gewechselt — stop")
                break
            if S.get("radio_type") not in ("DAB", "", None):
                log.info("DAB Runtime-Monitor: andere Quelle aktiv — stop")
                break

            try:
                new_lines = []
                for path, pos_name in ((err_file, "err"), (STDOUT_FILE, "out")):
                    chunk, new_pos = _read_welle_log_tail(
                        path, err_pos if pos_name == "err" else out_pos
                    )
                    if pos_name == "err":
                        err_pos = new_pos
                    else:
                        out_pos = new_pos
                    new_lines.extend(chunk)

                for ln in new_lines:
                    s = ln.strip()
                    if not s:
                        continue
                    low = s.lower()
                    flags = _welle_line_flags(s)

                    if flags["sync"]:
                        _lock_found = True
                        S["dab_sync_seen"] = True
                        S["radio_playing"] = True
                        S["dab_attempting"] = True
                        S.pop("source_error", None)
                        if not S.get("dab_pcm_seen"):
                            S["dab_playback_state"] = "partial_sync"
                        log.info(f"DAB Runtime: sync — {s[:60]}")

                    if flags["superframe"]:
                        _lock_found = True
                        S["dab_sync_seen"] = True
                        S["dab_superframe_seen"] = True
                        S["dab_sync_ok"] = True
                        S["radio_playing"] = True
                        if not S.get("dab_pcm_seen"):
                            S["dab_playback_state"] = "locked"
                        try:
                            from modules import source_state as _sst
                            _sst.commit_source("dab")
                        except Exception:
                            pass

                    if flags["pcm"]:
                        if not _pcm_found:
                            _pcm_found = True
                            S["dab_pcm_seen"] = True
                            S["dab_audio_ready"] = True
                            S["dab_playback_state"] = "locked"
                            S["dab_sync_ok"] = True
                            S["radio_playing"] = True
                            log.info(f"DAB Runtime: PCM aktiv — {s[:70]}")
                            try:
                                from modules import audio as _aud
                                _aud.unsuspend_sink()
                            except Exception as _ue:
                                log.warn(f"DAB Runtime: unsuspend: {_ue}")

                    if "permission denied" in low and "pcm" in low:
                        S["dab_last_error"] = s[:180]
                        S["dab_playback_state"] = "pcm_error"
                        log.error(f"DAB Runtime: PCM blockiert — {s[:100]}")

                    if "lost coarse sync" in low and _lock_found and not _pcm_found:
                        S["dab_playback_state"] = "partial_sync"
                        S["dab_sync_ok"] = False

            except Exception as _e:
                log.warn(f"DAB Runtime-Monitor: {_e}")

            _t.sleep(1.0)

        log.info(
            f"DAB Runtime-Monitor: end session={session_id} "
            f"lock={_lock_found} pcm={_pcm_found}"
        )

    _recovery_thread = _threading.Thread(
        target=_monitor, daemon=True, name=f"dab_runtime_{session_id[:8]}"
    )
    _recovery_thread.start()


def play_station(station, S, settings=None):
    global _player_proc

    with _dab_play_lock:
        return _play_station_locked(station, S, settings)


def _play_station_locked(station, S, settings=None):
    global _player_proc

    # RTL-SDR verfügbar? Wenn nicht → sofort abbrechen
    from modules.platform import CAPS
    if not CAPS.get("rtlsdr"):
        log.warn("DAB play_station: RTL-SDR nicht verfügbar — abgebrochen")
        S["dab_playback_state"] = "idle"
        return {"state": "no_rtlsdr", "error": "RTL-SDR nicht verfügbar"}

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
            S["radio_type"]   = "DAB+"
            S["source_error"]  = "RTL-SDR belegt"
            log.warn(f"DAB: RTL-SDR belegt vor play {name} [{ch}]")
            return

    session_id = _new_session_id()
    _set_session(session_id)
    _stop_dls_thread()
    # Alle laufenden welle-cli zuerst beenden (Orphan-Prevention)
    try:
        import subprocess as _sp_pre
        _sp_pre.run("pkill -f welle-cli 2>/dev/null",
                    shell=True, timeout=3, capture_output=True)
        time.sleep(1.0)
        if _rtlsdr:
            try:
                _rtlsdr.wait_until_free(timeout=3.0)
            except Exception:
                pass
    except Exception:
        pass
    _sess_err_file = _err_file_for_session(session_id)
    _truncate_file(_sess_err_file)
    _truncate_file(STDOUT_FILE)  # DLS-stdout sauber starten
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
    S["dab_attempting"] = True   # welle-cli wird gestartet, Lock noch ausstehend
    S["dab_last_error"] = ""

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
            log.info("DAB: Audio-Server inaktiv — kein Abbruch (ALSA-direkt)")

        # Prio C: shell=True → Popen(list)
        # _name_q (shlex.quote) war nur wegen shell=True nötig — jetzt direkt
        # stdbuf -oL: stdout line-buffered erzwingen
        # Ohne stdbuf: bei Datei-Redirect full-buffered (4KB) → DLS kommt nie an
        # Mit stdbuf: jede Zeile wird sofort in STDOUT_FILE geschrieben
        _stdbuf = ["stdbuf", "-oL", "-eL"]
        _welle_cmd = _stdbuf + [
            "welle-cli", "-F", "rtl_sdr", "-T", "-c", ch, "-g", _gain, "-p", name
        ]
        _welle_stderr = open(_sess_err_file, "w")  # stderr
        try:
            _welle_stdout = open(STDOUT_FILE, "w")  # stdout: DLS, service list
        except Exception as _oe:
            log.warn(f"DAB: STDOUT_FILE open fehlgeschlagen: {_oe} — nutze DEVNULL")
            import subprocess as _sp_null
            _welle_stdout = open(os.devnull, "w")

        # v0.11.102: Direktes ALSA wie manuelles `sudo welle-cli` (ohne PA-Plugin).
        # pidrive_core.service setzt PULSE_SERVER global — fuer welle-cli entfernen,
        # sonst blockiert das PipeWire-ALSA-Plugin den Decode/PCM-Pfad.
        _welle_env = dict(os.environ)
        _welle_env.pop("PULSE_SERVER", None)
        _welle_env.pop("PIPEWIRE_RUNTIME_DIR", None)
        _welle_env.pop("PULSE_SINK", None)

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

        # v0.10.55: Audio-Routing-Debug beim Start
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
            "welle_direct_alsa": True,
            "pulse_server_in_env": "PULSE_SERVER" in _welle_env,
            "pulse_sink_in_env": "PULSE_SINK" in _welle_env,
            "pa_default_sink_before_start": _pa_default,
            "ppm": _ppm_val,
            "gain": _gain,
            "sess_err_file": _sess_err_file,
            "stdout_file": STDOUT_FILE,
        })

        log.info(
            f"DAB play: START name={name!r} channel={ch} sid={sid!r} gain={_gain} "
            f"session={session_id} | ALSA=direct PULSE_SERVER={'✗' if 'PULSE_SERVER' not in _welle_env else '✓'} "
            f"PA_Default={_pa_default or '(nicht gesetzt)'}"
        )

        try:
            from modules import audio as _audio_wake
            _audio_wake.unsuspend_sink(_adec.get("sink") or _audio_wake.get_alsa_sink())
        except Exception as _ue:
            log.warn(f"DAB: unsuspend sink: {_ue}")

        _pop_common = dict(
            shell=False,
            stdout=_welle_stdout,
            stderr=_welle_stderr,
            env=_welle_env,
            stdin=subprocess.PIPE,
        )

        if _rtlsdr:
            try:
                _player_proc = _rtlsdr.start_process(
                    _welle_cmd,
                    owner="dab_play",
                    **_pop_common,
                )
                _welle_stderr.close()
                _welle_stdout.close()
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
                **_pop_common,
            )
            _welle_stderr.close()
            _welle_stdout.close()

        _feed_welle_programme(_player_proc, name, "startup")
        _start_welle_stdin_feeder(_player_proc, name, session_id)

        _write_play_debug({
            "welle_pid": getattr(_player_proc, "pid", None),
            "welle_started_ts": time.time(),
        })

        # DLS-Thread sofort starten — DLS kommt oft während des Lock-Waits!
        # Nicht erst nach Lock-Wait: dann ist die DLS-Zeile schon im File
        log.warn(f"DAB DLS-Thread starten: session={session_id[:12]} err_file={_sess_err_file}")
        _start_dls_thread(session_id, name, S)

        lock_wait_max = int(settings.get("dab_wait_lock", 90)) if settings else 90
        sync_ok = False
        pcm_seen = False
        sync_seen = False
        superframe_seen = False
        last_err = ""
        _last_err_ts = 0.0
        _err_tail_pos = 0
        _out_tail_pos = 0

        for _ in range(lock_wait_max):
            time.sleep(1.0)
            if _get_session() != session_id:
                log.warn(f"DAB play: session superseded during lock wait {session_id}")
                return False

            try:
                new_lines = []
                for path, pos_attr in ((ERR_FILE, "_err_tail_pos"), (STDOUT_FILE, "_out_tail_pos")):
                    pos = _err_tail_pos if pos_attr == "_err_tail_pos" else _out_tail_pos
                    chunk, new_pos = _read_welle_log_tail(path, pos)
                    if pos_attr == "_err_tail_pos":
                        _err_tail_pos = new_pos
                    else:
                        _out_tail_pos = new_pos
                    new_lines.extend(chunk)

                for ln in new_lines:
                    parsed = _parse_welle_status_line(ln)
                    if parsed:
                        _append_play_debug_line(parsed[0], parsed[1])

                    flags = _welle_line_flags(ln)
                    low = ln.lower()
                    if flags["sync"] and not sync_seen:
                        sync_seen = True
                        log.info(f"DAB lock: ✓ found sync — {ln[:80]}")
                        S["dab_playback_state"] = "partial_sync"
                        S["dab_attempting"]   = True
                    if flags["superframe"] and not superframe_seen:
                        superframe_seen = True
                        log.info(f"DAB lock: ✓ superframe sync — {ln[:80]}")
                        S["dab_playback_state"] = "locked"
                        S["dab_attempting"] = False
                    if flags["pcm"] and not pcm_seen:
                        pcm_seen = True
                        log.info(f"DAB lock: ✓ PCM bereit — {ln[:80]}")
                        S["dab_playback_state"] = "locked"
                        S["dab_attempting"] = False
                        try:
                            from modules import audio as _aud_pcm
                            _aud_pcm.unsuspend_sink()
                        except Exception:
                            pass
                    if flags["service_list"]:
                        log.info("DAB lock: service list empfangen")
                    if (not _is_welle_noise_line(ln)
                            and any(x in low for x in ["failed", "cannot open",
                                                       "permission denied", "xrun", "error"])):
                        if (__import__("time").time() - _last_err_ts) > 10.0:
                            last_err = ln[:180]
                            _last_err_ts = __import__("time").time()
                            log.warn(f"DAB welle: {ln[:100]}")

                    if any(p in low for p in _DAB_FATAL_PATTERNS):
                        log.error(f"DAB FATAL: RTL-SDR nicht verfuegbar ({ln[:80]}) — stoppe")
                        try:
                            import subprocess as _sp
                            _sp.run(f"pkill -f 'welle-cli.*{ch}' 2>/dev/null", shell=True, timeout=2)
                        except Exception:
                            pass
                        _set_dab_status_fields(S, dab_state="device_error",
                                               dab_last_error=ln[:100], radio_playing=False)
                        return False

                if sync_seen and superframe_seen:
                    sync_ok = True

                if sync_ok or pcm_seen:
                    break

            except Exception as e:
                last_err = str(e)

        dab_state = ("locked" if sync_ok
                     else "pcm_only" if pcm_seen
                     else "partial_sync" if sync_seen  # Signal da, kein stabiler Superframe
                     else "no_lock")
        S["dab_sync_seen"]    = sync_seen
        S["dab_partial_sync"] = sync_seen and not sync_ok
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
        S["dab_playback_state"] = dab_state

        _write_play_debug({
            "state": dab_state,
            "sync_ok": sync_ok,
            "pcm_seen": pcm_seen,
            "sync_seen": sync_seen,
            "superframe_seen": superframe_seen,
            "last_error_line": last_err,
            "lock_wait_seconds": lock_wait_max,
        })

        # radio_playing=True bei: sync_ok, pcm_seen, oder sync_seen (instabiler aber echter Empfang)
        # Manueller Test beweist: sync_seen allein reicht für PCM+DLS trotz Lost-coarse-sync-Phasen
        if sync_ok or pcm_seen:
            S["radio_playing"] = True
            _radio_started = True  # voller Lock oder PCM bestätigt
            if not pcm_seen:
                log.info("DAB: sync_ok aber kein PCM — Audio möglicherweise instabil")
        elif sync_seen:
            # Partieller Sync: Signal erkannt, aber noch kein stabiler Superframe
            # welle-cli kann trotzdem Audio/DLS liefern (instabil aber funktional)
            S["radio_playing"] = True
            _radio_started = True  # partieller Lock — besser als false-negative
            log.info("DAB: partieller Sync (sync_seen, kein Superframe) — playing=True für instabilen Betrieb")
        else:
            # no_lock: DAB läuft noch (welle-cli), aber Status ehrlich halten
            S["radio_playing"] = False
            S["source_error"]  = "Kein Lock"
            S["dab_playback_state"] = "no_lock"
            _radio_started = False
            log.warn(f"DAB: no_lock — welle-cli läuft weiter, Recovery-Monitor aktiv (session={session_id})")

        S["dab_attempting"]   = True
        S["dab_last_error"]   = last_err or "no_lock"
        S["radio_station"] = "DAB: " + name
        S["radio_name"] = name
        S["radio_type"] = "DAB"
        S["control_context"] = "radio_dab"

        # Runtime-Monitor: Sync/PCM/DLS auch nach partiellem Lock weiter verfolgen
        _start_recovery_monitor(session_id, name, S, settings)

        log.action("DAB", f"Wiedergabe: {name} ({ch}, sid={sid or '-'}) session={session_id} started={_radio_started}")
        return _radio_started

    except Exception as e:
        S["radio_playing"] = False
        S["radio_station"] = "DAB Fehler"
        _set_dab_status_fields(S, dab_state="exception", dab_last_error=str(e))
        _write_play_debug({
            "state": "exception",
            "error": str(e),
        })
        log.error(f"DAB play Fehler: {e}")
        return False


def stop(S):
    global _player_proc, _scan_running

    with _dab_play_lock:
        _stop_locked(S)


def _stop_locked(S):
    global _player_proc, _scan_running

    log.info("DAB stop: requested")
    _scan_running = False

    _stop_dls_thread()
    _clear_session()

    if _player_proc:
        try:
            if getattr(_player_proc, "stdin", None):
                try:
                    _player_proc.stdin.close()
                except Exception:
                    pass
            _player_proc.terminate()
            _player_proc.wait(timeout=2)
        except Exception:
            pass

    if _rtlsdr:
        try:
            _rtlsdr.stop_process()
        except Exception:
            pass
    # Orphan-Killer: alle welle-cli Prozesse beenden
    try:
        import subprocess as _sp_kill
        _sp_kill.run("pkill -f welle-cli 2>/dev/null",
                     shell=True, timeout=3, capture_output=True)
    except Exception:
        pass

    import subprocess as _sp, time as _tm
    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, timeout=3, capture_output=True)
    _tm.sleep(0.3)  # kurz warten damit pkill wirkt

    # RTL-SDR Lock-File clearen — welle-cli ist tot, Lock kann weg
    try:
        from modules.radio.rtlsdr import clear_stale_lock as _csl_dab
        _csl_dab()
    except Exception: pass

    _player_proc = None

    if S.get("radio_type") == "DAB":
        S["radio_playing"] = False
        S["radio_station"] = ""
        # v0.10.55: Clear DLS/artist/track fields on stop to avoid stale display
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


def play_by_number(nr, S, settings=None):
    """Spielt Station Nr. nr (1-basiert) aus dab_stations.json."""
    path = os.path.join(os.path.dirname(__file__), "../../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        stations = data.get("stations", data) if isinstance(data, dict) else data
        if 1 <= nr <= len(stations):
            s = stations[nr - 1]
            log.info(f"DAB play_by_number: #{nr} → {s.get('name','?')!r}")
            return play_station(_normalize_station(s), S, settings=settings)
        log.warn(f"DAB play_by_number: Nr {nr} außerhalb 1-{len(stations)}")
        return False
    except Exception as e:
        log.error(f"DAB play_by_number: Fehler {e}")
        return False


def play_by_name(name, S, settings=None, service_id=""):
    # "Sender #N" → per Nummer nachschlagen (Boot-Resume-Kompatibilität)
    _nr_match = re.match(r"Sender\s+#?(\d+)$", str(name or "").strip(), re.I)
    if _nr_match:
        _nr = int(_nr_match.group(1))
        log.info(f"DAB play_by_name: 'Sender #{_nr}' → lookup per Nummer")
        return play_by_number(_nr, S, settings)
    path = os.path.join(os.path.dirname(__file__), "../../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        stations = data.get("stations", data) if isinstance(data, dict) else data
        service_id = str(service_id or "").strip().lower()

        if service_id:
            for s in stations:
                sid = str(s.get("service_id", "") or "").strip().lower()
                if sid and sid == service_id:
                    log.info(f"DAB play_by_name service_id match name={name!r} sid={service_id}")
                    return play_station(_normalize_station(s), S, settings=settings)

        for s in stations:
            if s.get("name", "") == name:
                log.info(f"DAB play_by_name fallback name={name!r}")
                return play_station(_normalize_station(s), S, settings=settings)

        log.warn(f"DAB play_by_name: Station nicht gefunden name={name!r} sid={service_id!r}")
        return False

    except Exception as e:
        log.error(f"DAB play_by_name: {e}")
        return False


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
