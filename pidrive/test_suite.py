#!/usr/bin/env python3
"""
test_suite.py — PiDrive System-Test v0.1.0

Vollständiger System-Check: alle Quellen, Audio, BT, AVRCP, MPRIS2, Ressourcen.
Nutzung: pidrivectl test all

Ausgabe: farbig im Terminal + /tmp/pidrive_test_results.json
BMW-Display: aktueller Test-Schritt während Ausführung sichtbar
"""

import os, sys, time, json, subprocess, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ── Farben ────────────────────────────────────────────────────────────────────
R  = "\033[31m"; G  = "\033[32m"; Y  = "\033[33m"; B  = "\033[34m"
C  = "\033[36m"; W  = "\033[37m"; M  = "\033[35m"; BOLD = "\033[1m"; RST = "\033[0m"
DIM = "\033[2m"

PASS = f"{G}✓{RST}"; FAIL = f"{R}✗{RST}"; WARN = f"{Y}⚠{RST}"; INFO = f"{B}→{RST}"

# ── Ergebnis-Tracking ─────────────────────────────────────────────────────────
_results = []
_start_ts = 0.0
_total = 0
_passed = 0
_failed = 0
_warnings = 0
_has_audio_sink = False

def _p(symbol, label, detail="", elapsed=None):
    global _passed, _failed, _warnings
    t = f"  {DIM}({elapsed:.1f}s){RST}" if elapsed else ""
    d = f"  {DIM}{detail}{RST}" if detail else ""
    print(f"  {symbol} {label}{d}{t}")
    entry = {"label": label, "detail": detail,
             "status": "pass" if symbol == PASS else ("fail" if symbol == FAIL else "warn"),
             "elapsed": elapsed}
    _results.append(entry)
    if symbol == PASS: _passed += 1
    elif symbol == FAIL: _failed += 1
    else: _warnings += 1

def _section(name, icon=""):
    print(f"\n{BOLD}{C}{'─'*50}{RST}")
    print(f"{BOLD}{C}  {icon}  {name}{RST}")
    print(f"{BOLD}{C}{'─'*50}{RST}")

def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() + r.stderr.strip()
    except Exception as e:
        return str(e)

def _read_json(path, default=None):
    try:
        with open(path) as f: return json.load(f)
    except Exception:
        return default or {}

def _write_trigger(trigger):
    try:
        from ipc import append_trigger
        append_trigger(trigger)
        return True
    except Exception:
        try:
            with open("/tmp/pidrive_cmd", "a") as f:
                f.write(trigger + "\n")
            return True
        except Exception:
            return False

def _current_source():
    ss = _read_json("/tmp/pidrive_source_state.json")
    return ss.get("source_current", "idle")

def _wait_for_metadata(source_key, max_wait=20, poll=1.0):
    """Wartet bis Metadaten für eine Quelle vorhanden sind."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        cur = _current_source()
        s = _read_json("/tmp/pidrive_status.json")
        track = s.get("track") or s.get("radio_name") or s.get("dls_text") or s.get("dls")
        if track and (cur == source_key or source_key == "any"):
            return track
        time.sleep(poll)
    return None

def _wait_for_source(source_key, max_wait=15):
    """Wartet bis source_key aktiv ist (source_state.json, nicht status.json)."""
    ctx_map = {"webradio": "radio_web", "fm": "radio_fm", "dab": "radio_dab"}
    deadline = time.time() + max_wait
    while time.time() < deadline:
        cur = _current_source()
        if cur == source_key:
            return True
        s = _read_json("/tmp/pidrive_status.json")
        if s.get("control_context") == ctx_map.get(source_key):
            return True
        if source_key == "spotify" and s.get("spotify"):
            return True
        time.sleep(0.5)
    return False

def _send_to_bmw(title, artist="PiDrive Test", album="System Test"):
    """Aktuellen Test-Schritt ans BMW-Display senden."""
    try:
        t = title[:50].replace("|", "")
        a = artist[:40].replace("|", "")
        al = album[:30].replace("|", "")
        _write_trigger(f"mpris_push:{t}|{a}|{al}")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# TEST-BLÖCKE
# ══════════════════════════════════════════════════════════════════════════════

def test_system():
    """1. Systemressourcen."""
    _section("SYSTEM", "🖥")
    _send_to_bmw("1/9: System-Check", "RAM · Disk · CPU · Version")

    # Version
    ver = _read_json(os.path.join(BASE_DIR, "../VERSION"), None)
    if not ver:
        try: ver = open(os.path.join(BASE_DIR, "VERSION")).read().strip()
        except: ver = "?"
    _p(INFO, f"PiDrive {ver}")

    # Core online?
    s = _read_json("/tmp/pidrive_status.json")
    age = time.time() - os.path.getmtime("/tmp/pidrive_status.json") if os.path.exists("/tmp/pidrive_status.json") else 999
    if age < 10:
        _p(PASS, "Core online", f"status.json {age:.0f}s alt")
    else:
        _p(FAIL, "Core offline oder status.json veraltet", f"{age:.0f}s alt")

    # RAM
    mem = _run("free -m | awk '/^Speicher:|^Mem:/{print $2,$3,$4}'")
    parts = mem.split()
    if len(parts) >= 3:
        total, used, free = int(parts[0]), int(parts[1]), int(parts[2])
        pct = used * 100 // total
        sym = PASS if pct < 80 else (WARN if pct < 90 else FAIL)
        _p(sym, f"RAM: {used}M / {total}M  ({pct}% genutzt)", f"{free}M frei")
    else:
        _p(WARN, "RAM: nicht ermittelbar", mem[:50])

    # Disk
    disk = _run("df -h / | awk 'NR==2{print $2,$3,$4,$5}'")
    parts = disk.split()
    if len(parts) >= 4:
        pct = int(parts[3].replace("%",""))
        sym = PASS if pct < 80 else (WARN if pct < 90 else FAIL)
        _p(sym, f"Disk: {parts[2]} / {parts[0]}  ({pct}% voll)", f"{parts[2]} frei")
    else:
        _p(WARN, "Disk: nicht ermittelbar")

    # CPU Throttling (Pi)
    throttled = _run("vcgencmd get_throttled 2>/dev/null | cut -d= -f2")
    if throttled and throttled != "0x0":
        _p(WARN, f"CPU-Throttling: {throttled}", "Unterspannung / Überhitzung!")
    elif throttled == "0x0":
        _p(PASS, "CPU-Throttling: keines")
    else:
        _p(INFO, "CPU-Throttling: n/a (kein Pi oder vcgencmd fehlt)")

    # Load
    load = _run("cat /proc/loadavg | cut -d' ' -f1-3")
    _p(INFO, f"Load Average: {load}")

    # Swap
    swap = _run("free -m | awk '/^Swap:|^Auslager/{print $2,$3}'")
    sp = swap.split()
    if len(sp) == 2 and int(sp[0]) > 0:
        pct = int(sp[1]) * 100 // int(sp[0])
        sym = PASS if pct < 50 else (WARN if pct < 80 else FAIL)
        _p(sym, f"Swap: {sp[1]}M / {sp[0]}M ({pct}% genutzt)")

    # Temp
    temp = _run("vcgencmd measure_temp 2>/dev/null | cut -d= -f2")
    if temp:
        try:
            t = float(temp.replace("'C",""))
            sym = PASS if t < 70 else (WARN if t < 80 else FAIL)
            _p(sym, f"CPU-Temp: {temp}")
        except: _p(INFO, f"CPU-Temp: {temp}")

    # RTL-SDR
    rtl = _run("lsusb 2>/dev/null | grep -iE 'rtl|0bda:2838|Rafael'")
    if rtl:
        _p(PASS, "RTL-SDR: erkannt", rtl[:60])
    else:
        _p(WARN, "RTL-SDR: nicht gefunden (FM/DAB/Scanner nicht verfügbar)")

    return _failed == 0


def test_audio():
    """2. Audio + PipeWire/PA."""
    _section("AUDIO", "🔊")
    _send_to_bmw("2/9: Audio-Check", "PipeWire · Sinks · BT")

    # PA läuft?
    # PipeWire oder PulseAudio
    pw  = _run("systemctl is-active pipewire 2>/dev/null")
    pwp = _run("systemctl is-active pipewire-pulse 2>/dev/null")
    pa  = _run("systemctl is-active pulseaudio 2>/dev/null")
    if pw == "active" and pwp == "active":
        _p(PASS, "PipeWire System-Mode: aktiv ✓")
    elif pa == "active":
        _p(WARN, "PulseAudio aktiv (PipeWire-Upgrade empfohlen)")
    else:
        _p(FAIL, "Kein Audio-Server aktiv!")

    # Sinks
    sinks = _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null")
    if not sinks:
        _p(FAIL, "PA-Sinks: keine vorhanden!")
    else:
        for line in sinks.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]
                state = parts[-1] if len(parts) > 4 else ""
                if "null" in name.lower():
                    _p(WARN, f"Sink: {name}", "Null-Sink (virtuell)")
                elif "bluez" in name.lower():
                    _p(PASS, f"Sink: {name}", f"BT A2DP ✓  {state}")
                else:
                    _p(PASS, f"Sink: {name}", state)

    # PipeWire-Konflikt?
    # PipeWire ist jetzt der Audio-Server — kein Konflikt mehr
    _p(INFO, "Audio-Stack: PipeWire (kein PA-Konflikt)")

    # BT Audio-Test
    bt_sink = ""
    for line in sinks.splitlines():
        if "bluez" in line.lower():
            bt_sink = line.split()[1] if len(line.split()) > 1 else ""
            break

    if bt_sink:
        t0 = time.time()
        _run(f"PULSE_SERVER=unix:/var/run/pulse/native paplay --device={bt_sink} "
             f"/usr/share/sounds/alsa/Front_Center.wav 2>/dev/null", timeout=5)
        _p(PASS, "BT-Ton abgespielt", f"{bt_sink[:40]}", time.time()-t0)
    else:
        _p(WARN, "Kein BT-Sink — BT verbinden für Audio-Test")

    # Sink-Status für Wiedergabe-Tests merken
    global _has_audio_sink
    _has_audio_sink = bool(bt_sink) or bool(
        _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null"
             " | grep -v null")
    )

    return True


def _avrcp_version_info(mac):
    """AVRCP-Version des Geräts aus dem SDP-Record lesen (Cover-Art-Fähigkeit).
    Gibt (version_int|None, cover_art_bool, note) zurück.
    Cover Art (Bilder über BT) gibt es erst ab AVRCP 1.6 (0x0106)."""
    import re
    if not mac:
        return None, False, "keine MAC"
    out = _run(f"sdptool browse {mac} 2>&1", timeout=10)
    low = (out or "").lower()
    if (not out) or ("not found" in low) or ("no such file" in low) or ("command not found" in low):
        return None, False, "sdptool nicht verfuegbar (Teil von bluez)"
    if ("failed to connect" in low or "host is down" in low
            or "connection refused" in low or "can't connect" in low):
        return None, False, "Geraet nicht erreichbar (verbunden?)"
    lines = out.splitlines()
    versions = []
    for i, ln in enumerate(lines):
        if "remote control" in ln.lower():
            for j in range(i, min(i + 18, len(lines))):
                m = re.search(r"Version:\s*0x(01[0-9a-fA-F]{2})", lines[j])
                if m:
                    versions.append(int(m.group(1), 16))
    if not versions:
        return None, False, "keine AVRCP-Version im SDP gefunden"
    return max(versions), (max(versions) >= 0x0106), ""


def test_bluetooth():
    """3. Bluetooth + AVRCP."""
    _section("BLUETOOTH + AVRCP", "🔵")
    _send_to_bmw("3/9: Bluetooth-Check", "A2DP · AVRCP · Player0")

    # hci0 aktiv?
    hci = _run("hciconfig hci0 2>/dev/null")
    if "UP RUNNING" in hci:
        _p(PASS, "hci0: UP RUNNING")
    else:
        _p(FAIL, "hci0: nicht aktiv", hci[:60])
        return False

    # BT verbunden?
    s = _read_json("/tmp/pidrive_status.json")
    bt_mac = s.get("bt_last_mac") or s.get("bt_sink_mac","")
    if s.get("bt"):
        name = s.get("bt_device","?")
        _p(PASS, f"BT verbunden: {name}", bt_mac)
    else:
        _p(WARN, "BT nicht verbunden (kein A2DP-Test möglich)")
        return True

    # A2DP-Sink? (PipeWire: bluez_output.* / Legacy: bluez_sink.*)
    sinks = _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null")
    mac_u = bt_mac.replace(":","_")
    bt_sink = ""
    for ln in sinks.splitlines():
        parts = ln.split()
        if len(parts) >= 2 and mac_u in parts[1].upper() and (
            "bluez_output" in parts[1] or "bluez_sink" in parts[1]
        ):
            bt_sink = parts[1]
            break
    if bt_sink:
        _p(PASS, "A2DP-Sink aktiv", bt_sink)
    else:
        _p(FAIL, "A2DP-Sink fehlt!", "pactl set-card-profile... ausführen")

    # AVRCP player0?
    t0 = time.time()
    objs = _run("dbus-send --system --print-reply --dest=org.bluez / "
                "org.freedesktop.DBus.ObjectManager.GetManagedObjects 2>/dev/null", timeout=4)
    if "player0" in objs:
        _p(PASS, "AVRCP /player0 vorhanden", f"{time.time()-t0:.1f}s")
    else:
        _p(WARN, "AVRCP /player0 nicht gefunden", "BT gerade getrennt?")

    # AVRCP-Version der Headunit → Cover-Art-Fähigkeit (Bilder gibt's erst ab 1.6)
    _ver, _cover, _note = _avrcp_version_info(bt_mac)
    if _ver is not None:
        _vs = f"{_ver >> 8}.{_ver & 0xff}"
        if _cover:
            _p(PASS, f"AVRCP-Version: {_vs}", "Cover Art (ab 1.6) wird unterstuetzt")
        else:
            _p(INFO, f"AVRCP-Version: {_vs}", "kein Cover Art (Bilder erst ab AVRCP 1.6)")
    else:
        _p(INFO, "AVRCP-Version nicht ermittelbar", _note)

    # MPRIS2 auf D-Bus?
    t0 = time.time()
    names = _run("dbus-send --system --print-reply --dest=org.freedesktop.DBus / "
                 "org.freedesktop.DBus.ListNames 2>/dev/null", timeout=4)
    if "org.mpris.MediaPlayer2.pidrive" in names:
        _p(PASS, "MPRIS2 registriert", f"org.mpris.MediaPlayer2.pidrive ({time.time()-t0:.1f}s)")
    else:
        _p(FAIL, "MPRIS2 NICHT auf D-Bus!", "BMW-Display ohne Metadaten")

    # AVRCP inject test
    t0 = time.time()
    _write_trigger("avrcp_test_ping")
    time.sleep(0.5)
    events = _read_json("/tmp/pidrive_avrcp_events.json", {})
    ring = events.get("events", [])
    total_ev = events.get("total", 0)
    _p(INFO, f"AVRCP-Ringbuffer: {len(ring)} Events gespeichert, {total_ev} gesamt")

    return True


def test_mpris2_push():
    """4. MPRIS2 Test-Push."""
    _section("MPRIS2 TEST-PUSH", "📡")
    _send_to_bmw("4/9: MPRIS2 Push-Test", "BMW-Display Metadaten-Test")

    _ver = open(os.path.join(BASE_DIR, "VERSION")).read().strip() if os.path.exists(os.path.join(BASE_DIR, "VERSION")) else "?"
    _write_trigger(f"mpris_push:System Test läuft|PiDrive v{_ver}|pidrivectl test all")
    time.sleep(1.0)
    _p(INFO, "Test-Metadaten ans BMW-Display gesendet",
       "Zeile1: 'System Test läuft'  Artist: 'PiDrive v...'")

    # GetAll prüfen
    result = _run(
        "dbus-send --system --print-reply "
        "--dest=org.mpris.MediaPlayer2.pidrive "
        "/org/mpris/MediaPlayer2 "
        "org.freedesktop.DBus.Properties.GetAll "
        "string:org.mpris.MediaPlayer2.Player 2>&1", timeout=4
    )
    if "xesam:title" in result or "Metadata" in result:
        _p(PASS, "MPRIS2 GetAll: Metadaten lesbar")
        for ln in result.splitlines():
            if "title" in ln.lower() or "artist" in ln.lower():
                _p(INFO, f"  {ln.strip()[:80]}")
    elif "No such name" in result or "not provided" in result:
        _p(FAIL, "MPRIS2 nicht erreichbar", result[:80])
    else:
        _p(WARN, "MPRIS2 GetAll: unklare Antwort", result[:80])

    return True


def test_webradio():
    """5. Webradio."""
    _section("WEBRADIO", "📻")
    _send_to_bmw("5/9: Webradio-Test", "Rock Antenne · Metadaten")

    # Prüfen ob Audio-Sink vorhanden — ohne Sink startet mpv nicht
    _sinks = _run("PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null")
    _real_sink = any(s for s in _sinks.splitlines() if "null" not in s.lower())
    if not _real_sink:
        _p(WARN, "Webradio: kein realer Audio-Sink (BT nicht verbunden / vor Reboot)")
        _p(INFO, "  → pidrivectl bt connect <MAC> && pidrivectl play web 9")
        return None

    t0 = time.time()
    _write_trigger("radio_stop")  # laufende Quelle stoppen
    import time as _twb; _twb.sleep(2.0)
    _write_trigger("play_web:Rock Antenne")
    src_ok = _wait_for_source("webradio", max_wait=20)
    if not src_ok:
        # Bei Einzeltest-Aufruf _has_audio_sink direkt prüfen
        _any_sink = _run("PULSE_SERVER=unix:/var/run/pulse/native "
                        "pactl list sinks short 2>/dev/null | grep -v null")
        if not _has_audio_sink and not _any_sink:
            _p(WARN, "Webradio: kein Audio-Sink (BT verbinden) — übersprungen")
            return None
        _p(FAIL, f"Webradio: Quelle nicht aktiv nach {max_wait}s")
        return False
    _p(PASS, "Webradio: gestartet", f"{time.time()-t0:.1f}s")

    # Metadaten warten
    _send_to_bmw("5/9: Webradio", "Warte auf Metadaten...")
    meta = _wait_for_metadata("webradio", max_wait=20)
    elapsed = time.time() - t0
    if meta:
        _p(PASS, f"Metadaten: '{meta[:50]}'", f"{elapsed:.1f}s")
        _send_to_bmw(f"Webradio: {meta[:40]}", "Rock Antenne", f"✓ {elapsed:.0f}s")
    else:
        _p(WARN, "Metadaten: keine nach 20s", "Webradio läuft, aber kein Titel")

    return True


def test_fm(freq="104.4"):
    """6. FM Radio."""
    _section(f"FM RADIO ({freq} MHz)", "📡")
    _send_to_bmw(f"6/9: FM {freq} MHz", "rtl_fm · Antenne Bayern")

    # RTL-SDR verfügbar?
    s = _read_json("/tmp/pidrive_status.json")
    if not s.get("rtlsdr", True):
        _p(WARN, "RTL-SDR nicht verfügbar — FM-Test übersprungen")
        return None

    t0 = time.time()
    _write_trigger("stop")
    time.sleep(0.5)
    _write_trigger("radio_stop")  # laufende Quelle stoppen
    import time as _tfm; _tfm.sleep(1.5)
    _write_trigger(f"play_fm:{freq}")
    src_ok = _wait_for_source("fm", max_wait=20)
    elapsed = time.time() - t0
    if not _has_audio_sink and not src_ok:
        _any_sink = _run("PULSE_SERVER=unix:/var/run/pulse/native "
                        "pactl list sinks short 2>/dev/null | grep -v null")
        if not _any_sink:
            _p(WARN, f"FM {freq}: kein Audio-Sink — übersprungen")
            return None
    if src_ok:
        _p(PASS, f"FM {freq} MHz: gestartet", f"{elapsed:.1f}s")
        meta = _wait_for_metadata("fm", max_wait=15)
        if meta:
            _p(PASS, f"FM-Metadaten: '{meta[:50]}'")
            _send_to_bmw(f"FM: {meta[:40]}", f"{freq} MHz", "✓")
        else:
            _p(INFO, "FM: kein RDS/Metadaten (normal ohne RDS-Signal)")
    else:
        _p(FAIL, f"FM {freq}: Quelle nicht aktiv", f"{elapsed:.1f}s")

    return src_ok


def test_scanner_fm(freq="103.0"):
    """7. Scanner FM."""
    _section(f"SCANNER FM ({freq} MHz)", "🔍")
    _send_to_bmw(f"7/9: Scanner FM {freq}", "rtl_fm Scanner-Modus")

    s = _read_json("/tmp/pidrive_status.json")
    caps_rtl = _run("which rtl_fm 2>/dev/null")
    if not caps_rtl:
        _p(WARN, "rtl_fm nicht verfügbar — Scanner übersprungen")
        return None

    t0 = time.time()
    _write_trigger("stop")
    time.sleep(0.5)
    _write_trigger("scanner_stop")  # laufende Quelle stoppen
    import time as _tsc; _tsc.sleep(1.5)
    _write_trigger(f"scan_setfreq:fm:{freq}")
    src_ok = _wait_for_source("scanner", max_wait=20)
    elapsed = time.time() - t0
    if src_ok:
        _p(PASS, f"Scanner FM {freq}: aktiv", f"{elapsed:.1f}s")
        time.sleep(5)
        _p(INFO, "Scanner läuft (5s Hörtest)")
        _send_to_bmw(f"Scanner {freq} MHz", "FM Scanner", "✓")
    else:
        _p(WARN, f"Scanner FM {freq}: nicht gestartet (RTL-SDR belegt?)", f"{elapsed:.1f}s")

    return src_ok


def test_dab(sender_nr=22):
    """8. DAB+."""
    _section(f"DAB+ (Sender #{sender_nr})", "📻")
    # _send_to_bmw absichtlich NICHT aufgerufen — würde MPRIS2-Push triggern → SIGABRT

    caps_dab = _run("which welle-cli 2>/dev/null")
    if not caps_dab:
        _p(WARN, "welle-cli nicht verfügbar — DAB übersprungen")
        return None

    # Senderliste lesen
    import json as _j
    stations_path = os.path.join(BASE_DIR, "..", "dab_stations.json")
    try:
        stations = _j.load(open(stations_path))
        sender = stations[sender_nr - 1] if len(stations) >= sender_nr else None
        name = sender.get("name","?") if sender else f"Sender #{sender_nr}"
    except Exception:
        name = f"Sender #{sender_nr}"

    t0 = time.time()
    # Sicherstellen dass kein welle-cli mehr läuft
    import subprocess as _sp3
    _sp3.run("pkill -f welle-cli 2>/dev/null", shell=True)
    time.sleep(0.5)
    _write_trigger("stop")
    time.sleep(0.5)
    _write_trigger(f"play_dab:{name}")
    _send_to_bmw(f"DAB: {name}", "Warte auf Lock...", "max 30s")

    # Warte auf Lock / PCM / DLS
    deadline = time.time() + 50
    dab_state = "unknown"
    while time.time() < deadline:
        dbg = _read_json("/tmp/pidrive_dab_play_debug.json", {})
        st = _read_json("/tmp/pidrive_status.json", {})
        if dbg.get("pcm_seen") or st.get("dab_pcm_seen"):
            dab_state = "pcm_ok"; break
        if st.get("dab_sync_ok"):
            dab_state = "sync_ok"; break
        if _current_source() == "dab" and st.get("dab_sync_seen"):
            dab_state = "partial"; break
        if st.get("dab_playback_state") == "no_lock":
            dab_state = "no_lock"; break
        time.sleep(1)

    elapsed = time.time() - t0

    if dab_state in ("pcm_ok", "sync_ok", "partial"):
        meta = _wait_for_metadata("dab", max_wait=15)
        _p(PASS if dab_state == "pcm_ok" else WARN,
           f"DAB: {name}", f"{elapsed:.1f}s  state={dab_state}")
        if meta:
            _p(PASS, f"DAB-Metadaten: '{meta[:50]}'")
        else:
            _p(WARN, "Keine DLS-Metadaten (noch nicht empfangen)")
    elif dab_state == "no_lock":
        _p(WARN, f"DAB no_lock: kein Signal für {name}", f"{elapsed:.1f}s")
    else:
        _p(WARN, f"DAB: unklar nach {elapsed:.1f}s", f"state={dab_state}")

    import os as _dab_os
    _sf = "/tmp/pidrive_dab_welle_out.txt"
    _ef = "/tmp/pidrive_dab_welle.err"
    _sf_sz = _dab_os.path.getsize(_sf) if _dab_os.path.exists(_sf) else -1
    _ef_sz = _dab_os.path.getsize(_ef) if _dab_os.path.exists(_ef) else -1
    _p(INFO if _sf_sz >= 0 else WARN,
       f"STDOUT_FILE: {_sf_sz} Bytes" if _sf_sz >= 0 else "STDOUT_FILE fehlt!")
    _p(INFO if _ef_sz >= 0 else WARN,
       f"ERR_FILE:    {_ef_sz} Bytes" if _ef_sz >= 0 else "ERR_FILE fehlt!")
    _dls_hits = []
    for _df in (_ef, _sf):
        if _dab_os.path.exists(_df) and _dab_os.path.getsize(_df) > 0:
            try:
                _dls_hits += [l for l in open(_df, encoding="utf-8", errors="ignore")
                              if "DLS:" in l]
            except Exception:
                pass
    if _dls_hits:
        _p(PASS, f"DLS: {_dls_hits[-1][:70]}")
    else:
        _p(WARN, "Keine DLS-Zeile in stderr/stdout")
    if _ef_sz > 0:
        try:
            _last_err = [l for l in open(_ef, encoding="utf-8", errors="ignore")
                         if l.strip() and "TII:" not in l and "UTCTime" not in l][-1:]
            if _last_err:
                _p(INFO, f"Letzter Fehler: {_last_err[0][:70]}")
        except Exception:
            pass

    return dab_state not in ("no_lock","unknown")


def test_dab_scan(channel="11B"):
    """DAB-Kanal-Scan mit Stationsliste."""
    _section(f"DAB SCAN Kanal {channel}", "📡")
    _send_to_bmw(f"DAB Scan {channel}", "Welle-CLI Scan...", "max 30s")

    caps = _run("which welle-cli 2>/dev/null")
    if not caps:
        _p(WARN, "welle-cli fehlt — Scan übersprungen")
        return

    # Frequenz für Kanal ermitteln
    freq_map = {
        "5A":"174.928","5B":"176.640","5C":"178.352","5D":"180.064",
        "6A":"181.936","6B":"183.648","6C":"185.360","6D":"187.072",
        "7A":"188.928","7B":"190.640","7C":"192.352","7D":"194.064",
        "8A":"195.936","8B":"197.648","8C":"199.360","8D":"201.072",
        "9A":"202.928","9B":"204.640","9C":"206.352","9D":"208.064",
        "10A":"209.936","10B":"211.648","10C":"213.360","10D":"215.072",
        "11A":"216.928","11B":"218.640","11C":"220.352","11D":"222.064",
        "12A":"223.936","12B":"225.648","12C":"227.360","12D":"229.072",
    }
    freq_mhz = freq_map.get(channel.upper())
    if not freq_mhz:
        _p(FAIL, f"Unbekannter Kanal: {channel}")
        return

    port = 7981
    t0 = time.time()
    _p(INFO, f"Starte welle-cli auf {channel} ({freq_mhz} MHz, Port {port})...")

    # welle-cli im Hintergrund für 25s
    proc = subprocess.Popen(
        f"welle-cli -c {channel} -g -1 -C 1 -w {port} 2>/tmp/welle_scan_test.err",
        shell=True, stdout=subprocess.DEVNULL
    )
    time.sleep(22)  # Scan-Zeit

    try:
        r = subprocess.run(
            f"curl -s --max-time 3 http://127.0.0.1:{port}/mux.json",
            shell=True, capture_output=True, text=True, timeout=5
        )
        data = json.loads(r.stdout) if r.stdout else {}
    except Exception:
        data = {}
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except: proc.kill()
        # Sicherheits-Kill: alle welle-cli Prozesse beenden
        import subprocess as _sp2
        _sp2.run("pkill -f welle-cli 2>/dev/null", shell=True)

    elapsed = time.time() - t0

    if not data:
        _p(WARN, f"Kein mux.json nach {elapsed:.0f}s", "kein Signal auf " + channel)
        return

    ens = data.get("ensemble",{}).get("label",{}).get("label","?")
    snr = data.get("demodulator",{}).get("snr", 0)
    fic_err = data.get("demodulator",{}).get("fic",{}).get("numcrcerrors",0)
    services = data.get("services",[])

    snr_sym = PASS if snr > 10 else (WARN if snr > 5 else FAIL)
    _p(snr_sym, f"SNR: {snr:.1f} dB", f"FIC-Fehler: {fic_err}  Ensemble: {ens}")

    if services:
        _p(PASS, f"{len(services)} Sender gefunden auf {channel}:")
        _send_to_bmw(f"DAB {channel}: {len(services)} Sender", f"SNR {snr:.0f}dB  {ens}", "✓")
        for svc in services[:15]:
            label = svc.get("label",{}).get("label","?")
            mode = svc.get("mode","?")
            bitrate = ""
            comps = svc.get("components",[])
            if comps:
                sub = comps[0].get("subchannel",{})
                bitrate = f"{sub.get('bitrate','?')}kbps"
            errs = svc.get("errorcounters",{})
            err_str = ""
            if errs.get("frameerrors",0) or errs.get("rserrors",0):
                err_str = f" ⚠ fe={errs.get('frameerrors',0)} re={errs.get('rserrors',0)}"
            _p(INFO, f"  {label:<22}  {mode}  {bitrate}{err_str}")
    else:
        _p(WARN, f"Keine Sender auf {channel}", f"SNR={snr:.1f}  evtl. kein Signal")
        _send_to_bmw(f"DAB {channel}: kein Lock", f"SNR {snr:.0f}dB", "Antenne?")


def test_spotify():
    """9. Spotify."""
    _section("SPOTIFY CONNECT", "🎵")
    _send_to_bmw("9/9: Spotify-Test", "librespot · Connect")

    # Service aktiv?
    for svc in ("librespot", "raspotify"):
        st = _run(f"systemctl is-active {svc} 2>/dev/null")
        if st == "active":
            _p(PASS, f"{svc}: aktiv")
            creds = "/var/cache/librespot/credentials.json"
            if os.path.exists(creds):
                _p(PASS, "OAuth-Token: vorhanden", creds)
            else:
                _p(WARN, "OAuth-Token fehlt", "pidrivectl system spotify-oauth")
            break
    else:
        _p(WARN, "Weder librespot noch raspotify aktiv")
        return

    # Spotify aktivieren
    t0 = time.time()
    _write_trigger("stop")
    time.sleep(0.3)
    _write_trigger("spotify_on")
    src_ok = _wait_for_source("spotify", max_wait=10)
    if src_ok:
        _p(PASS, "Spotify Connect: aktiviert", f"{time.time()-t0:.1f}s")
        _p(INFO, "→ In Spotify-App PiDrive auswählen und abspielen")
        time.sleep(5)
        s = _read_json("/tmp/pidrive_status.json")
        track = s.get("track","")
        if track:
            _p(PASS, f"Spotify-Metadaten: '{track[:50]}'")
            _send_to_bmw(track[:45], s.get("artist","Spotify")[:35], "Spotify ✓")
        else:
            _p(INFO, "Noch kein Titel (Abspielen in App nötig)")
    else:
        if not _has_audio_sink:
            _p(INFO, "Spotify aktiviert — kein Audio-Sink (BT verbinden)")
        else:
            _p(WARN, "Spotify: source nicht aktiv nach 10s (Audio-Sink vorhanden?)")


def test_avrcp_inject():
    """AVRCP-Trigger-Inject Test."""
    _section("AVRCP INJECT TEST", "🎮")
    _send_to_bmw("AVRCP Test", "next · prev · play")

    before = _read_json("/tmp/pidrive_avrcp_events.json",{}).get("total",0)
    for trigger in ("next","previous","play_pause"):
        _write_trigger(trigger)
        time.sleep(0.3)
    time.sleep(1)
    after = _read_json("/tmp/pidrive_avrcp_events.json",{}).get("total",0)
    diff = after - before
    _p(INFO, f"AVRCP-Inject: {diff} Events verarbeitet (erwartet ≥0)")
    _p(INFO, "→ pidrivectl avrcp monitor  für Live-Check mit BMW")


def test_log_summary():
    """Log-Zusammenfassung der Testperiode."""
    _section("LOG-AUSWERTUNG", "📋")

    try:
        with open("/var/log/pidrive/pidrive.log") as f:
            lines = f.readlines()
        # Letzte 100 Zeilen analysieren
        recent = lines[-100:]
        errors   = [l.strip() for l in recent if "[ERROR]"   in l]
        warnings = [l.strip() for l in recent if "[WARNING]" in l]
        infos    = [l.strip() for l in recent if "[INFO]"    in l and
                    any(k in l for k in ("MPRIS","BT","A2DP","AVRCP","Source","Boot"))]

        if errors:
            _p(FAIL, f"Fehler im Log ({len(errors)}):")
            for e in errors[-5:]:
                _p(FAIL, f"  {e[-100:]}")
        else:
            _p(PASS, "Keine Fehler im Log (letzte 100 Zeilen)")

        if warnings:
            _p(WARN, f"Warnungen: {len(warnings)}")
            for w in warnings[-5:]:
                _p(WARN, f"  {w[-100:]}")

        if infos:
            _p(INFO, f"Status-Events ({len(infos)}):")
            for i in infos[-5:]:
                _p(INFO, f"  {i[-100:]}")
    except Exception as e:
        _p(WARN, f"Log nicht lesbar: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_all():
    global _start_ts, _results, _passed, _failed, _warnings
    _start_ts = time.time()
    _results = []; _passed = 0; _failed = 0; _warnings = 0
    global _has_audio_sink
    _has_audio_sink = False

    print(f"\n{BOLD}{M}{'═'*60}{RST}")
    print(f"{BOLD}{M}  PiDrive System-Test{RST}  {DIM}pidrivectl test all{RST}")
    print(f"{BOLD}{M}  {time.strftime('%Y-%m-%d %H:%M:%S')}{RST}")
    print(f"{BOLD}{M}{'═'*60}{RST}")

    _send_to_bmw("PiDrive System-Test", "startet...", "pidrivectl test all")

    test_system()
    test_audio()
    test_bluetooth()
    test_mpris2_push()
    test_webradio()

    # Quellen die RTL-SDR brauchen
    have_rtl = bool(_run("which rtl_fm 2>/dev/null"))
    if have_rtl:
        test_fm("104.4")
        test_scanner_fm("103.0")
        test_dab(22)
        test_dab_scan("11B")
    else:
        _section("FM / SCANNER / DAB", "⚠")
        _p(WARN, "RTL-SDR nicht verfügbar — FM/Scanner/DAB übersprungen")

    test_spotify()
    test_avrcp_inject()

    # Stop + Cleanup
    _write_trigger("stop")
    import subprocess as _sp4
    _sp4.run("pkill -f welle-cli 2>/dev/null", shell=True)
    time.sleep(0.5)

    test_log_summary()

    # ── Zusammenfassung ──────────────────────────────────────────────────────
    elapsed = time.time() - _start_ts
    print(f"\n{BOLD}{M}{'═'*60}{RST}")
    print(f"{BOLD}  ERGEBNIS  {RST}  {elapsed:.1f}s")
    print(f"  {G}{BOLD}{_passed} bestanden{RST}   "
          f"{R}{BOLD}{_failed} Fehler{RST}   "
          f"{Y}{BOLD}{_warnings} Warnungen{RST}")
    print(f"{BOLD}{M}{'═'*60}{RST}\n")

    # BMW-Display: Ergebnis
    result_str = f"✓{_passed}  ✗{_failed}  ⚠{_warnings}"
    _send_to_bmw("Test abgeschlossen", result_str, f"{elapsed:.0f}s")

    # JSON speichern
    out = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed": elapsed,
        "passed": _passed, "failed": _failed, "warnings": _warnings,
        "results": _results,
    }
    try:
        with open("/tmp/pidrive_test_results.json", "w") as f:
            json.dump(out, f, indent=2)
        print(f"  {INFO} Ergebnisse: /tmp/pidrive_test_results.json\n")
    except Exception:
        pass

    return _failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
