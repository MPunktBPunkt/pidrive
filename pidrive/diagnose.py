#!/usr/bin/env python3
"""diagnose.py - PiDrive System-Diagnose v0.7.10

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

def main():
    print(f"\n{'='*50}\n  PiDrive Diagnose v0.7.10\n{'='*50}")
    print(f"  Datum:  {run('date')}\n  Kernel: {run('uname -r')}")
    check_services()
    check_ipc()
    check_display_env()
    check_fbcp()
    check_fb("/dev/fb0", "fb0 (HDMI intern)")
    check_fb("/dev/fb1", "fb1 (SPI Display)")
    check_vtcon()
    check_log()
    test_sdl()
    summary()

if __name__ == "__main__":
    if os.getuid() != 0:
        print("sudo python3 diagnose.py"); sys.exit(1)
    main()
