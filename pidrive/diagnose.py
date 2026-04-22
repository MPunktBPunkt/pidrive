#!/usr/bin/env python3
"""diagnose.py - PiDrive System-Diagnose v0.9.6

v0.6.0: Core/Display getrennt.
- pidrive_core.service  — headless, kein pygame
- pidrive_display.service — pygame auf fb1 direkt

Aufruf: sudo python3 ~/pidrive/pidrive/diagnose.py
"""
import os, subprocess, fcntl, sys, time

VT_ACTIVATE = 0x5606

def run(cmd):
    try: return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except: return ""

def S(t): print(f"\n{'='*50}\n  {t}\n{'='*50}")
def ok(m):   print(f"  ✓ {m}")
def warn(m): print(f"  ⚠ {m}")
def err(m):  print(f"  ✗ {m}")
def nfo(m):  print(f"    {m}")

def check_services():
    S("PIDRIVE SERVICES (Core + Display + Web)")

    # Core
    core_st = run("systemctl is-active pidrive_core 2>/dev/null")
    (ok if core_st=="active" else err)(f"pidrive_core.service: {core_st}")
    core_pid = run("systemctl show pidrive_core --property=MainPID --value 2>/dev/null")
    if core_pid and core_pid != "0":
        ok(f"Core PID: {core_pid}")
        try:
            exe = os.readlink(f"/proc/{core_pid}/exe")
            (ok if "python" in exe else err)(f"Core exe: {exe}")
        except: pass

    # Display
    disp_st = run("systemctl is-active pidrive_display 2>/dev/null")
    color = ok if disp_st=="active" else warn  # warn not err — display optional
    color(f"pidrive_display.service: {disp_st} (optional)")
    disp_pid = run("systemctl show pidrive_display --property=MainPID --value 2>/dev/null")
    if disp_pid and disp_pid != "0":
        nfo(f"Display PID: {disp_pid}")
        try:
            exe = os.readlink(f"/proc/{disp_pid}/exe")
            nfo(f"Display exe: {exe}")
        except: pass

    # Alter monolithischer Service
    old_st = run("systemctl is-active pidrive 2>/dev/null")
    if old_st == "active":
        warn(f"Alter pidrive.service noch aktiv — sollte deaktiviert sein")
    else:
        ok(f"Alter pidrive.service: {old_st} (korrekt deaktiviert)")

def check_ipc():
    S("IPC STATUS (/tmp/ Dateien)")
    import json
    for path, label in [
        ("/tmp/pidrive_status.json", "Status-JSON"),
        ("/tmp/pidrive_menu.json",   "Menu-JSON"),
        ("/tmp/pidrive_cmd",         "Trigger-Datei"),
    ]:
        if os.path.exists(path):
            age = time.time() - os.path.getmtime(path)
            if path.endswith(".json"):
                try:
                    data = json.load(open(path))
                    ok(f"{label}: vorhanden ({int(age)}s alt) — {list(data.keys())[:4]}")
                except:
                    warn(f"{label}: vorhanden aber ungueltig")
            else:
                ok(f"{label}: vorhanden")
        else:
            if "cmd" in path:
                nfo(f"{label}: nicht vorhanden (wartet auf Befehl)")
            else:
                err(f"{label}: fehlt — Core schreibt nicht?")

def check_display_env():
    S("DISPLAY SERVICE KONFIGURATION")
    cfg = run("systemctl show pidrive_display -p Environment 2>/dev/null")
    if "SDL_FBDEV=/dev/fb1" in cfg:
        ok("SDL_FBDEV=/dev/fb1 (direkt auf SPI-Display)")
    else:
        err("SDL_FBDEV=/dev/fb1 fehlt im Display-Service!")
    if "FBCON_KEEP_TTY=1" in cfg:
        ok("SDL_VIDEO_FBCON_KEEP_TTY=1")
    else:
        warn("SDL_VIDEO_FBCON_KEEP_TTY=1 fehlt (set_mode() koennte haengen)")

def check_fbcp():
    S("FBCP (seit v0.6.0 dauerhaft entfernt)")
    r = run("pgrep -a fbcp")
    if r:
        warn(f"fbcp laeuft noch: {r}")
        warn("  Korrekt: kein fbcp mehr (fb1 direkt)")
    else:
        ok("fbcp laeuft nicht (korrekt fuer v0.6.0)")

def check_fb(path, name):
    S(f"FRAMEBUFFER {name} ({path})")
    if not os.path.exists(path): err(f"{path} fehlt"); return
    try:
        fb_num = path.replace("/dev/fb","")
        bpp_f  = f"/sys/class/graphics/fb{fb_num}/bits_per_pixel"
        vsz_f  = f"/sys/class/graphics/fb{fb_num}/virtual_size"
        bpp    = open(bpp_f).read().strip() if os.path.exists(bpp_f) else "?"
        vsz    = open(vsz_f).read().strip() if os.path.exists(vsz_f) else "?"
        ok(f"Groesse: {vsz}, {bpp} bpp")
        if path == "/dev/fb1" and bpp == "16":
            ok("fb1: 16bpp RGB565 — korrekt fuer direktes Rendering")
        elif path == "/dev/fb1" and bpp != "16":
            warn(f"fb1: {bpp}bpp — set_mode(..., 0, 16) noetig")

        raw   = open(path,"rb").read(min(4000, os.path.getsize(path)))
        total = len(raw)
        nz    = sum(1 for b in raw if b != 0)
        pct   = nz*100//total if total else 0
        (ok if pct > 5 else warn)(f"Inhalt: {pct}% non-zero {'(Bild vorhanden)' if pct>5 else '(schwarz/leer)'}")
    except Exception as e: err(f"Fehler: {e}")

def check_vtcon():
    S("VTCONSOLE STATUS")
    try:
        cmdline = open("/boot/cmdline.txt").read()
        (ok if "fbcon=nodeconfig" in cmdline else warn)(
            f"cmdline.txt: {'fbcon=nodeconfig gesetzt' if 'fbcon=nodeconfig' in cmdline else 'fbcon=nodeconfig fehlt'}")
    except: pass
    for i in (0,1):
        try:
            val  = open(f"/sys/class/vtconsole/vtcon{i}/bind").read().strip()
            name = open(f"/sys/class/vtconsole/vtcon{i}/name").read().strip()
            # vtcon0 = dummy (immer 1, normal)
            # vtcon1 = framebuffer (sollte 0 sein)
            if i == 0:
                nfo(f"vtcon0/bind={val} ({name}) — Text-VT-Layer (normal)")
            else:
                (ok if val=="0" else warn)(f"vtcon1/bind={val} ({name}) {'← OK' if val=='0' else '← fbcon noch aktiv'}")
        except Exception as e: nfo(f"vtcon{i}: {e}")

def check_log():
    S("PIDRIVE LOG (letzte 8 Zeilen)")
    log_file = "/var/log/pidrive/pidrive.log"
    if not os.path.exists(log_file): err("Log-Datei fehlt"); return
    lines = open(log_file).readlines()
    for l in lines[-8:]: nfo(l.rstrip())
    # Pruefe ob Core-Logs vorhanden
    core_start = run("systemctl show pidrive_core --property=ExecMainStartTimestamp --value 2>/dev/null")
    if core_start and lines:
        last_ts = lines[-1][:19]
        nfo(f"Core gestartet: {core_start[:19] if core_start else '?'}")

def test_sdl():
    S("SDL DISPLAY TEST (fb1)")
    try:
        import pygame
        os.environ["SDL_VIDEODRIVER"] = "fbcon"
        os.environ["SDL_FBDEV"]       = "/dev/fb1"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        os.environ["SDL_VIDEO_FBCON_KEEP_TTY"] = "1"
        pygame.display.init()
        ok(f"pygame.display.init() OK — Treiber: {pygame.display.get_driver()}")
        pygame.display.quit()
    except Exception as e:
        err(f"pygame auf fb1 FEHLER: {e}")
        nfo("  → set_mode() Test: sudo SDL_FBDEV=/dev/fb1 ... python3 -c 'import pygame...'")

def summary():
    S("ZUSAMMENFASSUNG")
    core_ok  = run("systemctl is-active pidrive_core 2>/dev/null") == "active"
    disp_ok  = run("systemctl is-active pidrive_display 2>/dev/null") == "active"
    ipc_ok   = os.path.exists("/tmp/pidrive_status.json")
    fbcp_off = not bool(run("pgrep fbcp"))
    fb1_ok   = os.path.exists("/dev/fb1")

    checks = [
        (core_ok,  "pidrive_core.service laeuft"),
        (ipc_ok,   "/tmp/pidrive_status.json vorhanden"),
        (fb1_ok,   "/dev/fb1 vorhanden (SPI-Display)"),
        (fbcp_off, "fbcp nicht aktiv (v0.6.0: nicht noetig)"),
    ]
    all_core_ok = True
    for r,l in checks:
        (ok if r else err)(l)
        if not r: all_core_ok = False

    # Display optional
    (ok if disp_ok else warn)(f"pidrive_display.service {'laeuft' if disp_ok else 'inaktiv (optional)'}")

    if all_core_ok:
        print("\n  ✓ Core laeuft korrekt")
        if not disp_ok:
            print("  ⚠ Display inaktiv — teste fb1 direkt:")
            print("    sudo SDL_FBDEV=/dev/fb1 SDL_VIDEODRIVER=fbcon SDL_AUDIODRIVER=dummy")
            print("    SDL_VIDEO_FBCON_KEEP_TTY=1 python3 -c")
            print("    \"import pygame,time; pygame.display.init(); s=pygame.display.set_mode((480,320),0,16)")
            print("     s.fill((255,0,0)); pygame.display.flip(); print('ROT OK'); time.sleep(5)\"")
    else:
        print("\n  ✗ Probleme vorhanden — siehe Details oben")

def _get_single_alsa_sink(sinks_text):
    """Gibt den ersten ALSA-Sink zurück der NICHT HDMI ist (Card 1 = Klinke)."""
    try:
        headphone = []
        hdmi_only = []
        for ln in sinks_text.splitlines():
            parts = ln.split()
            if len(parts) < 2 or "alsa_output" not in parts[1]:
                continue
            name = parts[1].lower()
            raw  = ln.lower()
            if "hdmi" in name or "hdmi" in raw:
                hdmi_only.append(parts[1])
            else:
                headphone.append(parts[1])
        # Klinken-Sink bevorzugen; HDMI-Sink als letzter Ausweg
        return headphone[0] if headphone else (hdmi_only[0] if hdmi_only else "")
    except Exception:
        return ""


def _sink_is_hdmi(sink_name: str, sinks_text: str = "") -> bool:
    """Prüft ob ein Sink-Name zu HDMI (Card 0) gehört."""
    n = sink_name.lower()
    if "hdmi" in n:
        return True
    # .0. im Namen = Card 0 = HDMI auf Pi 3B mit modernem Pi OS
    import re
    if re.search(r'alsa_output\.0\.', sink_name):
        return True
    return False


def _parse_amixer_numid3(txt):
    raw = ""
    for l in txt.splitlines():
        if "values=" in l:
            raw = l.split("values=", 1)[-1].strip().split()[0]
            break
    if not raw:
        return "?"
    try:
        return str(int(raw, 0))
    except Exception:
        return raw



def check_audio():
    """
    Audio-Diagnose (v0.9.10) — prüft die vollständige Kette:
    system.pa → PulseAudio-Sinks → Klinken-Sink vorhanden? → Default Sink → Routing
    """
    S("AUDIO (PulseAudio + amixer)")
    PA = "PULSE_SERVER=unix:/var/run/pulse/native "

    # ── 1. PulseAudio aktiv? ────────────────────────────────────────────────
    pa_state = run("systemctl is-active pulseaudio 2>/dev/null")
    (ok if pa_state == "active" else err)(f"pulseaudio.service: {pa_state}")

    # ── 2. system.pa — Card 1 (Headphones/Klinke) geladen? ─────────────────
    # ROOT CAUSE v0.9.10: setup_bt_audio.sh schrieb system.pa nur mit device_id=0 (HDMI)
    # → kein Klinken-Sink in PulseAudio → Audio geht zu HDMI → kein Ton
    sys_pa = "/etc/pulse/system.pa"
    if os.path.exists(sys_pa):
        try:
            with open(sys_pa) as f:
                spa_content = f.read()
            has_card0 = "device_id=0" in spa_content
            has_card1 = "device_id=1" in spa_content
            if has_card0 and has_card1:
                ok("system.pa: Card 0 (HDMI) + Card 1 (Headphones/Klinke) ✓")
            elif has_card1 and not has_card0:
                ok("system.pa: Card 1 (Headphones/Klinke) geladen — Card 0 fehlt (OK wenn kein HDMI)")
            elif has_card0 and not has_card1:
                err("system.pa: NUR Card 0 (HDMI) geladen — Card 1 (Klinke) FEHLT!")
                err("  → FIX: sudo sed -i 's/device_id=0/device_id=0\\nload-module module-alsa-card device_id=1/' /etc/pulse/system.pa")
                err("  → dann: sudo systemctl restart pulseaudio")
            else:
                warn("system.pa: kein module-alsa-card gefunden")
        except Exception as e:
            warn(f"system.pa: Lesefehler ({e})")
    else:
        warn("system.pa: /etc/pulse/system.pa nicht gefunden")

    # ── 3. ALSA Hardware (aplay -l) ─────────────────────────────────────────
    aplay_out = run("aplay -l 2>/dev/null")
    has_hdmi = "HDMI" in aplay_out or "hdmi" in aplay_out.lower()
    has_headphones = "Headphones" in aplay_out or "headphones" in aplay_out.lower()
    if has_headphones:
        ok("ALSA: bcm2835 Headphones (Klinke) als Hardware erkannt ✓")
    else:
        warn("ALSA: kein Headphones-Gerät in aplay -l — Treiberproblem?")
    if has_hdmi:
        nfo("ALSA: bcm2835 HDMI vorhanden (Card 0)")

    # ── 4. amixer controls — Klinken-Control ermitteln ──────────────────────
    # amixer numid=3 ist auf neuem Pi OS NICHT der Routing-Switch!
    # Auf Kernel >=5.x: Card 0 hat Master Playback Volume, kein Route-Switch
    # Card 1 (Headphones) hat eigene PCM-Controls
    amix_c0 = run("amixer -c 0 controls 2>/dev/null")
    amix_c1 = run("amixer -c 1 controls 2>/dev/null")
    if amix_c0:
        has_route_c0 = "PCM Playback Route" in amix_c0 or "Route" in amix_c0
        has_pcm_c0   = "PCM Playback Volume" in amix_c0 or "Master" in amix_c0
        if has_route_c0:
            nfo("amixer Card 0: PCM Playback Route vorhanden (alter Kernel)")
        elif has_pcm_c0:
            nfo("amixer Card 0: Master/PCM Volume — kein Route-Switch (neuer Kernel, HDMI)")
    if amix_c1:
        has_pcm_c1 = "PCM Playback Volume" in amix_c1
        has_mute_c1 = "PCM Playback Switch" in amix_c1
        if has_pcm_c1:
            vol_c1 = run("amixer -c 1 sget 'PCM' 2>/dev/null")
            if "on" in vol_c1.lower():
                ok("amixer Card 1 (Klinke): PCM Playback = on (nicht gemutet) ✓")
            elif "off" in vol_c1.lower():
                err("amixer Card 1 (Klinke): PCM Playback GEMUTET — FIX: amixer -c 1 sset 'PCM' 85% unmute")
            else:
                nfo(f"amixer Card 1: {vol_c1[:60]}")
        else:
            warn("amixer Card 1: kein PCM Playback Volume Control")
    else:
        warn("amixer Card 1 nicht erreichbar — Card 1 existiert als ALSA-Gerät?")

    # ── 5. PulseAudio Sinks — Klinken-Sink vorhanden? ───────────────────────
    sinks = run(PA + "pactl list sinks short 2>/dev/null")
    sink_list = []
    if sinks:
        for s in sinks.splitlines():
            if not s.strip():
                continue
            parts = s.split()
            if len(parts) >= 2:
                sink_list.append(parts[1])
                nfo(f"Sink: {s[:90]}")
    else:
        err("Keine PulseAudio-Sinks — PulseAudio läuft aber keine Sinks?")

    # Kritische Prüfung: gibt es einen Nicht-HDMI ALSA-Sink?
    klinke_sinks = [s for s in sink_list if "alsa_output" in s and not _sink_is_hdmi(s)]
    hdmi_sinks   = [s for s in sink_list if "alsa_output" in s and _sink_is_hdmi(s)]

    if klinke_sinks:
        ok(f"Klinken-Sink vorhanden: {klinke_sinks[0]} ✓")
    else:
        err("KEIN Klinken-Sink in PulseAudio!")
        if hdmi_sinks:
            err(f"  Nur HDMI-Sink vorhanden: {hdmi_sinks[0]}")
            err("  → Audio geht zu HDMI → kein Ton auf Klinke")
            err("  → FIX: sudo sed -i 's/device_id=0/device_id=0\nload-module module-alsa-card device_id=1/' /etc/pulse/system.pa && sudo systemctl restart pulseaudio")

    # ── 6. Default Sink ──────────────────────────────────────────────────────
    ds = run(PA + "pactl get-default-sink 2>/dev/null")
    if not ds:
        info_txt = run(PA + "pactl info 2>/dev/null")
        for ln in info_txt.splitlines():
            if "Default Sink:" in ln:
                ds = ln.split(":", 1)[1].strip()
                break
    if ds:
        if _sink_is_hdmi(ds):
            err(f"Default Sink: {ds} — IST HDMI! Kein Ton auf Klinke")
            err("  → FIX: pactl set-default-sink " + (klinke_sinks[0] if klinke_sinks else "<klinke-sink>"))
        elif "alsa_output" in ds:
            ok(f"Default Sink: {ds} (Klinke) ✓")
        else:
            nfo(f"Default Sink: {ds}")
    else:
        err("Default Sink: NICHT GESETZT — mpv wählt ersten verfügbaren Sink (oft HDMI!)")
        if klinke_sinks:
            err(f"  → FIX: PULSE_SERVER=unix:/var/run/pulse/native pactl set-default-sink {klinke_sinks[0]}")

    # ── 7. Sink-Inputs ───────────────────────────────────────────────────────
    si = run(PA + "pactl list sink-inputs short 2>/dev/null")
    if si:
        ok(f"Aktive Sink-Inputs: {len(si.splitlines())} (mpv/librespot?)")
        for s in si.splitlines():
            nfo(f"  Input: {s[:90]}")
        # Prüfen ob Inputs auf HDMI-Sink laufen
        for s in si.splitlines():
            parts = s.split()
            if len(parts) >= 2:
                sink_id = parts[1]
                # Sink-ID mit Sink-Namen abgleichen
                for ln in (sinks or "").splitlines():
                    p = ln.split()
                    if len(p) >= 2 and p[0] == sink_id and _sink_is_hdmi(p[1]):
                        err(f"  ⚠ Sink-Input {parts[0]} läuft auf HDMI-Sink! → kein Ton auf Klinke")
    else:
        warn("Keine aktiven Sink-Inputs — kein Audio läuft gerade")

    # ── 8. Audio State File ──────────────────────────────────────────────────
    state_file = "/tmp/pidrive_audio_state.json"
    if os.path.exists(state_file):
        import json
        try:
            with open(state_file) as f:
                state = json.load(f)
            eff  = state.get("effective", "?")
            req  = state.get("requested", "?")
            rsn  = state.get("reason", "?")
            sink = state.get("sink", "?")
            ok(f"Audio-State: requested={req} effective={eff} reason={rsn}")
            # Kreuzvalidierung: behauptet klinke, aber Sink ist HDMI?
            if eff == "klinke" and sink and _sink_is_hdmi(sink):
                err(f"  ⚠ WIDERSPRUCH: effective=klinke aber sink={sink} ist HDMI!")
                err("     PiDrive glaubt Klinke zu spielen, Audio geht aber zu HDMI")
            elif eff == "klinke" and sink and not _sink_is_hdmi(sink):
                ok(f"  Sink={sink} ist Klinke ✓")
        except Exception as e:
            warn(f"Audio-State: Lesefehler ({e})")
    else:
        warn("Audio-State-Datei fehlt (/tmp/pidrive_audio_state.json)")


def check_bluetooth():
    S("BLUETOOTH")

    # Service Status
    bt_state = run("systemctl is-active bluetooth 2>/dev/null")
    (ok if bt_state == "active" else err)(f"bluetooth.service: {bt_state}")

    # hci0 vorhanden?
    hci = run("hciconfig hci0 2>/dev/null")
    if hci:
        up = "UP RUNNING" in hci
        (ok if up else warn)(f"hci0: {'UP RUNNING' if up else 'DOWN / fehlt'}")
    else:
        err("hci0 nicht gefunden — BT-Dongle fehlt oder Treiber-Problem")

    # Gepaarte Geräte
    paired = run("bluetoothctl paired-devices 2>/dev/null")
    if paired:
        ok(f"Gepaarte Geräte: {len(paired.splitlines())}")
        for l in paired.splitlines():
            nfo(f"  {l}")
    else:
        warn("Keine gepaarten Geräte in BlueZ-Datenbank")
        warn("→ Gerät muss neu gepairt werden (bluetoothctl: pair ...)")

    # BT-Agent
    agent_test = run("echo 'agent on' | timeout 4s bluetoothctl 2>/dev/null")
    if "registered" in agent_test.lower() or "agent on" in agent_test.lower():
        ok("BT-Agent: registrierbar")
    else:
        warn(f"BT-Agent: Antwort: {agent_test[:60]}")

    # A2DP Sinks in PulseAudio
    PA = "PULSE_SERVER=unix:/var/run/pulse/native "
    bt_sinks = run(PA + "pactl list sinks short 2>/dev/null | grep bluez")
    if bt_sinks:
        ok(f"BT A2DP Sink aktiv: {bt_sinks[:80]}")
    else:
        nfo("Kein BT A2DP Sink aktiv (normal wenn kein BT verbunden)")


def check_rtlsdr():
    S("RTL-SDR")
    import json as _json

    # USB
    lsusb = run("lsusb 2>/dev/null")
    found = any(x in lsusb for x in ["0bda:2838", "RTL2838", "RTL2832"])
    (ok if found else warn)(f"RTL-SDR USB: {'erkannt ✓' if found else 'NICHT erkannt'}")
    if not found:
        warn("→ Stick abziehen und neu einstecken, dann RTL-SDR Reset im WebUI")

    # Tools
    for tool in ["rtl_fm", "rtl_test", "welle-cli"]:
        p = run(f"which {tool} 2>/dev/null")
        (ok if p else err)(f"{tool}: {p if p else 'FEHLT'}")

    # RTL-SDR State File
    state_file = "/tmp/pidrive_rtlsdr.json"
    if os.path.exists(state_file):
        try:
            with open(state_file) as f:
                state = _json.load(f)
            busy = state.get("busy", False)
            procs = state.get("processes", [])
            (ok if not busy else warn)(f"RTL-SDR busy: {busy} | Prozesse: {len(procs)}")
            ppm = state.get("ppm", None)
            if ppm is not None:
                nfo(f"PPM-Konfiguration: {ppm}")
        except Exception as e:
            warn(f"RTL-SDR State: Lesefehler ({e})")
    else:
        nfo("Kein RTL-SDR State File — normal beim Start")

    # Settings: ppm + squelch
    settings_file = "/home/pi/pidrive/pidrive/config/settings.json"
    if os.path.exists(settings_file):
        try:
            import json as _j
            with open(settings_file) as f:
                sett = _j.load(f)
            nfo(f"Settings: fm_gain={sett.get('fm_gain',-1)} dab_gain={sett.get('dab_gain',-1)} "
                f"ppm={sett.get('ppm_correction',0)} squelch={sett.get('scanner_squelch',25)}")
        except Exception:
            pass


def check_processes():
    S("RELEVANTE PROZESSE")
    cmd = (r"ps ax -o pid=,user=,cmd= | egrep "
           r"'pidrive|rtl_fm|welle-cli|rtl_test|mpv|librespot|pulseaudio|pipewire|bluetoothd' "
           r"| grep -v grep")
    out = run(cmd)
    if out:
        ok("Relevante Prozesse gefunden:")
        for ln in out.splitlines():
            nfo(ln[:140])
        # Warnung: mpv läuft aber kein PulseAudio-Input?
        pa_cmd = "PULSE_SERVER=unix:/var/run/pulse/native pactl list sink-inputs short 2>/dev/null"
        pa_out = run(pa_cmd)
        has_mpv = any("mpv" in l for l in out.splitlines())
        if has_mpv and not pa_out:
            warn("mpv läuft, aber keine PulseAudio Sink-Inputs!")
            warn("→ PULSE_SERVER in pidrive_core.service prüfen")
        elif pa_out:
            ok(f"PulseAudio Sink-Inputs: {len(pa_out.splitlines())}")
    else:
        warn("Keine relevanten Prozesse gefunden")


def check_source_state():
    S("SOURCE STATE (Quellen-Zustandsmaschine)")
    try:
        import sys, os, time as _time, json as _j
        sys.path.insert(0, "/home/pi/pidrive/pidrive")
        try:
            from modules.source_state import load_snapshot_file, snapshot
            st = load_snapshot_file() or snapshot()
            src    = st.get("source_current", "?")
            bt     = st.get("bt_state", "?")
            ar     = st.get("audio_route", "?")
            tr     = st.get("transition", False)
            bp     = st.get("boot_phase", "?")
            owner  = st.get("owner", "")
            target = st.get("source_target", "")
            since  = st.get("since", 0)
            (ok if not tr else warn)(f"Quelle: {src} | Audio-Route: {ar} | BT: {bt}")
            nfo(f"boot_phase: {bp} | transition: {tr}")
            if owner:
                nfo(f"owner: {owner}")
            if target:
                nfo(f"target: {target}")
            if since:
                try:
                    age = _time.time() - float(since)
                    nfo(f"transition_age: {age:.1f}s")
                except Exception:
                    pass
            if tr:
                warn(f"Transition läuft: owner={owner}")
            if bp == "cold_start":
                warn("boot_phase=cold_start — Core evtl. nicht synchron (Shared-State fehlt?)")
            # Plausibilitätscheck gegen Audio-State
            try:
                af = "/tmp/pidrive_audio_state.json"
                if os.path.exists(af):
                    with open(af, "r", encoding="utf-8") as f:
                        ad = _j.load(f)
                    eff = ad.get("effective", "")
                    if eff == "klinke" and not ar:
                        warn("source_state.audio_route leer, Audio-State sagt klinke — Sync-Problem")
                    elif eff and ar and eff != ar:
                        warn(f"Audio-State/source_state abweichend: effective={eff} vs audio_route={ar}")
                    elif eff and ar and eff == ar:
                        ok(f"source_state.audio_route konsistent: {ar}")
            except Exception as _se:
                nfo(f"source/audio Plausibilitätscheck: {_se}")
        except Exception as e:
            warn(f"source_state Import fehlgeschlagen: {e}")
    except Exception as e:
        warn(f"source_state check: {e}")


def main():
    print(f"\n{'='*50}\n  PiDrive Diagnose v0.9.6\n{'='*50}")
    print(f"  Datum:  {run('date')}\n  Kernel: {run('uname -r')}")
    check_services()
    check_ipc()
    check_display_env()
    check_fbcp()
    check_fb("/dev/fb0", "fb0 (HDMI intern)")
    check_fb("/dev/fb1", "fb1 (SPI Display)")
    check_vtcon()
    check_log()
    check_audio()
    check_bluetooth()
    check_rtlsdr()
    check_processes()
    check_source_state()
    test_sdl()
    summary()

if __name__ == "__main__":
    if os.getuid() != 0:
        print("sudo python3 diagnose.py"); sys.exit(1)
    main()
