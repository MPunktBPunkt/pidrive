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
    try:
        alsa = []
        for ln in sinks_text.splitlines():
            parts = ln.split()
            if len(parts) >= 2 and "alsa_output" in parts[1]:
                alsa.append(parts[1])
        return alsa[0] if alsa else ""
    except Exception:
        return ""


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
    S("AUDIO (PulseAudio + amixer)")
    PA = "PULSE_SERVER=unix:/var/run/pulse/native "

    # PulseAudio aktiv?
    pa_state = run("systemctl is-active pulseaudio 2>/dev/null")
    (ok if pa_state == "active" else err)(f"pulseaudio.service: {pa_state}")

    # Sinks
    sinks = run(PA + "pactl list sinks short 2>/dev/null")
    if sinks:
        for s in sinks.splitlines():
            nfo(f"Sink: {s[:80]}")
    else:
        warn("Keine PulseAudio-Sinks (pactl nicht erreichbar?)")

    # Default Sink
    ds = run(PA + "pactl get-default-sink 2>/dev/null")
    if not ds:
        # Fallback: pactl info enthält "Default Sink: NAME"
        info_txt = run(PA + "pactl info 2>/dev/null")
        for ln in info_txt.splitlines():
            if "Default Sink:" in ln:
                ds = ln.split(":", 1)[1].strip()
                break
    if ds:
        ok(f"Default Sink: {ds}")
    else:
        # Low-Risk Fallback: wenn genau ein ALSA-Sink da ist
        fallback_sink = ""
        try:
            for ln in sinks.splitlines():
                parts = ln.split()
                if len(parts) >= 2 and "alsa_output" in parts[1]:
                    fallback_sink = parts[1]
                    break
        except Exception:
            fallback_sink = ""
        if fallback_sink:
            warn(f"Default Sink: leer — Fallback aus sink list: {fallback_sink}")
        else:
            warn("Default Sink: leer (pactl get-default-sink + pactl info ergaben nichts)")

    # Sink-Inputs
    si = run(PA + "pactl list sink-inputs short 2>/dev/null")
    if si:
        ok(f"Aktive Sink-Inputs: {len(si.splitlines())} (mpv/librespot?)")
        for s in si.splitlines():
            nfo(f"  Input: {s[:80]}")
    else:
        warn("Keine aktiven Sink-Inputs — kein Audio läuft gerade?")

    # amixer numid=3 (Pi 3B Ausgang: 0=auto, 1=klinke, 2=HDMI)
    amix = run("amixer -c 0 cget numid=3 2>/dev/null")
    if amix:
        raw_val = ""
        for l in amix.splitlines():
            if "values=" in l:
                raw_val = l.split("values=", 1)[-1].strip().split()[0]
                break
        mapping = {"0": "Auto (unsicher!)", "1": "Klinke ✓", "2": "HDMI (kein Ton auf Klinke!)"}
        raw = "?"
        try:
            if raw_val:
                raw = str(int(raw_val, 0))
        except Exception:
            raw = raw_val or "?"
        label = mapping.get(raw, f"Unbekannt ({raw})")
        (ok if raw == "1" else warn)(f"Pi Audio-Ausgang (amixer numid=3): {label}")
    else:
        warn("amixer numid=3 nicht lesbar")

    # Audio State File
    state_file = "/tmp/pidrive_audio_state.json"
    if os.path.exists(state_file):
        import json
        try:
            with open(state_file) as f:
                state = json.load(f)
            eff = state.get("effective", "?")
            req = state.get("requested", "?")
            rsn = state.get("reason", "?")
            ok(f"Audio-State: requested={req} effective={eff} reason={rsn}")
            if eff == "klinke":
                alsa_sink = _get_single_alsa_sink(sinks if "sinks" in dir() else "")
                if alsa_sink:
                    ok(f"Klinke-Routing plausibel: effective=klinke + sink={alsa_sink}")
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
