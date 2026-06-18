#!/usr/bin/env python3
"""dab_dls.py — DLS-Poller (Dynamic Label Segment)  v0.11.99"""

from modules.radio.dab_helpers import (
    _dls_thread, _dls_stop_event, ERR_FILE, STDOUT_FILE, _err_file_for_session,
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


def _read_new_lines(path: str, last_pos: int) -> tuple[str, int]:
    """Inkrementell neue Zeilen aus Log-Datei lesen (Tail bei Rotation)."""
    if not os.path.exists(path):
        return "", last_pos
    try:
        fsize = os.path.getsize(path)
        if last_pos > fsize:
            last_pos = max(0, fsize - 200)
        elif fsize - last_pos > 80_000:
            last_pos = fsize - 80_000
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(last_pos)
            new_data = f.read()
            return new_data, f.tell()
    except Exception:
        return "", last_pos


def _dls_poller(session_id: str, station_name: str, S: dict):
    """
    Liest DLS aus welle-cli stderr (ERR_FILE) und optional stdout.
    welle-cli schreibt DLS/TII/PCM-Status nach stderr — nicht stdout.
    """
    last_dls = ""
    dls_lines_seen = 0
    dls_stop_reason = "running"
    err_pos = 0
    out_pos = 0
    _write_play_debug({
        "dls_thread_started": True,
        "dls_session_id": session_id,
        "dls_lines_seen": 0,
        "dls_stop_reason": "running",
        "dls_station": station_name,
        "dls_sources": ["stderr", "stdout"],
    })

    log.warn(
        f"DAB DLS poller: start session={session_id[:12]} "
        f"station={station_name!r} err={ERR_FILE}"
    )

    while not _dls_stop_event.is_set():
        if _get_session() != session_id:
            log.info(f"DAB DLS poller: stop (session changed) old={session_id} new={_get_session()}")
            dls_stop_reason = "session_changed"
            break

        if S.get("radio_type") not in ("DAB", "") and S.get("radio_type") is not None:
            log.info(f"DAB DLS poller: stop (andere Quelle aktiv: {S.get('radio_type')!r})")
            dls_stop_reason = "other_source_active"
            break

        try:
            for path, pos_ref in ((ERR_FILE, "err"), (STDOUT_FILE, "out")):
                new_data, new_pos = _read_new_lines(
                    path, err_pos if pos_ref == "err" else out_pos
                )
                if pos_ref == "err":
                    err_pos = new_pos
                else:
                    out_pos = new_pos

                if not new_data:
                    continue

                for line in new_data.splitlines():
                    s = line.strip()
                    if not s:
                        continue

                    parsed_status = _parse_welle_status_line(s)
                    if parsed_status:
                        _append_play_debug_line(parsed_status[0], parsed_status[1])

                    parsed_dls = _parse_dls_line(s)
                    if not parsed_dls:
                        continue

                    raw = parsed_dls["raw"]
                    if raw == last_dls:
                        continue

                    S["dls_text"] = raw
                    dls_lines_seen += 1
                    S["dls"] = raw
                    S["dls_raw"] = raw
                    S["radio_text"] = raw
                    S["artist"] = parsed_dls["artist"]
                    S["track"] = parsed_dls["track"]
                    S["dls_ts"] = int(time.time())
                    S["dab_dls_state"] = "ok"
                    if not S.get("track"):
                        S["track"] = raw
                    log.warn(f"DLS gefunden ({path}): {raw[:60]!r}")

                    try:
                        import sys as _sys, os as _os
                        _base = _os.path.dirname(_os.path.dirname(
                            _os.path.dirname(_os.path.abspath(__file__))))
                        if _base not in _sys.path:
                            _sys.path.insert(0, _base)
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
                        "last_dls_source": path,
                        "dls_lines_seen": dls_lines_seen,
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

        time.sleep(1.0)

    _write_play_debug({
        "dls_thread_stopped": True,
        "dls_thread_stop_ts": time.time(),
        "dls_lines_seen": dls_lines_seen,
        "dls_stop_reason": dls_stop_reason,
    })
    log.info(
        f"DAB DLS poller: end session={session_id} lines_seen={dls_lines_seen} "
        f"reason={dls_stop_reason}"
    )


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
