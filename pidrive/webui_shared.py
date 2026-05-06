#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webui_shared.py — Shared helpers für PiDrive WebUI Blueprints  v0.10.46
"""

import os
import sys
import json
import time
import threading
import socket
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CMD_FILE = "/tmp/pidrive_cmd"
STATUS_FILE = "/tmp/pidrive_status.json"
MENU_FILE = "/tmp/pidrive_menu.json"
PROGRESS_FILE = "/tmp/pidrive_progress.json"
RTLSDR_FILE = "/tmp/pidrive_rtlsdr.json"
AVRCP_FILE = "/tmp/pidrive_avrcp.json"
LIST_FILE = "/tmp/pidrive_list.json"
LOG_FILE = "/var/log/pidrive/pidrive.log"
READY_FILE = "/tmp/pidrive_ready"
KNOWN_BT_FILE = "/tmp/pidrive_bt_known_devices.json"
BT_AGENT_FILE = "/tmp/pidrive_bt_agent.json"
STATIONS_FILE = os.path.join(BASE_DIR, "pidrive", "config", "stations.json")

DAB_DEBUG_FILE = "/tmp/pidrive_dab_play_debug.json"

ALLOWED_COMMANDS = {
    "up", "down", "left", "right", "enter", "back",
    "wifi_on", "wifi_off", "wifi_toggle", "wifi_scan",
    "bt_on", "bt_off", "bt_toggle", "bt_scan",
    "bt_disconnect", "bt_reconnect_last",
    "spotify_on", "spotify_off", "spotify_toggle",
    "radio_stop", "library_stop",
    "audio_klinke", "audio_hdmi", "audio_bt", "audio_all",
    "vol_up", "vol_down",
    "gain_fm_auto", "gain_dab_auto",
    "dab_scan", "dab_scan_replace", "fm_scan",
    "fm_next", "fm_prev", "dab_next", "dab_prev",
    "lib_browse",
    "reboot", "shutdown", "sys_info", "sys_version", "update",
    "rtlsdr_reset",
    "bt_backup", "bt_restore",
}

PA_ENV = "PULSE_SERVER=unix:/var/run/pulse/native"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_cmd(cmd):
    with open(CMD_FILE, "w", encoding="utf-8") as f:
        f.write(cmd.strip() + "\n")


def file_age(path):
    try:
        return round(time.time() - os.path.getmtime(path), 1)
    except Exception:
        return None


# v0.10.46: IP-Cache (30s TTL) — verhindert Socket-Open bei jedem Request
_ip_cache: tuple = ("", 0.0)

def get_ip() -> str:
    global _ip_cache
    import time as _t
    if _t.time() - _ip_cache[1] < 30.0 and _ip_cache[0]:
        return _ip_cache[0]
    ip = "?"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    _ip_cache = (ip, _t.time())
    return ip


def safe_run(cmd):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=15
        )
        return {
            "ok": r.returncode == 0,
            "code": r.returncode,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "cmd": cmd,
        }
    except Exception as e:
        return {
            "ok": False,
            "code": -1,
            "stdout": "",
            "stderr": str(e),
            "cmd": cmd,
        }


def get_version():
    try:
        # VERSION liegt im gleichen Verzeichnis wie webui_shared.py (pidrive/)
        _ver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
        with open(_ver_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "?"


def _sink_is_hdmi(name: str) -> bool:
    import re
    n = (name or "").lower()
    if "hdmi" in n:
        return True
    if re.search(r"alsa_output\.0\.", name or ""):
        return True
    return False


def _first_nonempty(*values):
    for v in values:
        if isinstance(v, str):
            if v.strip():
                return v.strip()
        elif v:
            return v
    return ""


def _compose_dls_text(artist: str, track: str, fallback_text: str = "") -> str:
    artist = (artist or "").strip()
    track = (track or "").strip()
    fallback_text = (fallback_text or "").strip()

    if artist and track:
        return f"{artist} - {track}"
    if track:
        return track
    if artist:
        return artist
    return fallback_text


# ──────────────────────────────────────────────────────────────────────────────
# Audio Debug
# ──────────────────────────────────────────────────────────────────────────────

def get_volume_data() -> dict:
    try:
        import re as _re
        import sys as _sys
        _b = str(BASE_DIR)
        if _b not in _sys.path:
            _sys.path.insert(0, _b)

        sinks_out = (safe_run(PA_ENV + " pactl list sinks short 2>/dev/null").get("stdout", "") or "")
        sink = ""
        source_label = ""

        sin_out = (safe_run(PA_ENV + " pactl list sink-inputs short 2>/dev/null").get("stdout", "") or "")
        active_sink_ids = set()
        for ln in sin_out.splitlines():
            p = ln.split()
            if len(p) >= 2 and p[0].isdigit():
                active_sink_ids.add(p[1])

        sink_id_to_name = {}
        for ln in sinks_out.splitlines():
            p = ln.split()
            if len(p) >= 2:
                sink_id_to_name[p[0]] = p[1]

        for sid in active_sink_ids:
            sname = sink_id_to_name.get(sid, "")
            if sname:
                sink = sname
                source_label = "active_input"
                break

        if not sink:
            for ln in sinks_out.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and "bluez_sink" in parts[1] and "a2dp_sink" in parts[1]:
                    sink = parts[1]
                    source_label = "bt_sink"
                    break
        if not sink:
            for ln in sinks_out.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and _re.search(r"alsa_output\.1\.", parts[1]):
                    sink = parts[1]
                    source_label = "alsa_card1"
                    break
        if not sink:
            for ln in sinks_out.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and "alsa_output" in parts[1] and not _sink_is_hdmi(parts[1]):
                    sink = parts[1]
                    source_label = "alsa_fallback"
                    break

        vol = ""
        if sink:
            full_out = (safe_run(PA_ENV + " pactl list sinks 2>/dev/null").get("stdout", "") or "")
            in_target = False
            for ln in full_out.splitlines():
                if _re.search(r"Name:\s*" + _re.escape(sink), ln, _re.IGNORECASE):
                    in_target = True
                elif ln.strip().startswith("Sink #") or (in_target and _re.search(r"name\s*=\s*\S+", ln) and sink not in ln):
                    if in_target:
                        break
                if in_target:
                    if ln.strip().startswith("Volume:") and "%" in ln:
                        m = _re.search(r"(\d+)%", ln)
                        if m:
                            vol = m.group(1) + "%"
                            break

        return {
            "ok": True,
            "volume": vol or "–",
            "sink": sink or "",
            "source": source_label
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "volume": "–"}


def get_audio_debug() -> dict:
    data = {
        "pulse_active": False,
        "default_sink": "",
        "sinks": [],
        "sink_inputs": [],
        "decision": {},
        "current_volume": "–",
    }

    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules.audio import read_last_decision_file
        data["decision"] = read_last_decision_file()
        dec = data["decision"]
        data["fallback_active"] = bool(
            dec.get("requested") and dec.get("effective") and
            dec.get("requested") != dec.get("effective")
        )
        data["fallback_reason"] = dec.get("reason", "")
    except Exception:
        data["decision"] = {}
        data["fallback_active"] = False
        data["fallback_reason"] = ""

    try:
        pa_svc = safe_run("systemctl is-active pulseaudio 2>/dev/null")
        pa_svc_ok = (pa_svc.get("stdout", "").strip() in ("active", "activating"))
        if pa_svc_ok:
            pa2 = safe_run(PA_ENV + " pactl info 2>/dev/null")
            pa_api_ok = bool(pa2.get("stdout", "").strip())
            data["pulse_active"] = True if pa_api_ok else "service_only"
        else:
            data["pulse_active"] = False
    except Exception:
        data["pulse_active"] = False

    try:
        ds = safe_run(PA_ENV + " pactl get-default-sink 2>/dev/null")
        data["default_sink"] = (ds.get("stdout", "") or "").strip()
        if not data["default_sink"]:
            info = safe_run(PA_ENV + " pactl info 2>/dev/null")
            for ln in (info.get("stdout", "") or "").splitlines():
                if "Default Sink:" in ln:
                    data["default_sink"] = ln.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    try:
        sinks = safe_run(PA_ENV + " pactl list sinks short 2>/dev/null")
        out = sinks.get("stdout", "") or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                typ = (
                    "bt" if "bluez_sink" in name else
                    "hdmi" if _sink_is_hdmi(name) else
                    "alsa" if "alsa_output" in name else
                    "other"
                )
                data["sinks"].append({
                    "id": parts[0],
                    "name": name,
                    "type": typ,
                    "raw": line.strip(),
                })
    except Exception:
        pass

    try:
        sin = safe_run(PA_ENV + " pactl list sink-inputs short 2>/dev/null")
        out = sin.get("stdout", "") or ""
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if not parts or not parts[0].isdigit():
                continue
            data["sink_inputs"].append({
                "id": parts[0],
                "sink_id": parts[1] if len(parts) > 1 else "",
                "client": parts[2] if len(parts) > 2 else "",
                "driver": parts[3] if len(parts) > 3 else "",
                "raw": line.strip(),
            })
    except Exception:
        pass

    try:
        detail = safe_run(PA_ENV + " pactl list sink-inputs 2>/dev/null")
        txt = detail.get("stdout", "") or ""
        blocks = txt.split("Sink Input #")
        parsed = {}
        for block in blocks[1:]:
            lines = block.splitlines()
            if not lines:
                continue
            sid = lines[0].strip()
            item = {
                "application_name": "",
                "process_binary": "",
                "process_id": "",
                "media_name": "",
            }
            for ln in lines:
                s = ln.strip()
                if 'application.name = "' in s:
                    item["application_name"] = s.split('"')[1]
                elif 'application.process.binary = "' in s:
                    item["process_binary"] = s.split('"')[1]
                elif 'application.process.id = "' in s:
                    item["process_id"] = s.split('"')[1]
                elif 'media.name = "' in s:
                    item["media_name"] = s.split('"')[1]
            parsed[sid] = item

        sink_id_map = {s["id"]: s["name"] for s in data["sinks"]}
        for row in data["sink_inputs"]:
            extra = parsed.get(str(row.get("id", "")), {})
            row.update(extra)
            row["app_name"] = extra.get("application_name") or extra.get("media_name") or ""
            row["binary"] = extra.get("process_binary", "")
            row["pid"] = extra.get("process_id", "")
            row["sink_name"] = sink_id_map.get(row.get("sink_id", ""), "")
    except Exception:
        pass

    try:
        vol = get_volume_data()
        if isinstance(vol, dict):
            data["current_volume"] = vol.get("volume", "–")
    except Exception:
        pass

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Source / DAB / Spectrum Debug
# ──────────────────────────────────────────────────────────────────────────────

def get_source_state_debug():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules import source_state
        return source_state.load_snapshot_file() or source_state.snapshot()
    except Exception as e:
        return {"error": str(e)}


def get_dab_scan_debug():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules import dab
        return dab.load_last_scan_diag_file() or dab.get_last_scan_diag()
    except Exception as e:
        return {"error": str(e)}


def get_spectrum_debug():
    try:
        _base = str(BASE_DIR)
        if _base not in sys.path:
            sys.path.insert(0, _base)
        from modules import spectrum
        return spectrum.load_last_spectrum()
    except Exception as e:
        return {"error": str(e)}


def get_dab_status_debug():
    dbg = read_json(DAB_DEBUG_FILE, {})
    st = read_json(STATUS_FILE, {})

    artist = _first_nonempty(
        dbg.get("artist"),
        dbg.get("last_dls_artist"),
        st.get("artist"),
    )

    track = _first_nonempty(
        dbg.get("track"),
        dbg.get("last_dls_track"),
        st.get("track"),
    )

    dls_text = _first_nonempty(
        dbg.get("dls_raw"),
        dbg.get("dls"),
        dbg.get("last_dls_raw"),
        st.get("dls_raw"),
        st.get("dls"),
        st.get("radio_text"),
        _compose_dls_text(artist, track, st.get("track", "")),
    )

    merged = {
        "name": _first_nonempty(
            dbg.get("name"),
            st.get("radio_name"),
            st.get("radio_station"),
        ),
        "channel": _first_nonempty(dbg.get("channel")),
        "service_id": _first_nonempty(
            dbg.get("service_id"),
            st.get("dab_service_id"),
        ),
        "ensemble": _first_nonempty(
            dbg.get("ensemble"),
            st.get("dab_ensemble"),
        ),
        "gain": _first_nonempty(
            str(dbg.get("gain", "")) if dbg.get("gain", "") != "" else "",
        ),
        "ppm": _first_nonempty(
            str(dbg.get("ppm", "")) if dbg.get("ppm", "") != "" else "",
        ),
        "sync_ok": bool(dbg.get("sync_ok", st.get("dab_sync_ok", False))),
        "dab_state": _first_nonempty(
            dbg.get("dab_state"),
            st.get("dab_state"),
        ),
        "last_error_line": _first_nonempty(
            dbg.get("last_error_line"),
            st.get("dab_last_error"),
        ),
        "artist": artist,
        "track": track,
        "dls_text": dls_text,
        "dls_available": bool(dls_text),
        "radio_name": st.get("radio_name", ""),
        "radio_type": st.get("radio_type", ""),
        "radio_playing": bool(st.get("radio", False)),
        "dab_pcm_seen": st.get("dab_pcm_seen", False),
        "dab_sync_seen": st.get("dab_sync_seen", False),
        "dab_superframe_seen": st.get("dab_superframe_seen", False),
        "dab_audio_ready": st.get("dab_audio_ready", False),
        "ts": dbg.get("ts", st.get("ts", 0)),
        "debug_exists": os.path.exists(DAB_DEBUG_FILE),
        "debug_age": file_age(DAB_DEBUG_FILE),
        # v0.10.46: Audio-Routing-Debug aus play_debug.json
        "pulse_server_in_env":    dbg.get("pulse_server_in_env"),
        "pulse_sink_in_env":      dbg.get("pulse_sink_in_env"),
        "pa_default_sink":        dbg.get("pa_default_sink_before_start", ""),
        "welle_cmd":              dbg.get("welle_cmd", ""),
        "sess_err_file":          dbg.get("sess_err_file", ""),
    }

    if isinstance(dbg, dict):
        for k, v in dbg.items():
            if k not in merged:
                merged[k] = v

    return merged



def _load_stations_file():
    """stations.json lesen. Gibt dict mit 'stations'-Liste zurück."""
    try:
        with open(STATIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": 1, "stations": []}


# ──────────────────────────────────────────────────────────────────────────────
# View Model
# ──────────────────────────────────────────────────────────────────────────────

def build_view_model():
    status = read_json(STATUS_FILE, {})
    menu = read_json(MENU_FILE, {})
    progress = read_json(PROGRESS_FILE, {})
    rtlsdr = read_json(RTLSDR_FILE, {})
    avrcp = read_json(AVRCP_FILE, {})
    list_data = read_json(LIST_FILE, {})
    bt_known = read_json(KNOWN_BT_FILE, {"devices": []})
    bt_agent = read_json(BT_AGENT_FILE, {})

    nodes = menu.get("nodes", [])
    categories = menu.get("categories", [])
    items_list = menu.get("items", [])

    cursor = menu.get("cursor", 0)
    sel_node = nodes[cursor] if nodes and cursor < len(nodes) else {}

    debug = {
        "rev": menu.get("rev", 0),
        "path": menu.get("path", []),
        "title": menu.get("title", ""),
        "cursor": cursor,
        "can_back": menu.get("can_back", False),
        "selected_label": sel_node.get("label", "") if isinstance(sel_node, dict) else str(sel_node),
        "selected_type": sel_node.get("type", "") if isinstance(sel_node, dict) else "",
        "node_count": len(nodes),
        "core_ready": os.path.exists(READY_FILE),
        "status_age": file_age(STATUS_FILE),
        "menu_age": file_age(MENU_FILE),
    }

    return {
        "version": get_version(),
        "ip": get_ip(),
        "status": status,
        "menu": menu,
        "progress": progress,
        "rtlsdr": rtlsdr,
        "rtlsdr_age": file_age(RTLSDR_FILE),
        "rtlsdr_exists": os.path.exists(RTLSDR_FILE),
        "avrcp": avrcp,
        "avrcp_age": file_age(AVRCP_FILE),
        "avrcp_exists": os.path.exists(AVRCP_FILE),
        "audio_debug": get_audio_debug(),
        "source_state": get_source_state_debug(),
        "dab_scan_debug": get_dab_scan_debug(),
        "dab_status_debug": get_dab_status_debug(),
        "spectrum_debug": get_spectrum_debug(),
        "known_bt_devices": bt_known,
        "bt_agent": bt_agent,
        "processes": status.get("processes", []),
        "list_data": list_data,
        "list_active": list_data.get("active", False),
        "list_title": list_data.get("title", ""),
        "list_items": list_data.get("items", []),
        "list_selected": list_data.get("selected", 0),
        "nodes": nodes,
        "categories": categories,
        "items": items_list,
        "path": menu.get("path", []),
        "cursor": cursor,
        "rev": menu.get("rev", 0),
        "can_back": menu.get("can_back", False),
        "debug": debug,
        "status_age": file_age(STATUS_FILE),
        "menu_age": file_age(MENU_FILE),
        "progress_age": file_age(PROGRESS_FILE),
        "list_age": file_age(LIST_FILE),
        "status_exists": os.path.exists(STATUS_FILE),
        "menu_exists": os.path.exists(MENU_FILE),
        "progress_exists": os.path.exists(PROGRESS_FILE),
        "list_exists": os.path.exists(LIST_FILE),
        "log_exists": os.path.exists(LOG_FILE),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
