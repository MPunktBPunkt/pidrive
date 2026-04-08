#!/usr/bin/env python3
"""
diagnose.py - PiDrive System-Diagnose
Zeigt live den Status von VT, Framebuffer, SDL, fbcp und Service.

Aufruf:
  sudo python3 ~/pidrive/pidrive/diagnose.py
"""

import os
import subprocess
import fcntl
import sys
import time

VT_ACTIVATE   = 0x5606
VT_WAITACTIVE = 0x5607

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)

def ok(msg):   print(f"  ✓ {msg}")
def warn(msg): print(f"  ⚠ {msg}")
def err(msg):  print(f"  ✗ {msg}")

# ── VT Status ─────────────────────────────────────────────────────────────────

def check_vt():
    section("VT STATUS")
    fg = run("fgconsole")
    if fg == "3":
        ok(f"Aktives VT: {fg} (korrekt)")
    else:
        err(f"Aktives VT: {fg} (erwartet 3) — SDL VT_WAITACTIVE haengt!")

    sessions = run("loginctl list-sessions 2>/dev/null")
    print(f"  loginctl sessions:")
    for line in sessions.splitlines():
        print(f"    {line}")

    # Gibt es eine Session auf tty3?
    if "tty3" in sessions:
        ok("logind-Session auf tty3 gefunden")
    else:
        warn("Keine logind-Session auf tty3 — TTYPath=/dev/tty3 im Service noetig")

# ── Framebuffer ───────────────────────────────────────────────────────────────

def check_fb(path, name):
    section(f"FRAMEBUFFER {name} ({path})")
    if not os.path.exists(path):
        err(f"{path} fehlt")
        return
    try:
        import stat as stat_mod
        s = os.stat(path)
        mode = oct(s.st_mode)[-4:]
        print(f"  Permissions: {stat_mod.filemode(s.st_mode)} ({mode})")

        with open(path, "rb") as f:
            raw = f.read()
        nz  = sum(1 for b in raw if b != 0)
        pct = nz * 100 // len(raw) if raw else 0
        print(f"  Groesse:     {len(raw)} Bytes ({len(raw)//(640*4)} Zeilen)")
        print(f"  Non-zero:    {nz} Bytes ({pct}%)")
        print(f"  Erste 16:    {list(raw[:16])}")
        if pct > 5:
            ok(f"{name} hat Inhalt ({pct}% non-zero) — pygame zeichnet")
        elif pct > 0:
            warn(f"{name} hat wenig Inhalt ({pct}%) — evtl. nur Cursor")
        else:
            err(f"{name} ist komplett schwarz — pygame zeichnet nicht auf {path}")
    except Exception as e:
        err(f"Lesefehler: {e}")

# ── fbcp ──────────────────────────────────────────────────────────────────────

def check_fbcp():
    section("FBCP")
    result = run("pgrep -a fbcp")
    if result:
        ok(f"fbcp laeuft: {result}")
    else:
        err("fbcp laeuft NICHT — SPI Display bleibt dunkel")
        warn("Fix: fbcp &")

# ── pidrive Service ───────────────────────────────────────────────────────────

def check_service():
    section("PIDRIVE SERVICE")
    status = run("systemctl is-active pidrive")
    if status == "active":
        ok("pidrive.service: active (running)")
    else:
        err(f"pidrive.service: {status}")

    pid = run("systemctl show pidrive --property=MainPID --value")
    if pid and pid != "0":
        ok(f"PID: {pid}")
        # stdin des Prozesses prüfen
        try:
            stdin = os.readlink(f"/proc/{pid}/fd/0")
            ok(f"stdin → {stdin}")
        except Exception:
            warn("stdin nicht lesbar")

    # TTY-Konfiguration aus Service-Datei
    tty_cfg = run("grep -E 'TTYPath|StandardInput|PAMName' /etc/systemd/system/pidrive.service 2>/dev/null")
    if "TTYPath=/dev/tty3" in tty_cfg:
        ok("TTYPath=/dev/tty3 konfiguriert")
    else:
        err("TTYPath=/dev/tty3 fehlt! logind-Session wird nicht erzeugt.")
        err("Fix: TTYPath=/dev/tty3 in pidrive.service hinzufuegen")
    print(f"  TTY-Config: {tty_cfg.replace(chr(10), ' | ')}")

# ── VT Aktivierungstest ───────────────────────────────────────────────────────

def test_vt_activate():
    section("VT3 AKTIVIERUNGSTEST")
    try:
        fd = os.open("/dev/tty0", os.O_WRONLY | os.O_NOCTTY)
        fcntl.ioctl(fd, VT_ACTIVATE, 3)
        os.close(fd)
        ok("VT_ACTIVATE(3) abgeschickt")
        time.sleep(0.5)
        fg = run("fgconsole")
        if fg == "3":
            ok(f"VT3 ist jetzt foreground — VT-Wechsel funktioniert!")
        else:
            err(f"VT3 immer noch nicht foreground (fgconsole={fg})")
            err("logind blockiert VT-Wechsel — TTYPath im Service noetig")
    except Exception as e:
        err(f"VT_ACTIVATE fehlgeschlagen: {e}")

# ── SDL Test ──────────────────────────────────────────────────────────────────

def test_sdl():
    section("SDL DISPLAY TEST")
    try:
        import pygame
        os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
        os.environ.setdefault("SDL_FBDEV",       "/dev/fb0")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.display.init()
        drv = pygame.display.get_driver()
        ok(f"pygame.display.init() OK — Treiber: {drv}")
        pygame.display.quit()
    except Exception as e:
        err(f"pygame.display.init() FEHLER: {e}")

# ── Gettys ────────────────────────────────────────────────────────────────────

def check_gettys():
    section("GETTY STATUS")
    for tty in ("tty1", "tty2", "tty3"):
        status = run(f"systemctl is-active getty@{tty}.service 2>/dev/null")
        masked = run(f"systemctl is-enabled getty@{tty}.service 2>/dev/null")
        if status == "active":
            warn(f"getty@{tty}: active — kann VT blockieren")
        elif "masked" in masked:
            ok(f"getty@{tty}: masked (korrekt)")
        else:
            ok(f"getty@{tty}: {status}/{masked}")

# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*50)
    print("  PiDrive Diagnose")
    print("="*50)
    print(f"  Datum: {run('date')}")
    print(f"  Kernel: {run('uname -r')}")

    check_vt()
    check_service()
    check_gettys()
    check_fbcp()
    check_fb("/dev/fb0", "fb0 (HDMI/pygame)")
    check_fb("/dev/fb1", "fb1 (SPI Display)")
    test_vt_activate()
    test_sdl()

    section("ZUSAMMENFASSUNG")
    fg = run("fgconsole")
    sessions = run("loginctl list-sessions 2>/dev/null")
    service  = run("systemctl is-active pidrive")
    fbcp_ok  = bool(run("pgrep fbcp"))
    tty_ok   = "TTYPath=/dev/tty3" in run(
        "grep TTYPath /etc/systemd/system/pidrive.service 2>/dev/null")

    all_ok = True
    checks = [
        (fg == "3",    "VT3 foreground"),
        ("tty3" in sessions, "logind-Session auf tty3"),
        (service == "active", "pidrive.service laeuft"),
        (fbcp_ok,    "fbcp laeuft"),
        (tty_ok,     "TTYPath=/dev/tty3 im Service"),
    ]
    for result, label in checks:
        if result:
            ok(label)
        else:
            err(label)
            all_ok = False

    if all_ok:
        print("\n  ✓✓✓ Alles korrekt konfiguriert ✓✓✓")
    else:
        print("\n  ✗ Probleme gefunden — siehe Details oben")

if __name__ == "__main__":
    if os.getuid() != 0:
        print("Bitte als root ausfuehren: sudo python3 diagnose.py")
        sys.exit(1)
    main()
