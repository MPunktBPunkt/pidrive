"""
mpv_meta.py — Now-Playing Metadaten via mpv JSON-IPC
PiDrive v0.8.0

Liest ICY/Stream-Metadaten aus einem laufenden mpv-Prozess via Unix-Socket.
Thread-sicher: läuft als Daemon-Thread, schreibt in S (State-Dict).

Unterstützte Metadaten:
  icy-title   → "Foo Fighters - Everlong" (typisch)
  icy-name    → Sendername vom Stream
  media-title → Fallback
"""

import json
import os
import socket
import threading
import time

MPV_SOCKET = "/tmp/pidrive_mpv.sock"

_listener_thread = None
_stop_event      = threading.Event()



import json as _json_hist

PLAY_HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "play_history.json"
)
_HISTORY_MAX = 2000

def _write_play_history(station, artist, track, raw, source="webradio"):
    """Gespielten Titel in play_history.json anhängen."""
    import time as _t3
    entry = {
        "ts":       int(_t3.time()),
        "ts_human": _t3.strftime("%Y-%m-%d %H:%M:%S", _t3.localtime()),
        "date":     _t3.strftime("%Y-%m-%d", _t3.localtime()),
        "source":   (source or "webradio").lower(),
        "station":  station or "",
        "artist":   artist or "",
        "track":    track or "",
        "raw":      raw or "",
    }
    try:
        try:
            with open(PLAY_HISTORY_FILE) as _fh: history = _json_hist.load(_fh)
            if not isinstance(history, list): history = []
        except Exception: history = []
        history.append(entry)
        if len(history) > _HISTORY_MAX: history = history[-_HISTORY_MAX:]
        with open(PLAY_HISTORY_FILE, "w") as _fh:
            _json_hist.dump(history, _fh, ensure_ascii=False, separators=(",",":"))
    except Exception: pass

def _parse_stream_title(raw: str) -> dict:
    """ICY-Titelstring in artist/track aufteilen.
    "Foo Fighters - Everlong" → {"artist": "Foo Fighters", "track": "Everlong"}
    "Everlong"                → {"artist": "", "track": "Everlong"}
    """
    raw = (raw or "").strip()
    if not raw:
        return {"artist": "", "track": ""}
    # Nur beim ersten " - " splitten (Bandnamen können "-" enthalten)
    if " - " in raw:
        parts = raw.split(" - ", 1)
        return {"artist": parts[0].strip(), "track": parts[1].strip()}
    return {"artist": "", "track": raw}


def _listener_loop(sock_path: str, station_name: str, S: dict, stop: threading.Event):
    """Verbindet auf mpv-Socket, beobachtet Metadaten, schreibt in S."""
    import log

    # Auf mpv IPC-Socket warten (bis 15s — Pi 3 kann langsam starten)
    for _i in range(150):
        if stop.is_set():
            return
        if os.path.exists(sock_path):
            break
        time.sleep(0.1)
    else:
        log.warn(f"[MPV_META] Socket nicht gefunden nach 15s: {sock_path} — Metadaten nicht verfügbar")
        S["metadata_unavailable"] = True
        return

    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3.0)
        # Socket vorhanden → Metadaten-Pfad aktiv
        S["metadata_unavailable"] = False
        s.connect(sock_path)
        s.settimeout(None)
    except OSError as e:
        log.warn("[MPV_META] Socket connect fehlgeschlagen: " + str(e))
        return

    log.info("[MPV_META] Verbunden — beobachte Metadaten für: " + station_name)

    # metadata + media-title beobachten
    for obs_id, prop in [(1, "metadata"), (2, "media-title")]:
        cmd = json.dumps({"command": ["observe_property", obs_id, prop]}) + "\n"
        try:
            s.sendall(cmd.encode("utf-8"))
        except OSError:
            break

    buf = b""
    while not stop.is_set():
        try:
            s.settimeout(1.0)
            chunk = s.recv(4096)
            if not chunk:
                break
        except socket.timeout:
            continue
        except OSError:
            break

        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line.decode("utf-8", "ignore"))
            except Exception:
                continue

            if evt.get("event") != "property-change":
                continue

            name = evt.get("name", "")
            data = evt.get("data")

            if name == "metadata" and isinstance(data, dict):
                icy = (data.get("icy-title") or
                       data.get("StreamTitle") or
                       data.get("title") or "")
                parsed = _parse_stream_title(icy)
                S["track"]  = parsed["track"]
                S["artist"] = parsed["artist"]
                S["album"]  = ""
                if icy:
                    log.info(f"[MPV_META] Stream-Titel: {icy!r} "
                             f"→ artist={parsed['artist']!r} track={parsed['track']!r}")
                    # Play-History bei Titelwechsel
                    if parsed["track"] and parsed["track"] != S.get("_last_hist_track",""):
                        S["_last_hist_track"] = parsed["track"]
                        try:
                            _write_play_history(
                                station=station_name, artist=parsed["artist"],
                                track=parsed["track"], raw=icy,
                                source=S.get("radio_type","webradio"),
                            )
                        except Exception as _he:
                            pass

            elif name == "media-title" and isinstance(data, str):
                # Fallback wenn metadata leer bleibt
                if not S.get("track") and data and data != station_name:
                    parsed = _parse_stream_title(data)
                    S["track"]  = parsed["track"]
                    S["artist"] = parsed["artist"]
                    log.info(f"[MPV_META] media-title Fallback: {data!r}")

    s.close()
    log.info("[MPV_META] Listener beendet")


def start(station_name: str, S: dict, sock_path: str = MPV_SOCKET):
    """Metadaten-Listener als Daemon-Thread starten."""
    global _listener_thread, _stop_event
    stop()  # alten Thread beenden

    # Socket bereinigen
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass

    _stop_event = threading.Event()
    _listener_thread = threading.Thread(
        target=_listener_loop,
        args=(sock_path, station_name, S, _stop_event),
        daemon=True,
        name="mpv-meta"
    )
    _listener_thread.start()


def stop():
    """Laufenden Listener-Thread beenden."""
    global _listener_thread, _stop_event
    if _listener_thread and _listener_thread.is_alive():
        _stop_event.set()
        _listener_thread.join(timeout=2)
    _listener_thread = None
