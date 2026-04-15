#!/usr/bin/env python3
"""
avrcp_trigger.py - PiDrive AVRCP → File-Trigger Bridge
Phase 1: kontextabhängiges Mapping + Debug-JSON

Kontexte:
  - menu
  - radio         (FM / DAB / WEB)
  - scanner       (pmr446 / freenet / lpd433 / cb / vhf / uhf)
  - list_overlay  (modale Auswahl aktiv)

BMW / AVRCP 1.5:
  - next / previous / play_pause / stop
  - fast_forward / rewind
  - volumeup / volumedown
"""

import subprocess
import sys
import os
import time
import signal
import threading
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import log

CMD_FILE    = "/tmp/pidrive_cmd"
READY_FILE  = "/tmp/pidrive_ready"
STATUS_FILE = "/tmp/pidrive_status.json"
MENU_FILE   = "/tmp/pidrive_menu.json"
LIST_FILE   = "/tmp/pidrive_list.json"
DEBUG_FILE  = "/tmp/pidrive_avrcp.json"

DOUBLE_TAP_SEC = 0.5

_last_enter_time = 0.0
_last_event_ts   = 0.0
_last_event_name = ""
_last_trigger    = ""
_last_context    = ""
_last_source     = ""


def read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_debug(data):
    """Atomares Schreiben des AVRCP-Debug-JSON."""
    try:
        tmp = DEBUG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DEBUG_FILE)
    except Exception:
        pass


def write_cmd(cmd: str):
    """Trigger-Datei schreiben."""
    global _last_trigger
    try:
        with open(CMD_FILE, "w", encoding="utf-8") as f:
            f.write(cmd.strip() + "\n")
        _last_trigger = cmd
        log.info(f"AVRCP → {cmd}")
    except Exception as e:
        log.error(f"write_cmd: {e}")


def get_context():
    """
    Bedienkontext aus IPC-Dateien ableiten.

    Priorität:
      1. list.json aktiv          -> list_overlay
      2. status radio/scanner     -> radio / scanner
      3. sonst                    -> menu
    """
    status = read_json(STATUS_FILE, {})
    menu   = read_json(MENU_FILE, {})
    lst    = read_json(LIST_FILE, {})

    # 1. Modale Auswahl
    if lst.get("active"):
        return {
            "context": "list_overlay",
            "status": status, "menu": menu, "list": lst, "band": ""
        }

    radio_on   = bool(status.get("radio", False))
    radio_type = (status.get("radio_type", "") or "").upper()

    # 2. Scanner-Kontext
    if radio_on and radio_type == "SCANNER":
        band = ""
        path = menu.get("path", [])
        if path:
            low_path = " / ".join(str(x).lower() for x in path)
            for cand in ("pmr446", "freenet", "lpd433", "cb", "vhf", "uhf"):
                if cand in low_path:
                    band = cand
                    break
        # Fallback: aus radio_name raten
        if not band:
            rs = (status.get("radio_name") or status.get("radio_station") or "").lower()
            for cand, keys in [
                ("pmr446",  ["pmr"]),
                ("freenet", ["freenet"]),
                ("lpd433",  ["lpd"]),
                ("cb",      ["cb-funk", "cb funk", " cb "]),
                ("vhf",     ["vhf"]),
                ("uhf",     ["uhf"]),
            ]:
                if any(k in rs for k in keys):
                    band = cand
                    break

        return {
            "context": "scanner",
            "status": status, "menu": menu, "list": lst, "band": band
        }

    # 3. Radio-Kontext
    if radio_on:
        return {
            "context": "radio",
            "status": status, "menu": menu, "list": lst, "band": ""
        }

    # 4. Standard: Menü
    return {
        "context": "menu",
        "status": status, "menu": menu, "list": lst, "band": ""
    }


def map_event(event: str, ctx: dict):
    """AVRCP-Event → PiDrive Trigger je Kontext."""
    context    = ctx.get("context", "menu")
    status     = ctx.get("status", {})
    band       = ctx.get("band", "")
    radio_type = (status.get("radio_type", "") or "").upper()

    # Volume: immer global
    if event in ("volumeup",   "volume_up"):   return "vol_up"
    if event in ("volumedown", "volume_down"): return "vol_down"

    # Modale Auswahl: reine Navigation
    if context == "list_overlay":
        return {
            "next": "down",  "previous": "up",
            "play": "enter", "pause": "enter", "play_pause": "enter",
            "stop": "back",
            "fast_forward": "down", "rewind": "up",
        }.get(event)

    # Scanner
    if context == "scanner":
        if band in ("vhf", "uhf"):
            # Stufenlos: Feinschritt ±25kHz, Grobschritt ±1MHz
            return {
                "next":         f"scan_step:{band}:0.025",
                "previous":     f"scan_step:{band}:-0.025",
                "fast_forward": f"scan_step:{band}:1.0",
                "rewind":       f"scan_step:{band}:-1.0",
                "play":         f"scan_next:{band}",
                "pause":        f"scan_next:{band}",
                "play_pause":   f"scan_next:{band}",
                "stop":         "back",
            }.get(event)
        else:
            # Kanal-Bänder: pmr446/freenet/lpd433/cb
            jump = 10 if band == "cb" else 1
            return {
                "next":         f"scan_up:{band}"          if band else "down",
                "previous":     f"scan_down:{band}"        if band else "up",
                "fast_forward": f"scan_jump:{band}:{jump}" if band else "down",
                "rewind":       f"scan_jump:{band}:-{jump}"if band else "up",
                "play":         f"scan_next:{band}"        if band else "enter",
                "pause":        f"scan_next:{band}"        if band else "enter",
                "play_pause":   f"scan_next:{band}"        if band else "enter",
                "stop":         "back",
            }.get(event)

    # Radio
    if context == "radio":
        if radio_type == "FM":
            return {
                "next": "fm_next",  "previous": "fm_prev",
                "fast_forward": "fm_next", "rewind": "fm_prev",
                "play": "radio_stop", "pause": "radio_stop",
                "play_pause": "radio_stop",
                "stop": "back",
            }.get(event)

        if radio_type == "DAB":
            return {
                "next": "dab_next", "previous": "dab_prev",
                "fast_forward": "dab_next", "rewind": "dab_prev",
                "play": "radio_stop", "pause": "radio_stop",
                "play_pause": "radio_stop",
                "stop": "back",
            }.get(event)

        # WEB oder unbekannter Radio-Typ: konservativ Menü-Navigation
        return {
            "next": "down",  "previous": "up",
            "play": "radio_stop", "pause": "radio_stop",
            "play_pause": "radio_stop",
            "stop": "back",
            "fast_forward": "down", "rewind": "up",
        }.get(event)

    # Standard: Menü-Navigation
    return {
        "next": "down",  "previous": "up",
        "play": "enter", "pause": "enter", "play_pause": "enter",
        "stop": "back",
        "fast_forward": "down", "rewind": "up",
    }.get(event)


def handle_avrcp(event: str, source="unknown"):
    global _last_enter_time, _last_event_ts, _last_event_name, _last_context, _last_source

    event = event.strip().lower()
    if not event:
        return

    if not os.path.exists(READY_FILE):
        return

    ctx          = get_context()
    context_name = ctx.get("context", "menu")

    _last_event_ts   = time.time()
    _last_event_name = event
    _last_context    = context_name
    _last_source     = source

    debug_ctx = {
        "radio_type": ctx["status"].get("radio_type", ""),
        "radio":      ctx["status"].get("radio", False),
        "band":       ctx.get("band", ""),
        "menu_path":  ctx["menu"].get("path", []),
        "list_active":ctx["list"].get("active", False),
    }

    # Doppelklick Play/Pause → direkt "Jetzt läuft"
    if event in ("play", "pause", "play_pause"):
        now = time.time()
        if now - _last_enter_time < DOUBLE_TAP_SEC:
            write_cmd("cat:0")
            _last_enter_time = 0.0
            write_debug({"ts": now, "last_event": event, "context": context_name,
                         "trigger": "cat:0", "source": source, "ctx": debug_ctx})
            log.info(f"AVRCP event={event} src={source} ctx={context_name} -> cat:0 (double-tap)")
            return
        _last_enter_time = now

    trigger = map_event(event, ctx)
    if trigger:
        write_cmd(trigger)
        write_debug({"ts": time.time(), "last_event": event, "context": context_name,
                     "trigger": trigger, "source": source, "ctx": debug_ctx})
        log.info(f"AVRCP event={event} src={source} ctx={context_name} -> {trigger}")
    else:
        write_debug({"ts": time.time(), "last_event": event, "context": context_name,
                     "trigger": "", "source": source, "ctx": debug_ctx})
        log.info(f"AVRCP event={event} src={source} ctx={context_name} -> (ignored)")


def parse_bluetoothctl_line(line: str):
    """AVRCP-Event aus bluetoothctl-Ausgabe extrahieren."""
    line_l = line.lower()

    if "avrcp" in line_l or "player" in line_l:
        for keyword in (
            "next", "previous", "play_pause", "play", "pause", "stop",
            "fast_forward", "rewind",
            "volumeup", "volumedown", "volume_up", "volume_down"
        ):
            if keyword in line_l:
                return keyword

    for keyword in ("next", "previous", "playpause", "play", "pause", "stop",
                    "fast_forward", "rewind"):
        if f'"{keyword}"' in line_l or f"'{keyword}'" in line_l:
            return "play_pause" if keyword == "playpause" else keyword

    return None


def monitor_bluetoothctl():
    log.info("AVRCP: starte bluetoothctl monitor ...")
    try:
        proc = subprocess.Popen(
            ["bluetoothctl", "monitor"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        for line in proc.stdout:
            event = parse_bluetoothctl_line(line)
            if event:
                handle_avrcp(event, source="bluetoothctl")
    except Exception as e:
        log.error(f"AVRCP monitor: {e}")


def monitor_dbus():
    log.info("AVRCP: starte dbus-monitor (MediaPlayer2)...")
    try:
        proc = subprocess.Popen(
            ["dbus-monitor",
             "interface=org.mpris.MediaPlayer2.Player",
             "type=signal"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        for line in proc.stdout:
            line_s = line.strip()
            event = None
            if '"\'Next\'"'     in line_s: event = "next"
            elif '"\'Previous\'"'in line_s: event = "previous"
            elif '"\'PlayPause\'"'in line_s: event = "play_pause"
            elif '"\'Play\'"'    in line_s: event = "play"
            elif '"\'Pause\'"'   in line_s: event = "pause"
            elif '"\'Stop\'"'    in line_s: event = "stop"
            if event:
                handle_avrcp(event, source="dbus-monitor")
    except Exception as e:
        log.error(f"AVRCP dbus: {e}")


def auto_connect_bmw():
    """Gepairte Geräte beim Start verbinden."""
    try:
        r = subprocess.run(
            "bluetoothctl devices Paired 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) >= 2:
                mac  = parts[1]
                name = parts[2] if len(parts) > 2 else mac
                log.info(f"AVRCP: verbinde {name} ({mac})")
                subprocess.Popen(
                    f"bluetoothctl connect {mac}",
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
    except Exception as e:
        log.error(f"auto_connect: {e}")


def main():
    log.setup("core")
    log.info("=" * 50)
    log.info("PiDrive AVRCP Phase 1 gestartet")
    log.info("  Kontextbasiertes Mapping aktiv")
    log.info("  Kontexte: menu / radio / scanner / list_overlay")
    log.info("=" * 50)

    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    auto_connect_bmw()

    t1 = threading.Thread(target=monitor_bluetoothctl, daemon=True)
    t2 = threading.Thread(target=monitor_dbus, daemon=True)
    t1.start()
    t2.start()

    log.info("AVRCP: Warte auf Events ...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
