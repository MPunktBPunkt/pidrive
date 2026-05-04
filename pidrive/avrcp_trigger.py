#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
avrcp_trigger.py — PiDrive AVRCP → File-Trigger Bridge  v0.10.20

BMW / AVRCP 1.5:
  - BMW NBT EVO verbindet sich als AVRCP Controller
  - Drehsteller / Lenkradtasten → D-Bus-Signale
  - Dieser Prozess: D-Bus → /tmp/pidrive_cmd

v0.10.20 Debug-Erweiterungen:
  - Verboses Logging jedes Events: Raw-Linie, Kontext, Mapping, Latenz
  - Dedicated AVRCP-Raw-Logdatei für Autotest-Analyse
  - Nativer dbus-Python-Listener für PropertiesChanged (BlueZ MediaPlayer1)
  - Heartbeat-Log alle 60s (Lebenszeichen des Threads)
  - Alle D-Bus-Zeilen werden geloggt (nicht nur gematchte)
"""

import os
import sys
import json
import time
import signal
import threading
import subprocess
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log

STATUS_FILE  = "/tmp/pidrive_status.json"
MENU_FILE    = "/tmp/pidrive_menu.json"
LIST_FILE    = "/tmp/pidrive_list.json"
CMD_FILE     = "/tmp/pidrive_cmd"
AVRCP_FILE   = "/tmp/pidrive_avrcp.json"
READY_FILE   = "/tmp/pidrive_ready"

# v0.10.20: Dedicated AVRCP-Log für Autotest
AVRCP_RAW_LOG = "/var/log/pidrive/avrcp_raw.log"

DOUBLE_TAP_SEC = 1.2

_last_enter_time  = 0.0
_last_event_ts    = 0.0
_last_event_name  = ""
_last_context     = "startup"
_last_source      = ""
_last_trigger     = ""
_event_count      = 0       # Gesamtzahl AVRCP-Events
_lock             = threading.Lock()


# ── Logging-Hilfsfunktionen ───────────────────────────────────────────────────

def _raw_log(line: str):
    """
    v0.10.20: Jeden D-Bus/bluetoothctl-Rohdaten-Eintrag in AVRCP_RAW_LOG schreiben.
    Für Autotest-Analyse: tail -f /var/log/pidrive/avrcp_raw.log
    """
    try:
        ts = time.strftime("%H:%M:%S")
        with open(AVRCP_RAW_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        pass


def _sep(label: str = ""):
    """Trennlinie im Log für bessere Lesbarkeit."""
    if label:
        log.info(f"AVRCP ── {label} {'─' * max(0, 60 - len(label))}")
    else:
        log.info("AVRCP " + "─" * 64)


# ── IPC ──────────────────────────────────────────────────────────────────────

def read_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_debug(data: dict):
    try:
        tmp = AVRCP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, AVRCP_FILE)
    except Exception:
        pass


def write_cmd(cmd: str):
    global _last_trigger, _event_count
    t_write_start = time.time()
    try:
        with open(CMD_FILE, "w", encoding="utf-8") as f:
            f.write(cmd.strip() + "\n")
        dt_ms = int((time.time() - t_write_start) * 1000)
        with _lock:
            _last_trigger = cmd
            _event_count += 1
            cnt = _event_count
        log.info(f"AVRCP → trigger={cmd!r}  write={dt_ms}ms  count=#{cnt}")
        _raw_log(f"TRIGGER: {cmd}")
    except Exception as e:
        log.error(f"AVRCP write_cmd {cmd!r}: {e}")


# ── Kontext ───────────────────────────────────────────────────────────────────

def get_context() -> dict:
    status = read_json(STATUS_FILE, {})
    menu   = read_json(MENU_FILE,   {})
    lst    = read_json(LIST_FILE,   {})

    if lst.get("active"):
        return {"context": "list_overlay",
                "status": status, "menu": menu, "list": lst, "band": ""}

    radio_on   = bool(status.get("radio", False))
    radio_type = (status.get("radio_type", "") or "").upper()

    if radio_on and radio_type == "SCANNER":
        band = ""
        path = menu.get("path", [])
        if path:
            low_path = " / ".join(str(x).lower() for x in path)
            for cand in ("pmr446", "freenet", "lpd433", "cb", "vhf", "uhf"):
                if cand in low_path:
                    band = cand
                    break
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
        return {"context": "scanner",
                "status": status, "menu": menu, "list": lst, "band": band}

    if radio_on:
        return {"context": "radio",
                "status": status, "menu": menu, "list": lst, "band": ""}

    return {"context": "menu",
            "status": status, "menu": menu, "list": lst, "band": ""}


# ── Event-Mapping ─────────────────────────────────────────────────────────────

def map_event(event: str, ctx: dict) -> str | None:
    context    = ctx.get("context", "menu")
    status     = ctx.get("status", {})
    band       = ctx.get("band", "")
    radio_type = (status.get("radio_type", "") or "").upper()

    if event in ("volumeup",   "volume_up"):   return "vol_up"
    if event in ("volumedown", "volume_down"): return "vol_down"

    if context == "list_overlay":
        return {
            "next": "down",  "previous": "up",
            "play": "enter", "pause": "enter", "play_pause": "enter",
            "stop": "back",
            "fast_forward": "down", "rewind": "up",
        }.get(event)

    if context == "scanner":
        if band in ("vhf", "uhf"):
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
            jump = 10 if band == "cb" else 1
            return {
                "next":         f"scan_up:{band}"           if band else "down",
                "previous":     f"scan_down:{band}"         if band else "up",
                "fast_forward": f"scan_jump:{band}:{jump}"  if band else "down",
                "rewind":       f"scan_jump:{band}:-{jump}" if band else "up",
                "play":         f"scan_next:{band}"         if band else "enter",
                "pause":        f"scan_next:{band}"         if band else "enter",
                "play_pause":   f"scan_next:{band}"         if band else "enter",
                "stop":         "back",
            }.get(event)

    if context == "radio":
        if radio_type == "FM":
            return {
                "next": "fm_next",  "previous": "fm_prev",
                "fast_forward": "fm_next", "rewind": "fm_prev",
                "play": "radio_stop", "pause": "radio_stop",
                "play_pause": "radio_stop", "stop": "back",
            }.get(event)
        if radio_type == "DAB":
            return {
                "next": "dab_next", "previous": "dab_prev",
                "fast_forward": "dab_next", "rewind": "dab_prev",
                "play": "radio_stop", "pause": "radio_stop",
                "play_pause": "radio_stop", "stop": "back",
            }.get(event)
        return {
            "next": "down",  "previous": "up",
            "play": "radio_stop", "pause": "radio_stop",
            "play_pause": "radio_stop", "stop": "back",
            "fast_forward": "down", "rewind": "up",
        }.get(event)

    # Menü
    return {
        "next": "down",  "previous": "up",
        "play": "enter", "pause": "enter", "play_pause": "enter",
        "stop": "back",
        "fast_forward": "down", "rewind": "up",
    }.get(event)


# ── Haupt-Handler ─────────────────────────────────────────────────────────────

def handle_avrcp(event: str, source: str = "unknown", raw_line: str = ""):
    """
    v0.10.20: Verarbeit ein AVRCP-Event mit vollständigem Verbose-Logging.
    raw_line: die originale D-Bus / bluetoothctl Zeile (für Diagnose)
    """
    global _last_enter_time, _last_event_ts, _last_event_name
    global _last_context, _last_source

    event = event.strip().lower()
    if not event:
        return

    if not os.path.exists(READY_FILE):
        log.warn(f"AVRCP event={event!r} src={source} — PiDrive NICHT bereit (kein {READY_FILE})")
        return

    t0 = time.time()

    # ── Kontext lesen ────────────────────────────────────────────────────
    ctx          = get_context()
    context_name = ctx.get("context", "menu")
    radio_type   = (ctx["status"].get("radio_type", "") or "").upper()
    radio_name   = ctx["status"].get("radio_name", "") or ctx["status"].get("radio_station", "")
    band         = ctx.get("band", "")
    menu_path    = ctx["menu"].get("path", [])
    list_active  = ctx["list"].get("active", False)
    source_curr  = ctx["status"].get("source_current", "?")

    _last_event_ts   = t0
    _last_event_name = event
    _last_context    = context_name
    _last_source     = source

    # ── Verbose-Log ──────────────────────────────────────────────────────
    _sep(f"event={event!r}  src={source}")
    log.info(f"AVRCP    Event:   {event!r}  von {source}")
    log.info(f"AVRCP    Kontext: {context_name}  |  Quelle: {source_curr}  |  Typ: {radio_type or '–'}")
    if radio_name:
        log.info(f"AVRCP    Radio:   {radio_name}")
    if band:
        log.info(f"AVRCP    Band:    {band}")
    if menu_path:
        log.info(f"AVRCP    Pfad:    {' › '.join(str(p) for p in menu_path)}")
    if list_active:
        log.info(f"AVRCP    Liste:   aktiv (modal)")
    if raw_line:
        log.info(f"AVRCP    Raw:     {raw_line[:120]}")
        _raw_log(f"EVENT: {event!r} src={source} raw={raw_line[:120]}")

    # ── Doppelklick Play/Pause → direkt "Jetzt läuft" ───────────────────
    if event in ("play", "pause", "play_pause"):
        if t0 - _last_enter_time < DOUBLE_TAP_SEC:
            dt_tap = round(t0 - _last_enter_time, 2)
            log.info(f"AVRCP    Double-tap ({dt_tap}s) → cat:0 (Jetzt läuft)")
            write_cmd("cat:0")
            _last_enter_time = 0.0
            _write_debug_full(event, "cat:0", context_name, source, ctx, t0)
            return
        _last_enter_time = t0

    # ── Event → Trigger ───────────────────────────────────────────────────
    trigger = map_event(event, ctx)
    dt_ctx_ms = int((time.time() - t0) * 1000)

    if trigger:
        log.info(f"AVRCP    Mapping: {event!r} → {context_name} → {trigger!r}  [{dt_ctx_ms}ms]")
        write_cmd(trigger)
    else:
        log.info(f"AVRCP    Mapping: {event!r} → {context_name} → (ignoriert)  [{dt_ctx_ms}ms]")
        log.info(f"AVRCP    HINWEIS: Kein Mapping für diesen Event/Kontext")

    _write_debug_full(event, trigger or "", context_name, source, ctx, t0)


def _write_debug_full(event, trigger, context_name, source, ctx, t0):
    """Vollständiges Debug-JSON schreiben."""
    write_debug({
        "ts":          t0,
        "ts_human":    time.strftime("%H:%M:%S", time.localtime(t0)),
        "last_event":  event,
        "context":     context_name,
        "trigger":     trigger,
        "source":      source,
        "event_count": _event_count,
        "ctx": {
            "radio_type":   ctx["status"].get("radio_type", ""),
            "radio":        ctx["status"].get("radio", False),
            "radio_name":   ctx["status"].get("radio_name", ""),
            "source_current": ctx["status"].get("source_current", ""),
            "band":         ctx.get("band", ""),
            "menu_path":    ctx["menu"].get("path", []),
            "list_active":  ctx["list"].get("active", False),
        }
    })


# ── Monitor: bluetoothctl ─────────────────────────────────────────────────────

def parse_bluetoothctl_line(line: str) -> str | None:
    line_l = line.lower()
    if "avrcp" in line_l or "player" in line_l:
        for keyword in ("next", "previous", "play_pause", "play", "pause", "stop",
                        "fast_forward", "rewind", "volumeup", "volumedown"):
            if keyword in line_l:
                return keyword
    return None


def monitor_bluetoothctl():
    """
    v0.10.20: bluetoothctl monitor mit vollständigem Raw-Logging.
    Jede Zeile → Raw-Log, nur gematchte → handle_avrcp.
    """
    log.info("AVRCP: bluetoothctl monitor gestartet")
    _raw_log("=== bluetoothctl monitor START ===")
    heartbeat_ts = time.time()

    while True:
        try:
            proc = subprocess.Popen(
                ["bluetoothctl", "monitor"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1)

            for line in proc.stdout:
                raw = line.strip()
                if not raw:
                    continue

                # v0.10.20: Heartbeat alle 60s
                now = time.time()
                if now - heartbeat_ts > 60:
                    log.info(f"AVRCP heartbeat: bluetoothctl-thread läuft, events={_event_count}")
                    heartbeat_ts = now

                # Alle AVRCP/Player-Zeilen im Raw-Log
                low = raw.lower()
                if any(k in low for k in ("avrcp", "player", "media", "next", "previous",
                                           "play", "pause", "stop", "rewind", "forward")):
                    _raw_log(f"BTCTL: {raw}")
                    log.info(f"AVRCP btctl-raw: {raw[:120]}")

                event = parse_bluetoothctl_line(raw)
                if event:
                    handle_avrcp(event, source="bluetoothctl", raw_line=raw)

        except Exception as e:
            log.error(f"AVRCP bluetoothctl-monitor: {e}")
            _raw_log(f"ERROR bluetoothctl: {e}")
            time.sleep(5)


# ── Monitor: dbus-monitor ─────────────────────────────────────────────────────

# Alle relevanten AVRCP-Methoden und D-Bus-Signale die BMW senden kann
_AVRCP_METHODS = {
    "next":         "next",
    "previous":     "previous",
    "playpause":    "play_pause",
    "play":         "play",
    "pause":        "pause",
    "stop":         "stop",
    "fastforward":  "fast_forward",
    "rewind":       "rewind",
    "volumeup":     "volumeup",
    "volumedown":   "volumedown",
    "seek":         None,  # wird geloggt aber nicht gemappt
    "setposition":  None,
    "openuri":      None,
}

# BMW NBT EVO AVRCP-spezifische D-Bus-Pfade
_BMW_PATTERNS = [
    "org.mpris.MediaPlayer2",
    "org.bluez.MediaPlayer1",
    "org.bluez.MediaControl1",
    "AVRCP",
    "PassThrough",
    "bluez",
]


def _parse_dbus_line(line: str) -> tuple[str | None, str]:
    """
    v0.10.20: D-Bus Zeile auf AVRCP-Events parsen.
    Gibt (event_name_oder_None, erkannter_typ) zurück.
    Erkennt sowohl Methoden-Aufrufe als auch Property-Changes.
    """
    line_l = line.lower()

    # Direkter Method-Call: "member=Next", "member=Previous" etc.
    m = re.search(r'member=([A-Za-z]+)', line)
    if m:
        member = m.group(1).lower()
        if member in _AVRCP_METHODS:
            return _AVRCP_METHODS[member], f"member={m.group(1)}"

    # String-Matching für BMW-spezifische Varianten
    for method, event in [
        ('"Next"',       "next"),       ("'Next'",       "next"),
        ('"Previous"',   "previous"),   ("'Previous'",   "previous"),
        ('"PlayPause"',  "play_pause"), ("'PlayPause'",  "play_pause"),
        ('"Play"',       "play"),       ("'Play'",       "play"),
        ('"Pause"',      "pause"),      ("'Pause'",      "pause"),
        ('"Stop"',       "stop"),       ("'Stop'",       "stop"),
        ('"FastForward"',"fast_forward"),("'FastForward'","fast_forward"),
        ('"Rewind"',     "rewind"),     ("'Rewind'",     "rewind"),
    ]:
        if method in line:
            return event, f"string-match:{method}"

    # PlaybackStatus Property-Change (BMW meldet Pause/Play zurück)
    if "playbackstatus" in line_l:
        if '"playing"' in line_l or "'playing'" in line_l:
            return "play", "PlaybackStatus=Playing"
        if '"paused"' in line_l or "'paused'" in line_l:
            return "pause", "PlaybackStatus=Paused"
        if '"stopped"' in line_l or "'stopped'" in line_l:
            return "stop", "PlaybackStatus=Stopped"

    return None, ""


def monitor_dbus():
    """
    v0.10.20: dbus-monitor mit vollständigem Raw-Logging und erweiterter Erkennung.
    Loggt ALLE relevanten D-Bus-Zeilen, nicht nur gematchte.
    """
    log.info("AVRCP: dbus-monitor gestartet (interface=org.mpris.MediaPlayer2.Player)")
    _raw_log("=== dbus-monitor START ===")
    heartbeat_ts = time.time()

    # Puffer für zusammengehörige D-Bus-Nachrichten
    current_msg_lines: list = []
    current_msg_has_method = False

    while True:
        try:
            proc = subprocess.Popen(
                ["dbus-monitor",
                 "--system",
                 "interface=org.mpris.MediaPlayer2.Player",
                 "interface=org.bluez.MediaPlayer1",
                 "interface=org.bluez.MediaControl1"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1)

            log.info("AVRCP: dbus-monitor PID=" + str(proc.pid) + " gestartet")
            _raw_log(f"dbus-monitor PID={proc.pid}")

            for line in proc.stdout:
                raw = line.rstrip()
                if not raw:
                    continue

                now = time.time()
                if now - heartbeat_ts > 60:
                    log.info(f"AVRCP heartbeat: dbus-thread läuft, events={_event_count}")
                    heartbeat_ts = now

                # Raw-Log: alle Zeilen die AVRCP-relevant sein könnten
                low = raw.lower()
                is_relevant = any(p.lower() in low for p in _BMW_PATTERNS) or \
                              any(m in low for m in ("next", "previous", "play", "pause",
                                                      "stop", "rewind", "forward", "member="))
                if is_relevant:
                    _raw_log(f"DBUS: {raw}")

                # Event parsen
                event, match_type = _parse_dbus_line(raw)
                if event:
                    log.info(f"AVRCP dbus-match: {match_type!r} → event={event!r}  raw={raw[:80]}")
                    handle_avrcp(event, source="dbus-monitor", raw_line=raw)
                elif is_relevant and "member=" in low:
                    # Nicht-gematchter Member-Call → für BMW-Analyse loggen
                    log.info(f"AVRCP dbus-unmatched: {raw[:100]}")

            # Prozess beendet — stderr lesen für Fehleranalyse
            try:
                err = proc.stderr.read(500)
                if err:
                    log.warn(f"AVRCP dbus-monitor stderr: {err.strip()[:200]}")
                    _raw_log(f"dbus-monitor STDERR: {err.strip()[:200]}")
            except Exception:
                pass

        except Exception as e:
            log.error(f"AVRCP dbus-monitor: {e}")
            _raw_log(f"ERROR dbus-monitor: {e}")
            time.sleep(5)


# ── Auto-Connect ──────────────────────────────────────────────────────────────

def auto_connect_bmw():
    """Gepairte Geräte beim Start verbinden."""
    try:
        r = subprocess.run(
            "bluetoothctl devices Paired 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5)
        devices = []
        for line in r.stdout.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) >= 2:
                mac  = parts[1]
                name = parts[2] if len(parts) > 2 else mac
                devices.append((mac, name))
        if devices:
            log.info(f"AVRCP auto-connect: {len(devices)} gepairte Gerät(e)")
            for mac, name in devices:
                log.info(f"AVRCP auto-connect: verbinde {name!r} ({mac})")
                subprocess.Popen(
                    f"bluetoothctl connect {mac}",
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
        else:
            log.info("AVRCP auto-connect: keine gepairten Geräte")
    except Exception as e:
        log.error(f"AVRCP auto_connect: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.setup("core")
    _sep("PiDrive AVRCP v0.10.20 gestartet")
    log.info("AVRCP   Kontextbasiertes Mapping aktiv")
    log.info("AVRCP   Kontexte: menu / radio / scanner / list_overlay")
    log.info("AVRCP   Raw-Log:  " + AVRCP_RAW_LOG)
    log.info("AVRCP   Threads:  bluetoothctl-monitor + dbus-monitor")
    _sep()

    # Raw-Log initialisieren
    try:
        os.makedirs(os.path.dirname(AVRCP_RAW_LOG), exist_ok=True)
        _raw_log(f"=== AVRCP v0.10.20 Start {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    except Exception:
        pass

    # Debug-JSON sofort initialisieren
    write_debug({
        "ts":         time.time(),
        "last_event": "",
        "context":    "startup",
        "trigger":    "",
        "source":     "service_start",
        "event_count": 0,
        "ctx": {
            "radio_type":  "",
            "radio":       False,
            "band":        "",
            "menu_path":   [],
            "list_active": False,
        }
    })

    signal.signal(signal.SIGHUP,  signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    auto_connect_bmw()

    t1 = threading.Thread(target=monitor_bluetoothctl, daemon=True, name="btctl-monitor")
    t2 = threading.Thread(target=monitor_dbus,         daemon=True, name="dbus-monitor")
    t1.start()
    t2.start()

    log.info("AVRCP: Warte auf Events ...")
    log.info(f"AVRCP: Autotest-Analyse: tail -f {AVRCP_RAW_LOG}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
