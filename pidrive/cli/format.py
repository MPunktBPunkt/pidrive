#!/usr/bin/env python3
"""cli_format.py — PiDrive CLI: Ausgabe-Formatierung"""
import json
import sys

BOLD  = "\033[1m"
DIM   = "\033[2m"
GREEN = "\033[32m"
YELLOW= "\033[33m"
RED   = "\033[31m"
CYAN  = "\033[36m"
RESET = "\033[0m"

def _c(text, code):
    return f"{code}{text}{RESET}"

def out(text=""):
    print(text)

def err(text):
    print(f"{RED}Fehler: {text}{RESET}", file=sys.stderr)

def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

def print_status(d: dict):
    online = d.get("online", False)
    src    = d.get("source", "idle")
    out(_c(f"PiDrive {'online' if online else 'OFFLINE'}", GREEN if online else RED))
    out()
    out(_c("Wiedergabe", BOLD))
    out(f"  Quelle:       {src or '–'}")
    title = d.get("track") or d.get("radio_name") or "–"
    if src and src != "idle":
        out(f"  Sender/Titel: {title}")
        if d.get("artist"): out(f"  Artist:       {d['artist']}")
        if d.get("dls"):    out(f"  DLS:          {d['dls']}")
    else:
        out(f"  Sender/Titel: –")  # Keine aktive Quelle
    dab_ps = d.get("dab_play_state","")
    # DAB-Status nur zeigen wenn Quelle gerade DAB ist
    if d.get("source","") == "dab" and dab_ps and dab_ps != "locked":
        out("  DAB-Status:   " + dab_ps)
    out()
    out(_c("Audio", BOLD))
    _audio = d.get("audio_eff", "–")
    if _audio == "virtual": _audio = "virtuell (Container)"
    out(f"  Ausgang:      {_audio}")
    vol = d.get("volume"); out("  Lautstaerke:  " + (str(vol) + "%" if vol is not None else "–"))
    out()
    out(_c("Verbindungen", BOLD))
    bt_info = d.get("bt_device","") or ("verbunden" if d.get("bt") else "getrennt")
    out(f"  Bluetooth:    {bt_info}")
    sp = "aktiv ✓" if d.get("spotify") else "inaktiv"
    out(f"  Spotify:      {sp}")
    wifi_info = (d.get("wifi_ssid") or "–") if d.get("wifi") else "aus"
    out(f"  WiFi:         {wifi_info}")

def print_now(d: dict):
    src    = d.get("source", "")
    title  = d.get("title", "")
    playing = d.get("playing", False)

    if not playing and not src:
        out("Nichts läuft gerade.")
        return

    # Quelle aktiv aber keine Metadaten → sinnvoll anzeigen statt "–"
    _title_display = title or ("(Sender läuft, Metadaten folgen...)"
                               if playing else "(keine Metadaten)")

    if src:
        out(_c(f"[{src}]", CYAN) + "  " + _title_display)
    else:
        out(_title_display)

    if d.get("artist"): out(_c("  Artist: ", DIM) + d["artist"])
    if d.get("dls"):    out(_c("  DLS:    ", DIM) + d["dls"])
    if d.get("source_error"):
        out(_c(f"  ⚠ {d['source_error']}", YELLOW))
    elif d.get("metadata_unavailable") and not title:
        out(_c("  (Metadaten nicht verfügbar)", YELLOW))

def print_quick(d: dict):
    out(f"{_c('Quelle', BOLD)}  {d.get('source','–')}")
    out(f"{_c('Titel ', BOLD)}  {d.get('title','–')}")
    out(f"{_c('Vol   ', BOLD)}  {d.get('volume','–')}")
    out(f"{_c('Audio ', BOLD)}  {d.get('audio','–')}")
    out(f"{_c('BT    ', BOLD)}  {d.get('bt','–')}")
    out(f"{_c('WiFi  ', BOLD)}  {d.get('wifi','–')}")

def print_stations(stations: list, source: str):
    out(_c(f"Sender ({source.upper()}) — {len(stations)} Einträge:", BOLD))
    for i, s in enumerate(stations, 1):
        name = s.get("name", "?")
        extra = s.get("freq","") or s.get("channel","") or s.get("url","")[:40]
        fav = "★ " if s.get("favorite") else "  "
        out(f"  {i:3}.  {fav}{name:<30}  {_c(str(extra), DIM)}")

def print_favorites(favs: list):
    out(_c(f"Favoriten — {len(favs)} Einträge:", BOLD))
    for i, f in enumerate(favs, 1):
        src = f.get("source","?")
        out(f"  {i:2}.  {f.get('name','?'):<30}  {_c('['+src+']', DIM)}")

def print_bt_list(devices: list, title: str):
    if not devices:
        out(f"{title}: (leer)")
        return
    # Trenne echte Audio-Geräte von BLE-Rauschen
    audio = [d for d in devices if not d.get("ble_random_mac") and not d.get("random_mac")]
    ble   = [d for d in devices if d.get("ble_random_mac") or d.get("random_mac")]
    show  = audio if audio else devices  # Fallback: alles zeigen
    out(_c(f"{title} — {len(show)} Gerät(e):", BOLD))
    for d in show:
        mac    = d.get("mac","?")
        name   = d.get("name","?") or mac
        paired = "✓P" if d.get("paired") else "  "
        conn   = "✓" if d.get("connected") else " "
        trust  = "★" if d.get("trusted") else " "
        dtype = d.get("device_type", "")
        dtype_tag = ""
        if dtype == "avrcp_controller": dtype_tag = _c(" [AVRCP]", "[96m")
        elif dtype == "headphones":     dtype_tag = _c(" [Kopfhörer]", DIM)
        elif dtype == "speaker":        dtype_tag = _c(" [Lautsprecher]", DIM)
        out(f"  {conn}{trust}{paired}  {name:<25}  {_c(mac, DIM)}{dtype_tag}")
    if ble:
        out(f"  {_c(f'(+ {len(ble)} BLE-Geräte ohne Audio ausgeblendet)', DIM)}")

def print_resources(r: dict):
    out(_c("Systemressourcen:", BOLD))
    out(f"  RAM:        {r.get('ram','–')}")
    out(f"  Speicher:   {r.get('disk','–')}")
    out(f"  Uptime:     {r.get('uptime','–')}")
    thr = r.get("throttled","")
    if thr and thr != "0x0":
        out(_c(f"  Throttled:  {thr}  ← Unterspannung!", YELLOW))
    else:
        out(f"  Throttled:  {thr or '0x0'}  ✓")

def print_dab_status(data: dict):
    d = data.get("data") or {}
    if not d:
        out("Kein DAB aktiv.")
        return
    out(_c("DAB Status:", BOLD))
    out(f"  Sender:        {d.get('name','–')}")
    out(f"  Kanal/SID:     {d.get('channel','–')} / {d.get('service_id','–')}")
    out(f"  State:         {d.get('dab_state', d.get('state','–'))}")
    sync_ok = d.get("sync_ok") or d.get("dab_sync_ok", False)
    pcm     = d.get("dab_pcm_seen", d.get("pcm_seen", False))
    out(f"  Sync OK:       {'✓' if sync_ok else '✗'}")
    out(f"  PCM:           {'✓' if pcm else '✗'}")
    dls = d.get("last_dls_raw") or d.get("dls_text","")
    if dls:
        out(f"  DLS:           {dls}")
    err_line = d.get("last_error_line") or d.get("dab_last_error","")
    if err_line:
        out(_c(f"  Fehler:        {err_line}", YELLOW))


def _yn(v):
    return (GREEN + "ja" + RESET) if v else (DIM + "nein" + RESET)

def _state_color(state):
    if state in ("playing", "pcm_seen", "audio_ready"): return GREEN + state + RESET
    if state in ("partial_sync",): return YELLOW + state + RESET
    if state in ("no_lock", "failed", "error"): return RED + state + RESET
    return state or "?"

def format_dab_live_block(snap: dict) -> str:
    """Kompakter Refresh-Block für pidrivectl dab live."""
    import datetime as _dt
    ts   = _dt.datetime.fromtimestamp(snap["ts"]).strftime("%H:%M:%S")
    src  = snap.get("source_current", "?")
    name = snap.get("radio_name", "?") or "?"
    ch   = snap.get("channel", "") or "–"
    sid  = snap.get("service_id", "") or "–"
    st   = _state_color(snap.get("dab_playback_state", "?"))
    err  = snap.get("last_error", "") or "–"
    dls  = snap.get("dls_text", "") or "–"
    art  = snap.get("artist", "") or ""
    trk  = snap.get("track", "") or ""
    ef   = snap.get("sess_err_file", "") or "–"
    warns = snap.get("warnings", [])

    lines = [
        BOLD + "DAB LIVE" + RESET + "  [" + ts + "]  Quelle: " + src,
        "  Sender:      " + BOLD + name + RESET,
        "  Kanal:       " + ch + "  SID: " + sid,
        "  State:       " + st,
        "  Attempting:  " + _yn(snap.get("dab_attempting")),
        "  Sync OK:     " + _yn(snap.get("dab_sync_ok")) +
            ("  (partial)" if snap.get("dab_partial_sync") else ""),
        "  Superframe:  " + _yn(snap.get("dab_superframe_seen")),
        "  PCM:         " + _yn(snap.get("dab_pcm_seen")),
        "  Audio ready: " + _yn(snap.get("dab_audio_ready")),
        "  Radio spielt:" + _yn(snap.get("radio_playing")),
        "  Audio-Ausgang:" + (snap.get("audio_route") or "?"),
        "  DLS:         " + dls[:60],
    ]
    if art or trk:
        lines.append("  Titel:       " + " – ".join(filter(None, [art, trk]))[:60])
    lines.append("  Letzter Fehler: " + err[:70])
    lines.append("  Errfile:     " + ef)
    if warns:
        for w in warns:
            lines.append("  " + YELLOW + "⚠  " + w + RESET)
    return "\n".join(lines)


def format_dab_change_line(snap: dict, diff: dict) -> str:
    """Eine Zeile für --changes Modus."""
    import datetime as _dt
    ts = _dt.datetime.fromtimestamp(snap["ts"]).strftime("%H:%M:%S")
    parts = []
    for k, v in sorted(diff.items()):
        if isinstance(v, bool): parts.append(k + "=" + ("ja" if v else "nein"))
        elif v == "" or v is None: parts.append(k + "=–")
        else: parts.append(k + "=" + repr(str(v)[:40]))
    warn_str = ""
    for w in snap.get("warnings", []):
        warn_str += "  " + YELLOW + "⚠ " + w + RESET
    return ts + "  " + "  ".join(parts) + warn_str

