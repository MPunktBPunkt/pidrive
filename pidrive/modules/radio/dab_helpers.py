#!/usr/bin/env python3
"""dab_helpers.py — DAB+ Hilfsfunktionen und Gain-Tabelle  v0.10.55"""

import os, re, json, time, shlex, threading, subprocess, urllib.request as _ur
import sys as _sys
_PIDRIVE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PIDRIVE not in _sys.path:
    _sys.path.insert(0, _PIDRIVE)
import log, ipc
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
try:
    from modules import source_state as _src_state
except Exception:
    _src_state = None
try:
    from modules import audio as _audio
except Exception:
    _audio = None

ERR_FILE        = "/tmp/pidrive_dab_welle.err"   # stderr
STDOUT_FILE     = "/tmp/pidrive_dab_welle_out.txt"  # stdout (DLS, service list)
PLAY_DEBUG_FILE = "/tmp/pidrive_dab_play_debug.json"
SCAN_DEBUG_FILE = "/tmp/pidrive_dab_scan_debug.json"
C_DAB           = (0, 200, 180)

_player_proc    = None   # welle-cli Wiedergabe-Prozess
_scan_running   = False  # Scan läuft gerade
_last_scan_diag = {}

_dls_thread     = None
_dls_stop_event = threading.Event()
_dab_session_id = ""
_dab_session_lock = threading.RLock()
_dab_play_lock = threading.RLock()
_play_debug_lock = threading.Lock()

def _err_file_for_session(session_id: str = "") -> str:
    """Immer die einzelne rotierende DAB-Fehlerdatei zurückgeben.
    Session-spezifische Dateien würden sich unbegrenzt akkumulieren."""
    return ERR_FILE  # /tmp/pidrive_dab_welle.err — wird überschrieben







# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _write_json_atomic(path, data):
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    use_lock = path == PLAY_DEBUG_FILE
    if use_lock:
        _play_debug_lock.acquire()
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log.warn(f"DAB write json {path}: {e}")
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        if use_lock:
            _play_debug_lock.release()


def _read_welle_log_tail(path: str, pos: int) -> tuple:
    """Neue Zeilen aus welle stderr/stdout (inkrementell, mit Tail-Cap)."""
    if not path or not os.path.exists(path):
        return [], pos
    try:
        fsize = os.path.getsize(path)
        if pos > fsize:
            pos = max(0, fsize - 200)
        elif fsize - pos > 80_000:
            pos = fsize - 80_000
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(pos)
            chunk = f.read()
            lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
            return lines, f.tell()
    except Exception:
        return [], pos


def _welle_line_flags(line: str) -> dict:
    """Sync/PCM/Superframe-Marker in welle-cli Logzeile (stdout oder stderr)."""
    low = (line or "").strip().lower()
    return {
        "sync": "found sync" in low,
        "superframe": "superframe sync succeeded" in low,
        "pcm": (
            "pcm name:" in low
            or "pcm state: prepared" in low
            or "create audio output" in low
        ),
        "service_list": low == "service list" or low.startswith("service list"),
        "programme_prompt": "please enter programme name" in low,
    }


def _is_welle_noise_line(line: str) -> bool:
    """Harmloses welle-cli stderr — nicht als dab_last_error werten."""
    low = (line or "").strip().lower()
    if not low:
        return True
    if any(x in low for x in [
        "airspy", "airpsy_open",
        "r82xx", "pll not locked",
        "wait for sync",
        "rtlsdr_read_async",
        "utctime",
        "sync on phase", "synconphase",
        "lost coarse sync", "lost fine sync",
        "synconendnull", "syncondnull",
    ]):
        return True
    if '"tii"' in low or low.startswith("tii:"):
        return True
    if low.startswith("[0x") and "component" in low:
        return True
    if "ascty:" in low and "subch" in low:
        return True
    return False


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


def _limit_file_size(path, max_bytes=2_000_000):
    """Begrenzt Dateigröße auf max_bytes — behält letzte Bytes (neueste Daten)."""
    try:
        size = os.path.getsize(path)
        if size > max_bytes:
            with open(path, "rb") as f:
                f.seek(-max_bytes, 2)
                tail = f.read()
            with open(path, "wb") as f:
                f.write(tail)
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

    if _is_welle_noise_line(line):
        return None

    if any(x in low for x in [
        "failed",
        "lost coarse sync",
        "lost fine sync",
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

def _parse_signal_line(line):
    """Extrahiert SNR/RSSI/Freq-Offset aus welle-cli stderr-Zeilen."""
    import re as _re
    result = {}
    low = (line or "").lower()
    m = _re.search(r'snr[=: ]+([0-9.]+)', low)
    if m: result['snr_db'] = float(m.group(1))
    m = _re.search(r'(?:rssi|signal)[=: ]+(-?[0-9.]+)', low)
    if m: result['rssi_dbm'] = float(m.group(1))
    m = _re.search(r'coarsecorrector[=: ]+(-?[0-9]+)', low)
    if m: result['freq_offset'] = int(m.group(1))
    return result if result else None

