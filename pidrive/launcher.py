#!/usr/bin/env python3
"""
launcher.py - PiDrive TTY-Launcher v0.5.4

PAMName=login haengt auf systemd 247/Bullseye (interner Helper startet nie Python).
Loesung: launcher.py richtet TTY komplett selbst ein.

Ablauf:
  1. SIGHUP=SIG_IGN (verhindert exit bei VT-Events)
  2. setsid() — neue Session, Prozess wird Session-Leader
  3. tty3 oeffnen + TIOCSCTTY — tty3 als Controlling Terminal
  4. tcsetpgrp — wir sind foreground process group
  5. stdin auf tty3 — fuer USB-Tastatur
  6. execv main.py
"""

import os
import sys
import signal
import fcntl
import termios
from datetime import datetime

LOG_FILE = "/var/log/pidrive/pidrive.log"
TTY      = "/dev/tty3"

def _log(level, msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [LAUNCH/{level}] {msg}\n"
    sys.stderr.write(line)
    try:
        os.makedirs("/var/log/pidrive", exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        pass

def linfo(msg):  _log("INFO",  msg)
def lwarn(msg):  _log("WARN",  msg)
def lerror(msg): _log("ERROR", msg)


def main():
    linfo("=" * 50)
    linfo(f"PiDrive Launcher v0.5.3  PID={os.getpid()}  UID={os.getuid()}")

    # ── 1. SIGHUP ignorieren ──────────────────────────────────────────────
    # Muss VOR setsid/TIOCSCTTY passieren — der Kernel sendet HUP beim
    # Controlling-Terminal-Wechsel. Mit SIG_IGN sterben wir nicht.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    linfo("  ✓ SIGHUP=SIG_IGN")

    # ── 2. tty3 oeffnen ───────────────────────────────────────────────────
    try:
        fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY)
        linfo(f"  ✓ {TTY} geoeffnet (fd={fd})")
    except OSError as e:
        lerror(f"  ✗ {TTY} oeffnen fehlgeschlagen: {e.strerror}")
        sys.exit(1)

    # ── 3. Neue Session ───────────────────────────────────────────────────
    try:
        os.setsid()
        linfo(f"  ✓ setsid() OK  SID={os.getsid(0)}")
    except OSError as e:
        lwarn(f"  ⚠ setsid(): {e}")

    # ── 4. TIOCSCTTY — tty3 als Controlling Terminal ──────────────────────
    try:
        fcntl.ioctl(fd, termios.TIOCSCTTY, 1)
        linfo(f"  ✓ TIOCSCTTY: {TTY} ist Controlling Terminal")
    except OSError as e:
        lerror(f"  ✗ TIOCSCTTY: {e.strerror} (errno {e.errno})")
        os.close(fd)
        sys.exit(1)

    # ── 5. foreground process group ───────────────────────────────────────
    try:
        os.tcsetpgrp(fd, os.getpgrp())
        linfo(f"  ✓ tcsetpgrp pgid={os.getpgrp()} foreground")
    except OSError as e:
        lwarn(f"  ⚠ tcsetpgrp: {e}")

    # ── 6. stdin auf tty3 ─────────────────────────────────────────────────
    os.dup2(fd, 0)
    linfo(f"  ✓ stdin → {TTY}")
    if fd > 0:
        os.close(fd)

    # Verifikation
    try:
        linfo(f"  ✓ /proc/self/fd/0 → {os.readlink('/proc/self/fd/0')}")
    except Exception:
        pass

    # logind-Session Check (info only)
    try:
        import subprocess
        r = subprocess.run("loginctl | grep tty3", shell=True,
                           capture_output=True, text=True, timeout=2)
        if "tty3" in r.stdout:
            linfo("  ✓ logind-Session auf tty3")
        else:
            linfo("  ℹ keine logind-Session (normal ohne PAMName)")
    except Exception:
        pass

    # fgconsole
    try:
        import subprocess
        r = subprocess.run("fgconsole", shell=True,
                           capture_output=True, text=True, timeout=2)
        vt = r.stdout.strip()
        (linfo if vt == "3" else lwarn)(f"  {'✓' if vt=='3' else '⚠'} Aktives VT: tty{vt}")
    except Exception:
        pass

    # ── 7. main.py starten ────────────────────────────────────────────────
    here   = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "main.py")
    if not os.path.exists(target):
        lerror(f"main.py nicht gefunden: {target}")
        sys.exit(1)

    # VT3 aktivieren direkt vor execv — via ioctl, nicht chvt (chvt haengt
    # wenn wir TIOCSCTTY gesetzt haben und SIGHUP ignorieren).
    # Beim Restart nach Crash schaltet SDL zurueck auf VT2 — dieser Fix
    # stellt sicher dass jeder Neustart auf VT3 beginnt.
    try:
        import fcntl as _fc_vt
        _fd_vt = os.open("/dev/tty0", os.O_WRONLY | os.O_NOCTTY)
        _fc_vt.ioctl(_fd_vt, 0x5606, 3)  # VT_ACTIVATE 3
        os.close(_fd_vt)
        linfo("  ✓ VT_ACTIVATE 3 (vor execv)")
    except Exception as e:
        lwarn(f"  ⚠ VT_ACTIVATE: {e}")

    linfo(f"Starte: {sys.executable} {target}")
    linfo("=" * 50)
    os.execv(sys.executable, [sys.executable, target])


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        lerror(f"Launcher Fehler: {e}\n{traceback.format_exc()}")
        sys.exit(1)
