"""
modules/dab.py — DAB+ Wiedergabe und Scan via welle-cli (stark verbessert)
PiDrive v0.9.31+

Ziele:
- robustere Wiedergabe
- klare Lock-/Status-/DLS-Zustände
- DLS sauber in Runtime-State + Debug-JSON spiegeln
- Session-sicherer Poller
- bessere Diagnose für "Lock OK, aber kein hörbarer Ton"
"""

import os
import re
import json
import time
import shlex
import threading
import subprocess
import urllib.request as _ur

import log
import ipc

try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None

try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None


# ─────────────────────────────────────────────────────────────────────────────
# Dateien / Globals
# ─────────────────────────────────────────────────────────────────────────────

ERR_FILE = "/tmp/pidrive_dab_welle.err"
PLAY_DEBUG_FILE = "/tmp/pidrive_dab_play_debug.json"
SCAN_DEBUG_FILE = "/tmp/pidrive_dab_scan_debug.json"

_player_proc = None
_scan_running = False
_last_scan_diag = {}

_dls_thread = None
_dls_stop_event = threading.Event()
_dab_session_id = ""
_dab_session_lock = threading.RLock()

C_DAB = (0, 200, 180)


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _write_json_atomic(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log.warn(f"DAB write json {path}: {e}")


def _read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _truncate_file(path):
    try:
        with open(path, "w", encoding="utf-8"):
            pass
    except Exception:
        pass


def _run(cmd, capture=False, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if capture else (r.returncode == 0)
    except Exception:
        return "" if capture else False


def _normalize_station(st):
    out = dict(st or {})
    out.setdefault("service_id", "")
    out.setdefault("ensemble", "")
    out.setdefault("channel", "")
    out.setdefault("url_mp3", "")
    out.setdefault("favorite", False)
    out.setdefault("enabled", True)
    return out


def _new_session_id():
    return f"dab_{int(time.time() * 1000)}"


def _set_session(session_id: str):
    global _dab_session_id
    with _dab_session_lock:
        _dab_session_id = session_id


def _get_session():
    with _dab_session_lock:
        return _dab_session_id


def _clear_session():
    global _dab_session_id
    with _dab_session_lock:
        _dab_session_id = ""


def _write_play_debug(data: dict):
    old = _read_json(PLAY_DEBUG_FILE, {})
    merged = dict(old)
    merged.update(data)
    merged["ts"] = time.time()
    _write_json_atomic(PLAY_DEBUG_FILE, merged)


def _reset_runtime_dls_fields(S):
    S["artist"] = ""
    S["track"] = ""
    S["album"] = ""
    S["dls"] = ""
    S["dls_raw"] = ""
    S["radio_text"] = ""
    S["dls_ts"] = 0
    S["dab_dls_state"] = "empty"


def _set_dab_status_fields(S, **kwargs):
    for k, v in kwargs.items():
        S[k] = v


def _parse_dls_line(line: str):
    """
    Robuster Parser für DLS-Zeilen.
    Erlaubt:
    - 'DLS: Foo - Bar'
    - '[INFO] DLS: Foo - Bar'
    - '   DLS: Foo - Bar'
    """
    if not line:
        return None

    m = re.search(r"\bDLS:\s*(.+)$", line, re.IGNORECASE)
    if not m:
        return None

    raw = m.group(1).strip()
    if not raw:
        return None

    artist = ""
    track = raw

    if " - " in raw:
        parts = raw.split(" - ", 1)
        artist = parts[0].strip()
        track = parts[1].strip()

    return {
        "raw": raw,
        "artist": artist,
        "track": track,
    }


def _parse_welle_status_line(line: str):
    low = (line or "").strip().lower()
    if not low:
        return None

    if "found sync" in low:
        return ("sync_found", line.strip())
    if "superframe sync succeeded" in low:
        return ("superframe_ok", line.strip())
    if "pcm name:" in low:
        return ("pcm_ready", line.strip())
    if "dls:" in low:
        return ("dls_seen", line.strip())

    if any(x in low for x in [
        "failed",
        "lost",
        "cannot open",
        "permission denied",
        "xrun",
        "alsa",
        "audio"
    ]):
        return ("warn_or_error", line.strip())

    return None


def _append_play_debug_line(kind: str, line: str):
    dbg = _read_json(PLAY_DEBUG_FILE, {})
    lines = dbg.get("recent_lines", [])
    lines.append({
        "ts": round(time.time(), 3),
        "kind": kind,
        "line": line[:220]
    })
    dbg["recent_lines"] = lines[-40:]
    _write_json_atomic(PLAY_DEBUG_FILE, dbg)


# ─────────────────────────────────────────────────────────────────────────────
# Gain Mapping
# ─────────────────────────────────────────────────────────────────────────────

_RTL_GAIN_TABLE = [
    0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7,
    16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8,
    36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6
]


def _get_dab_gain(settings=None):
    try:
        if settings is None:
            from settings import load_settings as _ls
            settings = _ls()
        g = settings.get("dab_gain", -1)
        if isinstance(g, str):
            g = g.strip()
            if not g:
                return "-1"
        g = float(g)
        if g < 0:
            return "-1"
        idx = min(range(len(_RTL_GAIN_TABLE)), key=lambda i: abs(_RTL_GAIN_TABLE[i] - g))
        actual_db = _RTL_GAIN_TABLE[idx]
        log.info(f"DAB gain: {g:.0f} dB → Index {idx} ({actual_db:.1f} dB)")
        return str(idx)
    except Exception:
        return "-1"


# ─────────────────────────────────────────────────────────────────────────────
# Scan-Diagnose
# ─────────────────────────────────────────────────────────────────────────────

def get_last_scan_diag():
    return dict(_last_scan_diag)


def _write_scan_diag_file():
    _write_json_atomic(SCAN_DEBUG_FILE, _last_scan_diag)


def load_last_scan_diag_file():
    return _read_json(SCAN_DEBUG_FILE, {})


# ─────────────────────────────────────────────────────────────────────────────
# Wiedergabe-Status / DLS Poller
# ─────────────────────────────────────────────────────────────────────────────

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
    _write_play_debug({
        "dls_thread_started": True,
        "dls_session_id": session_id,
        "dls_station": station_name,
    })

    # Startoffset: wir lesen ab Dateiende nur neue Zeilen
    try:
        if os.path.exists(ERR_FILE):
            with open(ERR_FILE, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, os.SEEK_END)
                last_pos = f.tell()
    except Exception:
        last_pos = 0

    log.info(f"DAB DLS poller: start session={session_id} station={station_name!r}")

    while not _dls_stop_event.is_set():
        if _get_session() != session_id:
            log.info(f"DAB DLS poller: stop (session changed) old={session_id} new={_get_session()}")
            break

        if not (S.get("radio_playing") and S.get("radio_type") == "DAB" and S.get("radio_name") == station_name):
            log.info(f"DAB DLS poller: stop (radio state changed) station={station_name!r}")
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
                            S["dls"] = raw
                            S["dls_raw"] = raw
                            S["radio_text"] = raw
                            S["artist"] = parsed_dls["artist"]
                            S["track"] = parsed_dls["track"]
                            S["dls_ts"] = int(time.time())
                            S["dab_dls_state"] = "ok"

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
    log.info(f"DAB DLS poller: end session={session_id}")


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


# ─────────────────────────────────────────────────────────────────────────────
# Stations-IO
# ─────────────────────────────────────────────────────────────────────────────

def load_stations():
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data.get("stations", data) if isinstance(data, dict) else data
    except Exception:
        return []


def save_stations(stations):
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"DAB save Fehler: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Scan
# ─────────────────────────────────────────────────────────────────────────────

def scan_dab_channels(settings=None):
    import subprocess as _sp
    import time as _t

    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}

    SCAN_PORT = int(settings.get("dab_scan_port", 7981) or 7981)
    WAIT_LOCK = int(settings.get("dab_scan_wait_lock", 20) or 20)
    WAIT_HTTP = int(settings.get("dab_scan_http_timeout", 4) or 4)

    CHANNELS_REGIONAL = ["5C", "5D", "8D", "10A", "10D", "11D", "12D"]
    CHANNELS_FULL = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]

    requested_channels = settings.get("dab_scan_channels", []) or []
    if isinstance(requested_channels, str):
        requested_channels = [x.strip().upper() for x in requested_channels.split(",") if x.strip()]
    requested_channels = [str(x).strip().upper() for x in requested_channels if str(x).strip()]

    if requested_channels:
        region_list = [ch for ch in requested_channels if ch in CHANNELS_FULL]
        full_list = region_list[:]
        log.info(f"DAB Scan: gezielte Kanäle: {region_list} (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")
    else:
        region_list = CHANNELS_REGIONAL
        full_list = CHANNELS_FULL
        log.info(f"DAB Scan: Standard-Scan (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")

    gain_idx = _get_dab_gain(settings)
    found = []
    scanned = []

    def _lock_state_name(snr, ens_label, ens_id, services, fic_crc, last_fct0):
        if services > 0:
            return "services_found"
        if ens_label or (ens_id and ens_id != "0x0000"):
            return "ensemble_locked"
        if int(last_fct0 or 0) == 0:
            return "no_fct0_lock" if snr >= 2.0 else "no_signal"
        if fic_crc >= 0:
            return "fic_only"
        return "unknown"

    global _last_scan_diag
    _last_scan_diag = {
        "channels": {},
        "ts": int(time.time()),
        "wait_lock": WAIT_LOCK,
        "port": SCAN_PORT
    }
    _write_scan_diag_file()

    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
    _t.sleep(0.5)

    if _rtlsdr:
        usb = _rtlsdr.detect_usb()
        if not usb.get("present"):
            log.error("DAB Scan: RTL-SDR nicht erkannt")
            return []
        if _rtlsdr.is_busy():
            log.warn("DAB Scan: RTL-SDR belegt — warte 2s")
            _t.sleep(2)

    def _scan_channel(ch):
        _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
        _t.sleep(0.3)

        cmd = (f"welle-cli -c {ch} -g {gain_idx} -C 1 -w {SCAN_PORT} "
               f"2>/tmp/pidrive_dab_welle.err")
        proc = _sp.Popen(cmd, shell=True, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        _t.sleep(WAIT_LOCK)

        services = []
        snr = 0.0
        ens_label = ""
        ens_id = ""
        freq_corr = 0
        fic_crc = -1
        last_fct0 = 0
        rx_gain = ""

        try:
            url = f"http://127.0.0.1:{SCAN_PORT}/mux.json"
            resp = _ur.urlopen(url, timeout=WAIT_HTTP)
            data = json.loads(resp.read().decode("utf-8"))

            snr = float(data.get("demodulator", {}).get("snr", 0) or data.get("demodulator_snr", 0))
            ens_label = (data.get("ensemble", {}).get("label", {}).get("label", "") or "")
            ens_id = data.get("ensemble", {}).get("id", "")
            fic_crc = int(data.get("demodulator", {}).get("fic", {}).get("numcrcerrors", -1))
            last_fct0 = int(data.get("demodulator", {}).get("time_last_fct0_frame", 0) or 0)
            freq_corr = int(data.get("receiver", {}).get("hardware", {}).get("freqcorr", 0) or 0)
            rx_gain = str(data.get("receiver", {}).get("hardware", {}).get("gain", ""))

            raw_svcs = data.get("services", [])
            for svc in raw_svcs:
                _lbl = svc.get("label", "")
                if isinstance(_lbl, dict):
                    _lbl = _lbl.get("label", "") or ""
                name = str(_lbl or "").strip()
                sid = str(svc.get("sid", "") or "").strip()
                url_mp3 = str(svc.get("url_mp3", "") or "").strip()
                if name:
                    services.append({
                        "name": name,
                        "service_id": sid,
                        "url_mp3": url_mp3
                    })

        except Exception as e:
            log.info(f"DAB Scan: {ch}: mux.json nicht erreichbar ({e})")

        try:
            proc.terminate()
        except Exception:
            pass
        _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)

        lock_state = _lock_state_name(
            snr=snr, ens_label=ens_label, ens_id=ens_id,
            services=len(services), fic_crc=fic_crc, last_fct0=last_fct0
        )

        _last_scan_diag["channels"][ch] = {
            "ensemble": ens_label,
            "ensemble_id": ens_id,
            "services": len(services),
            "snr": snr,
            "freqcorr": freq_corr,
            "gain": rx_gain,
            "ficcrc": fic_crc,
            "lastfct0": last_fct0,
            "service_names": [s["name"] for s in services],
            "lock_state": lock_state,
        }
        _write_scan_diag_file()
        return services, ens_label, ens_id, snr

    ipc.write_progress("DAB+ Suchlauf", "Regionale Kanäle...", color="blue")
    for ch in region_list:
        ipc.write_progress("DAB+ Suchlauf", f"Kanal {ch}...", color="blue")
        svcs, ens_label, ens_id, snr = _scan_channel(ch)
        scanned.append(ch)
        for svc in svcs:
            entry = {
                "name": svc["name"],
                "channel": ch,
                "ensemble": ens_label,
                "service_id": str(svc["service_id"] or "").strip(),
                "url_mp3": "",
                "id": f"dab_{svc['service_id'] or svc['name']}",
                "favorite": False,
                "enabled": True,
            }
            if not any(
                (str(e.get("service_id","") or "").strip() == entry["service_id"] and entry["service_id"])
                or (e["name"] == svc["name"] and e["channel"] == ch)
                for e in found
            ):
                found.append(entry)

    if len(found) < 3 and not requested_channels:
        log.info("DAB Scan: Regionalscan < 3 Sender — Vollscan...")
        ipc.write_progress("DAB+ Suchlauf", "Vollscan...", color="blue")
        for ch in full_list:
            if ch in scanned:
                continue
            ipc.write_progress("DAB+ Suchlauf", f"Vollscan {ch}...", color="blue")
            svcs, ens_label, ens_id, snr = _scan_channel(ch)
            scanned.append(ch)
            for svc in svcs:
                entry = {
                    "name": svc["name"],
                    "channel": ch,
                    "ensemble": ens_label,
                    "service_id": str(svc["service_id"] or "").strip(),
                    "url_mp3": "",
                    "id": f"dab_{svc['service_id'] or svc['name']}",
                    "favorite": False,
                    "enabled": True,
                }
                if not any(
                    (str(e.get("service_id","") or "").strip() == entry["service_id"] and entry["service_id"])
                    or (e["name"] == svc["name"] and e["channel"] == ch)
                    for e in found
                ):
                    found.append(entry)

    _last_scan_diag["found"] = len(found)
    _write_scan_diag_file()
    log.info(f"DAB Scan: FERTIG — {len(found)} Sender")
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Wiedergabe
# ─────────────────────────────────────────────────────────────────────────────

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
    _truncate_file(ERR_FILE)
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
            " 2>" + ERR_FILE
        )

        _write_play_debug({
            "audio_decision": _adec,
            "welle_cmd": _welle_cmd,
            "ppm": _ppm_val,
            "gain": _gain,
        })

        log.info(f"DAB play: START name={name!r} channel={ch} sid={sid!r} gain={_gain} session={session_id}")

        if _rtlsdr:
            try:
                _player_proc = _rtlsdr.start_process(
                    _welle_cmd,
                    owner="dab_play",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
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
                stderr=subprocess.DEVNULL
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

            if not os.path.exists(ERR_FILE):
                continue

            try:
                with open(ERR_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [ln.strip() for ln in f.readlines()[-25:] if ln.strip()]

                for ln in lines[-8:]:
                    parsed = _parse_welle_status_line(ln)
                    if parsed:
                        _append_play_debug_line(parsed[0], parsed[1])

                    low = ln.lower()
                    if "found sync" in low:
                        sync_seen = True
                    if "superframe sync succeeded" in low:
                        superframe_seen = True
                    if "pcm name:" in low:
                        pcm_seen = True
                    if any(x in low for x in ["failed", "lost", "cannot open", "permission denied", "xrun"]):
                        last_err = ln[:180]

                if sync_seen and superframe_seen:
                    sync_ok = True

                if sync_ok or pcm_seen:
                    break

            except Exception as e:
                last_err = str(e)

        dab_state = "locked" if sync_ok else ("pcm_only" if pcm_seen else "no_lock")

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

        S["radio_playing"] = True
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

    _set_dab_status_fields(
        S,
        dab_state="stopped",
        dab_sync_ok=False,
        dab_audio_ready=False,
    )

    time.sleep(1.0)
    log.info("DAB stop: done")


def play_by_name(name, S, service_id=""):
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
                    play_station(_normalize_station(s), S)
                    return

        for s in stations:
            if s.get("name", "") == name:
                log.info(f"DAB play_by_name fallback name={name!r}")
                play_station(_normalize_station(s), S)
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