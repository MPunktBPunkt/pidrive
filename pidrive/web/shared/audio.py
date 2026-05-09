"""web/shared/audio.py — Audio-Debug, Volume, Source-State"""
import json
import os
import subprocess
from web.shared.constants import (
    PA_ENV, STATUS_FILE, BASE_DIR
)



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

def get_volume_data() -> dict:
    try:
        import re as _re
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
        from modules import source_state
        return source_state.load_snapshot_file() or source_state.snapshot()
    except Exception as e:
        return {"error": str(e)}
