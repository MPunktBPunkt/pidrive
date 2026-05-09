"""web/shared/view_model.py — ViewModel für Templates, DLS, DAB-Status"""
import json
import os
import time
from web.shared.constants import (
    STATUS_FILE, MENU_FILE, PROGRESS_FILE, RTLSDR_FILE, AVRCP_FILE, LIST_FILE, READY_FILE, KNOWN_BT_FILE, BT_AGENT_FILE, DAB_DEBUG_FILE, STATIONS_FILE, BASE_DIR
)




def read_json(path, default=None):
    """Liest eine JSON-Datei sicher."""
    if default is None:
        default = {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

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
        # v0.10.55: Audio-Routing-Debug aus play_debug.json
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
