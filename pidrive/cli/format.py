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
    out(f"  Sender/Titel: {title}")
    if d.get("artist"): out(f"  Artist:       {d['artist']}")
    if d.get("dls"):    out(f"  DLS:          {d['dls']}")
    dab_ps = d.get("dab_play_state","")
    if dab_ps and dab_ps not in ("idle","locked"):
        out(f"  DAB-Status:   {dab_ps}")
    out()
    out(_c("Audio", BOLD))
    out(f"  Ausgang:      {d.get('audio_eff', '–')}")
    out(f"  Lautstärke:   {d.get('volume', '–')}")
    out()
    out(_c("Verbindungen", BOLD))
    bt_info = d.get("bt_device","") or ("verbunden" if d.get("bt") else "getrennt")
    out(f"  Bluetooth:    {bt_info}")
    wifi_info = (d.get("wifi_ssid") or "–") if d.get("wifi") else "aus"
    out(f"  WiFi:         {wifi_info}")

def print_now(d: dict):
    if not d.get("playing") and not d.get("source"):
        out("Nichts läuft gerade.")
        return
    src = d.get("source", "")
    if src:
        out(_c(f"[{src}]", CYAN) + "  " + (d.get("title") or "–"))
    else:
        out(d.get("title") or "–")
    if d.get("artist"): out(_c("  Artist: ", DIM) + d["artist"])
    if d.get("dls"):    out(_c("  DLS:    ", DIM) + d["dls"])
    if d.get("metadata_unavailable"):
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
    out(_c(f"{title} — {len(devices)} Gerät(e):", BOLD))
    for d in devices:
        mac   = d.get("mac","?")
        name  = d.get("name","?")
        conn  = "✓" if d.get("connected") else " "
        trust = "★" if d.get("trusted") else " "
        out(f"  {conn}{trust}  {name:<25}  {_c(mac, DIM)}")

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
