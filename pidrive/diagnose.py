#!/usr/bin/env python3
"""diagnose.py - PiDrive System-Diagnose v0.9.14-final

Core/Display/Web Diagnose für PiDrive.

Aufruf:
    sudo python3 ~/pidrive/pidrive/diagnose.py
"""

import os
import subprocess
import sys
import time

VT_ACTIVATE = 0x5606


def run(cmd):
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def S(title):
    print(f"\n{'='*50}\n  {title}\n{'='*50}")


def ok(msg):
    print(f"  ✓ {msg}")


def warn(msg):
    print(f"  ⚠ {msg}")


def err(msg):
    print(f"  ✗ {msg}")


def nfo(msg):
    print(f"    {msg}")


def _sink_is_hdmi(sink_name: str, sinks_text: str = "") -> bool:
    """
    Card 0 = HDMI, Card 1 = Headphones/Klinke auf Pi 3B mit modernem Pi OS.
    """
    import re
    n = (sink_name or "").lower()
    if "hdmi" in n:
        return True
    if re.search(r'alsa_output\.0\.', sink_name or ""):
        return True
    return False


def _get_single_alsa_sink(sinks_text):
    """
    Gibt bevorzugt einen Nicht-HDMI ALSA-Sink zurück.
    """
    try:
        headphone = []
        hdmi_only = []
        for ln in sinks_text.splitlines():
            parts = ln.split()
            if len(parts) < 2 or "alsa_output" not in parts[1]:
                continue
            name = parts[1]
            if _sink_is_hdmi(name, sinks_text):
                hdmi_only.append(name)
            else:
                headphone.append(name)
        return headphone[0] if headphone else (hdmi_only[0] if hdmi_only else "")
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


def _read_json(path, default=None):
    if default is None:
        default = {}
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ──────────────────────────────────────────────────────────────────────────────
# Services / IPC / Display
# ──────────────────────────────────────────────────────────────────────────────

def check_services():
    S("PIDRIVE SERVICES (Core + Display + Web)")

    core_st = run("systemctl is-active pidrive_core 2>/dev/null")
    (ok if core_st == "active" else err)(f"pidrive_core.service: {core_st}")
    core_pid = run("systemctl show pidrive_core --property=MainPID --value 2>/dev/null")
    if core_pid and core_pid != "0":
        ok(f"Core PID: {core_pid}")
        try:
            exe = os.readlink(f"/proc/{core_pid}/exe")
            (ok if "python" in exe else err)(f"Core exe: {exe}")
        except Exception:
            pass

    disp_st = run("systemctl is-active pidrive_display 2>/dev/null")
    (ok if disp_st == "active" else warn)(f"pidrive_display.service: {disp_st} (optional)")
    disp_pid = run("systemctl show pidrive_display --property=MainPID --value 2>/dev/null")
    if disp_pid and disp_pid != "0":
        nfo(f"Display PID: {disp_pid}")
        try:
            exe = os.readlink(f"/proc/{disp_pid}/exe")
            nfo(f"Display exe: {exe}")
        except Exception:
            pass

    web_st = run("systemctl is-active pidrive_web 2>/dev/null")
    (ok if web_st == "active" else warn)(f"pidrive_web.service: {web_st} (optional)")
    web_pid = run("systemctl show pidrive_web --property=MainPID --value 2>/dev/null")
    if web_pid and web_pid != "0":
        nfo(f"Web PID: {web_pid}")

    old_st = run("systemctl is-active pidrive 2>/dev/null")
    if old_st == "active":
        warn("Alter pidrive.service noch aktiv — sollte deaktiviert sein")
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
                except Exception:
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
        warn(f"fbcp läuft noch: {r}")
        warn("  Korrekt: kein fbcp mehr (fb1 direkt)")
    else:
        ok("fbcp läuft nicht (korrekt fuer v0.6.0)")


def check_fb(path, name):
    S(f"FRAMEBUFFER {name} ({path})")
    if not os.path.exists(path):
        err(f"{path} fehlt")
        return
    try:
        fb_num = path.replace("/dev/fb", "")
        bpp_f  = f"/sys/class/graphics/fb{fb_num}/bits_per_pixel"
        vsz_f  = f"/sys/class/graphics/fb{fb_num}/virtual_size"
        bpp    = open(bpp_f).read().strip() if os.path.exists(bpp_f) else "?"
        vsz    = open(vsz_f).read().strip() if os.path.exists(vsz_f) else "?"
        ok(f"Groesse: {vsz}, {bpp} bpp")
        if path == "/dev/fb1" and bpp == "16":
            ok("fb1: 16bpp RGB565 — korrekt fuer direktes Rendering")
        elif path == "/dev/fb1" and bpp != "16":
            warn(f"fb1: {bpp}bpp — set_mode(..., 0, 16) noetig")

        raw   = open(path, "rb").read(min(4000, os.path.getsize(path)))
        total = len(raw)
        nz    = sum(1 for b in raw if b != 0)
        pct   = nz * 100 // total if total else 0
        (ok if pct > 5 else warn)(
            f"Inhalt: {pct}% non-zero {'(Bild vorhanden)' if pct > 5 else '(schwarz/leer)'}"
        )
    except Exception as e:
        err(f"Fehler: {e}")


def check_vtcon():
    S("VTCONSOLE STATUS")
    try:
        cmdline = open("/boot/cmdline.txt").read()
        (ok if "fbcon=nodeconfig" in cmdline else warn)(
            "cmdline.txt: " + ("fbcon=nodeconfig gesetzt" if "fbcon=nodeconfig" in cmdline else "fbcon=nodeconfig fehlt")
        )
    except Exception:
        pass

    for i in (0, 1):
        try:
            val  = open(f"/sys/class/vtconsole/vtcon{i}/bind").read().strip()
            name = open(f"/sys/class/vtconsole/vtcon{i}/name").read().strip()
            if i == 0:
                nfo(f"vtcon0/bind={val} ({name}) — Text-VT-Layer (normal)")
            else:
                (ok if val == "0" else warn)(
                    f"vtcon1/bind={val} ({name}) {'← OK' if val == '0' else '← fbcon noch aktiv'}"
                )
        except Exception as e:
            nfo(f"vtcon{i}: {e}")


def check_log():
    S("PIDRIVE LOG (letzte 8 Zeilen)")
    log_file = "/var/log/pidrive/pidrive.log"
    if not os.path.exists(log_file):
        err("Log-Datei fehlt")
        return
    lines = open(log_file).readlines()
    for l in lines[-8:]:
        nfo(l.rstrip())
    core_start = run("systemctl show pidrive_core --property=ExecMainStartTimestamp --value 2>/dev/null")
    if core_start and lines:
        nfo(f"Core gestartet: {core_start[:19] if core_start else '?'}")


# ──────────────────────────────────────────────────────────────────────────────
# Audio
# ──────────────────────────────────────────────────────────────────────────────

def check_audio():
    """
    Vollständige Audio-Diagnose:
    system.pa → ALSA → amixer → PulseAudio Sinks → Default-Sink → Audio-State
    """
    S("AUDIO (PulseAudio + amixer)")
    PA = "PULSE_SERVER=unix:/var/run/pulse/native "

    pa_state = run("systemctl is-active pulseaudio 2>/dev/null")
    (ok if pa_state == "active" else err)(f"pulseaudio.service: {pa_state}")

    # system.pa
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

    # ALSA Hardware
    aplay_out = run("aplay -l 2>/dev/null")
    has_hdmi = "HDMI" in aplay_out or "hdmi" in aplay_out.lower()
    has_headphones = "Headphones" in aplay_out or "headphones" in aplay_out.lower()
    if has_headphones:
        ok("ALSA: bcm2835 Headphones (Klinke) als Hardware erkannt ✓")
    else:
        warn("ALSA: kein Headphones-Gerät in aplay -l — Treiberproblem?")
    if has_hdmi:
        nfo("ALSA: bcm2835 HDMI vorhanden (Card 0)")

    # amixer
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

    # Sinks
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

    klinke_sinks = [s for s in sink_list if "alsa_output" in s and not _sink_is_hdmi(s)]
    hdmi_sinks   = [s for s in sink_list if "alsa_output" in s and _sink_is_hdmi(s)]

    if klinke_sinks:
        ok(f"Klinken-Sink vorhanden: {klinke_sinks[0]} ✓")
    else:
        err("KEIN Klinken-Sink in PulseAudio!")
        if hdmi_sinks:
            err(f"  Nur HDMI-Sink vorhanden: {hdmi_sinks[0]}")
            err("  → Audio geht zu HDMI → kein Ton auf Klinke")
            err("  → FIX: sudo sed -i 's/device_id=0/device_id=0\\nload-module module-alsa-card device_id=1/' /etc/pulse/system.pa && sudo systemctl restart pulseaudio")

    # Default Sink
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

    # Sink-Inputs
    si = run(PA + "pactl list sink-inputs short 2>/dev/null")
    if si:
        ok(f"Aktive Sink-Inputs: {len(si.splitlines())} (mpv/librespot?)")
        for s in si.splitlines():
            nfo(f"  Input: {s[:90]}")
        for s in si.splitlines():
            parts = s.split()
            if len(parts) >= 2:
                sink_id = parts[1]
                for ln in (sinks or "").splitlines():
                    p = ln.split()
                    if len(p) >= 2 and p[0] == sink_id and _sink_is_hdmi(p[1]):
                        err(f"  ⚠ Sink-Input {parts[0]} läuft auf HDMI-Sink! → kein Ton auf Klinke")
    else:
        warn("Keine aktiven Sink-Inputs — kein Audio läuft gerade")

    # Audio-State
    state_file = "/tmp/pidrive_audio_state.json"
    state = {}
    if os.path.exists(state_file):
        try:
            state = _read_json(state_file, {})
            eff  = state.get("effective", "?")
            req  = state.get("requested", "?")
            rsn  = state.get("reason", "?")
            sink = state.get("sink", "?")
            ok(f"Audio-State: requested={req} effective={eff} reason={rsn}")
            if eff == "klinke" and sink and _sink_is_hdmi(sink):
                err(f"  ⚠ WIDERSPRUCH: effective=klinke aber sink={sink} ist HDMI!")
            elif eff == "klinke" and sink and not _sink_is_hdmi(sink):
                ok(f"  Sink={sink} ist Klinke ✓")
        except Exception as e:
            warn(f"Audio-State: Lesefehler ({e})")
    else:
        warn("Audio-State-Datei fehlt (/tmp/pidrive_audio_state.json)")

    # Runtime-Sink / Verifikation
    try:
        rs = state.get("runtime_sink", "")
        vk = state.get("verify_ok", None)
        vr = state.get("verify_reason", "")
        if rs:
            nfo(f"Runtime Sink: {rs}")
        if vk is True:
            ok("Audio-Verifikation: OK")
        elif vk is False:
            warn(f"Audio-Verifikation: FAIL ({vr})")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Bluetooth
# ──────────────────────────────────────────────────────────────────────────────

def check_bluetooth():
    """
    Bluetooth-Diagnose mit Agent-Status, bekannten Geräten und BR/EDR-Hinweisen.
    """
    S("BLUETOOTH")
    PA = "PULSE_SERVER=unix:/var/run/pulse/native "

    bt_state = run("systemctl is-active bluetooth 2>/dev/null")
    (ok if bt_state == "active" else err)(f"bluetooth.service: {bt_state}")

    rfk = run("rfkill list bluetooth 2>/dev/null")
    if rfk:
        soft = "Soft blocked: yes" in rfk
        hard = "Hard blocked: yes" in rfk
        if hard:
            err("rfkill: BT HARD BLOCKED — Hardware-Schalter oder BIOS")
        elif soft:
            err("rfkill: BT SOFT BLOCKED — FIX: rfkill unblock bluetooth")
        else:
            ok("rfkill: BT nicht blockiert ✓")
    else:
        nfo("rfkill: kein BT-Eintrag (normal wenn Dongle noch nicht bereit)")

    hci = run("hciconfig hci0 2>/dev/null")
    if hci:
        up = "UP RUNNING" in hci
        (ok if up else warn)(f"hci0: {'UP RUNNING ✓' if up else 'DOWN — FIX: hciconfig hci0 up'}")
        for ln in hci.splitlines():
            if "LMP Version" in ln or "HCI Version" in ln:
                nfo(f"  Controller: {ln.strip()}")
    else:
        err("hci0 nicht gefunden — BT-Dongle fehlt oder Treiber-Problem")

    btmgmt = run("btmgmt info 2>/dev/null")
    if btmgmt:
        low = btmgmt.lower()
        has_bredr = ("bredr" in low or "br/edr" in low or
                     ("current settings:" in low and "bredr" in low))
        has_le = ("low energy" in low or
                  ("current settings:" in low and "le" in low) or
                  " le " in f" {low} ")
        if has_bredr:
            ok("Controller: BR/EDR (Classic BT) unterstützt ✓ — A2DP möglich")
        else:
            err("Controller: kein BR/EDR — A2DP NICHT möglich (Headphones benötigen Classic BT!)")
        if has_le:
            nfo("Controller: BLE unterstützt (für PiDrive irrelevant — A2DP nutzt Classic)")
    else:
        nfo("btmgmt nicht verfügbar — Controller-Features unbekannt")

    sys_pa = "/etc/pulse/system.pa"
    if os.path.exists(sys_pa):
        with open(sys_pa) as f:
            spa = f.read()
        has_discover = "module-bluetooth-discover" in spa
        has_policy   = "module-bluetooth-policy" in spa
        if has_discover:
            ok("system.pa: module-bluetooth-discover ✓")
        else:
            err("system.pa: module-bluetooth-discover FEHLT — BT A2DP wird nie als Sink geladen!")
        if has_policy:
            ok("system.pa: module-bluetooth-policy ✓")
        else:
            warn("system.pa: module-bluetooth-policy fehlt — Auto-Switching evtl. deaktiviert")
    else:
        warn("system.pa: /etc/pulse/system.pa nicht gefunden")

    pa_modules = run(PA + "pactl list modules short 2>/dev/null")
    if pa_modules:
        for mod in ["module-bluetooth-discover", "module-bluetooth-policy"]:
            loaded = mod in pa_modules
            (ok if loaded else warn)(
                f"PulseAudio: {mod} {'geladen ✓' if loaded else 'NICHT geladen'}"
            )
    else:
        warn("PulseAudio: Modulliste nicht abrufbar")

    paired = run("bluetoothctl paired-devices 2>/dev/null")
    if paired:
        ok(f"Gepaarte Geräte: {len(paired.splitlines())}")
        for l in paired.splitlines():
            nfo(f"  {l}")
    else:
        warn("Keine gepaarten Geräte in BlueZ-Datenbank")
        warn("  → Gerät muss neu gepairt werden (Kopfhörer in Pairing-Modus!)")

    try:
        sett = _read_json(os.path.join(os.path.dirname(__file__), "config", "settings.json"), {})
        last_mac  = sett.get("bt_last_mac", "")
        last_name = sett.get("bt_last_name", "")
        if last_mac:
            nfo(f"  Letztes Gerät (settings.json): {last_name} [{last_mac}]")
            bt_dir = "/var/lib/bluetooth"
            found_in_db = False
            if os.path.isdir(bt_dir):
                for adapter in os.listdir(bt_dir):
                    dev_path = os.path.join(bt_dir, adapter, last_mac)
                    if os.path.isdir(dev_path):
                        info_file = os.path.join(dev_path, "info")
                        if os.path.isfile(info_file):
                            found_in_db = True
                            info_content = open(info_file).read()
                            has_key = "[LinkKey]" in info_content or "[LongTermKey]" in info_content
                            (ok if has_key else warn)(
                                f"  BlueZ-DB: {last_name} — "
                                f"{'Pairing-Key vorhanden ✓' if has_key else 'KEIN Pairing-Key — muss neu gepairt werden'}"
                            )
            if not found_in_db:
                err(f"  BlueZ-DB: {last_name} [{last_mac}] NICHT in /var/lib/bluetooth/")
                err("    → Gerät wurde entfernt oder DB ist leer — Pairing nötig")
                backup_dir = os.path.join(os.path.dirname(__file__), "config", "bt_pairs")
                if os.path.isdir(backup_dir) and any(os.walk(backup_dir)):
                    warn("    → Backup vorhanden: 'BT Restore' im WebUI versuchen")
                else:
                    warn("    → Kein Backup vorhanden — Kopfhörer in Pairing-Modus bringen und neu pairen")
    except Exception as e:
        nfo(f"  settings.json: {e}")

    # Persistenter BT-Agent Status
    agentf = "/tmp/pidrive_bt_agent.json"
    if os.path.exists(agentf):
        try:
            ag = _read_json(agentf, {})
            if ag.get("running"):
                ok(f"BT-Agent Session: running pid={ag.get('pid', 0)}")
                nfo(f"ready={ag.get('ready')} health_ok={ag.get('health_ok')}")
                if ag.get("last_error"):
                    nfo(f"last_error={ag.get('last_error')}")
            else:
                warn(f"BT-Agent Session: nicht aktiv ({ag.get('last_error','')})")
        except Exception as e:
            warn(f"BT-Agent-Status: Lesefehler ({e})")

    # Bekannte Geräte
    knownf = "/tmp/pidrive_bt_known_devices.json"
    if os.path.exists(knownf):
        try:
            kd = _read_json(knownf, {})
            devs = kd.get("devices", [])
            if devs:
                ok(f"Bekannte BT-Geräte: {len(devs)}")
                for d in devs[:10]:
                    nfo(f"  {d.get('name','?')} [{d.get('mac','?')}] paired={d.get('paired',False)}")
            else:
                warn("Bekannte BT-Geräte: leer")
        except Exception as e:
            warn(f"Bekannte BT-Geräte: Lesefehler ({e})")

    bt_sinks = run(PA + "pactl list sinks short 2>/dev/null")
    if bt_sinks:
        a2dp = [l for l in bt_sinks.splitlines() if "bluez" in l.lower()]
        if a2dp:
            ok(f"BT A2DP Sink aktiv: {a2dp[0][:80]} ✓")
        else:
            nfo("Kein BT A2DP Sink aktiv (normal wenn kein BT verbunden)")
    else:
        nfo("PulseAudio Sinks nicht abrufbar")

    nfo("Hinweis: BT-Scan scannt Classic BR/EDR UND BLE gleichzeitig")
    nfo("  BLE-Geräte haben (random) MACs und sind für A2DP-Audio irrelevant")
    nfo("  Nur Geräte mit (public) MAC und Audio-Klasse können Kopfhörer sein")


# ──────────────────────────────────────────────────────────────────────────────
# RTL-SDR / Prozesse / Source-State / SDL
# ──────────────────────────────────────────────────────────────────────────────

def check_rtlsdr():
    S("RTL-SDR")
    found = any(x in run("lsusb 2>/dev/null") for x in ["0bda:2838", "RTL2838", "RTL2832"])
    (ok if found else warn)(f"RTL-SDR USB: {'erkannt ✓' if found else 'NICHT erkannt'}")
    if not found:
        warn("→ Stick abziehen und neu einstecken, dann RTL-SDR Reset im WebUI")

    for tool in ["rtl_fm", "rtl_test", "welle-cli"]:
        p = run(f"which {tool} 2>/dev/null")
        (ok if p else err)(f"{tool}: {p if p else 'FEHLT'}")

    state_file = "/tmp/pidrive_rtlsdr.json"
    if os.path.exists(state_file):
        try:
            state = _read_json(state_file, {})
            busy = state.get("busy", False)
            procs = state.get("processes", [])
            (ok if not busy else warn)(f"RTL-SDR busy: {busy} | Prozesse: {len(procs)}")
        except Exception as e:
            warn(f"RTL-SDR State: Lesefehler ({e})")
    else:
        nfo("Kein RTL-SDR State File — normal beim Start")

    settings_file = "/home/pi/pidrive/pidrive/config/settings.json"
    if os.path.exists(settings_file):
        try:
            sett = _read_json(settings_file, {})
            nfo(
                f"Settings: fm_gain={sett.get('fm_gain',-1)} "
                f"dab_gain={sett.get('dab_gain',-1)} "
                f"ppm={sett.get('ppm_correction',0)} "
                f"squelch={sett.get('scanner_squelch',25)}"
            )
        except Exception:
            pass


def check_processes():
    S("RELEVANTE PROZESSE")
    cmd = (
        r"ps ax -o pid=,user=,cmd= | egrep "
        r"'pidrive|rtl_fm|welle-cli|rtl_test|mpv|librespot|pulseaudio|pipewire|bluetoothd' "
        r"| grep -v grep"
    )
    out = run(cmd)
    if out:
        ok("Relevante Prozesse gefunden:")
        for ln in out.splitlines():
            nfo(ln[:140])
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
                    age = time.time() - float(since)
                    nfo(f"transition_age: {age:.1f}s")
                except Exception:
                    pass
            if tr:
                warn(f"Transition läuft: owner={owner}")
            if bp == "cold_start":
                warn("boot_phase=cold_start — Core evtl. nicht synchron (Shared-State fehlt?)")

            try:
                af = "/tmp/pidrive_audio_state.json"
                if os.path.exists(af):
                    ad = _read_json(af, {})
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


def test_sdl():
    S("SDL DISPLAY TEST (fb1)")
    try:
        import pygame
        os.environ["SDL_VIDEODRIVER"] = "fbcon"
        os.environ["SDL_FBDEV"] = "/dev/fb1"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        os.environ["SDL_VIDEO_FBCON_KEEP_TTY"] = "1"
        pygame.display.init()
        ok(f"pygame.display.init() OK — Treiber: {pygame.display.get_driver()}")
        pygame.display.quit()
    except Exception as e:
        err(f"pygame auf fb1 FEHLER: {e}")


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
    for r, l in checks:
        (ok if r else err)(l)
        if not r:
            all_core_ok = False

    (ok if disp_ok else warn)(f"pidrive_display.service {'laeuft' if disp_ok else 'inaktiv (optional)'}")

    if all_core_ok:
        print("\n  ✓ Core laeuft korrekt")
        if not disp_ok:
            print("  ⚠ Display inaktiv — teste fb1 direkt")
    else:
        print("\n  ✗ Probleme vorhanden — siehe Details oben")


def main():
    print(f"\n{'='*50}\n  PiDrive Diagnose v0.9.24\n{'='*50}")
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
        print("sudo python3 diagnose.py")
        sys.exit(1)
    main()