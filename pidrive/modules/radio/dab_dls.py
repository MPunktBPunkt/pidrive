#!/usr/bin/env python3
"""dab_dls.py — DLS-Poller (Dynamic Label Segment)  v0.10.55"""

from modules.radio.dab_helpers import (
    _dls_thread, _dls_stop_event, ERR_FILE, _err_file_for_session,
    _reset_runtime_dls_fields, _parse_dls_line,
    _dab_session_id, _dab_session_lock, _get_session,
    _write_play_debug,
    _append_play_debug_line, _parse_welle_status_line,
)
import threading, time, os
import log

def _stop_dls_thread():
    global _dls_thread
    _dls_stop_event.set()
    if _dls_thread and _dls_thread.is_alive():
        try:
            _dls_thread.join(timeout=2.0)
        except Exception:
            pass
    _dls_thread = None
    _dls_stop_event.clear()


def _dls_poller(session_id: str, station_name: str, S: dict):
    """
    Liest DLS robust aus ERR_FILE.
    Beendet sich, wenn:
    - Session wechselt
    - Stop-Event gesetzt wird
    - DAB nicht mehr die aktuelle Quelle ist
    """
    last_pos = 0
    last_dls = ""
    dls_lines_seen = 0      # Zähler für empfangene DLS-Zeilen
    dls_stop_reason = "running"
    _write_play_debug({
        "dls_thread_started": True,
        "dls_session_id": session_id,
        "dls_lines_seen": 0,
        "dls_stop_reason": "running",
        "dls_station": station_name,
    })

    # Immer ab Position 0 starten:
    # ERR_FILE wird bei jedem Session-Start neu erstellt (_truncate_file).
    # DLS erscheint oft während Lock-Wait → muss von Anfang gelesen werden.
    last_pos = 0

    log.warn(f"DAB DLS poller: start session={session_id[:12]} station={station_name!r} last_pos={last_pos}")

    while not _dls_stop_event.is_set():
        if _get_session() != session_id:
            log.info(f"DAB DLS poller: stop (session changed) old={session_id} new={_get_session()}")
            dls_stop_reason = "session_changed"
            break

        # Nur session-basiert stoppen — radio_playing flackert bei instabilem Empfang
        # und würde DLS-Übernahme trotz aktiver welle-cli-Sitzung unterbrechen
        if S.get("radio_type") not in ("DAB", "") and S.get("radio_type") is not None:
            # Andere Quelle aktiv (FM/Web/Spotify) → stoppen
            log.info(f"DAB DLS poller: stop (andere Quelle aktiv: {S.get('radio_type')!r})")
            dls_stop_reason = "other_source_active"
            break

        try:
            if not os.path.exists(ERR_FILE):
                time.sleep(1.0)
                continue

            with open(ERR_FILE, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(last_pos)
                new_data = f.read()
                last_pos = f.tell()

            if new_data:
                for line in new_data.splitlines():
                    s = line.strip()
                    if not s:
                        continue

                    parsed_status = _parse_welle_status_line(s)
                    if parsed_status:
                        _append_play_debug_line(parsed_status[0], parsed_status[1])

                    parsed_dls = _parse_dls_line(s)
                    if parsed_dls:
                        raw = parsed_dls["raw"]
                        if raw != last_dls:
                            S["dls_text"] = raw
                            dls_lines_seen += 1
                            S["dls"] = raw
                            S["dls_raw"] = raw
                            S["radio_text"] = raw
                            S["artist"] = parsed_dls["artist"]
                            S["track"] = parsed_dls["track"]
                            S["dls_ts"] = int(time.time())
                            S["dab_dls_state"] = "ok"
                            log.warn(f"DLS gefunden: {raw[:60]!r} → S[dls]={S.get('dls','-')!r}")
                            # Playlist-Eintrag schreiben (wie Webradio)
                            try:
                                import sys as _sys, os as _os
                                _base = _os.path.dirname(_os.path.dirname(
                                    _os.path.dirname(_os.path.abspath(__file__))))
                                if _base not in _sys.path: _sys.path.insert(0, _base)
                                from mpv_meta import _write_play_history as _wph
                                _wph(station_name, parsed_dls["artist"],
                                     parsed_dls["track"], raw, source="dab")
                            except Exception as _pe:
                                log.warn(f"DLS play_history Fehler: {_pe}")

                            _write_play_debug({
                                "last_dls_raw": raw,
                                "last_dls_artist": S["artist"],
                                "last_dls_track": S["track"],
                                "last_dls_ts": time.time(),
                                "dls_last_pos": last_pos,
                            })

                            log.info(
                                f"DAB DLS: session={session_id} "
                                f"raw={raw!r} artist={S['artist']!r} track={S['track']!r}"
                            )
                            last_dls = raw

        except Exception as e:
            _write_play_debug({
                "dls_error": str(e),
                "dls_error_ts": time.time(),
            })
            log.warn(f"DAB DLS poller: {e}")

        time.sleep(1.5)

    _write_play_debug({
        "dls_thread_stopped": True,
        "dls_thread_stop_ts": time.time(),
    })
    _write_play_debug({
        "dls_thread_stopped": True,
        "dls_lines_seen": dls_lines_seen,
        "dls_stop_reason": dls_stop_reason,
    })
    log.info(f"DAB DLS poller: end session={session_id} lines_seen={dls_lines_seen} reason={dls_stop_reason}")


def _start_dls_thread(session_id: str, station_name: str, S: dict):
    global _dls_thread
    _stop_dls_thread()
    _dls_thread = threading.Thread(
        target=_dls_poller,
        args=(session_id, station_name, S),
        daemon=True,
        name="dab_dls"
    )
    _dls_thread.start()



