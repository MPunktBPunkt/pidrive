#!/usr/bin/env python3
"""
launcher.py - PiDrive TTY-Launcher v0.5.0

v0.5.0: Stark vereinfacht dank PAMName=login im Service.
systemd erzeugt eine echte logind-Session auf VT3 — kein manuelles
TIOCSCTTY, setsid() oder VT_ACTIVATE noetig. SDL bekommt den VT
sauber uebergeben.

SIGHUP=SIG_IGN bleibt als Sicherheitsnetz.
"""

import os
import sys
import signal
from datetime import datetime

# ── Minimales Logging (vor main.py Import) ──────────────────────────────────

LOG_FILE = "/var/log/pidrive/pidrive.log"

def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _log(level, msg):
    line = f"{_ts()} [LAUNCH/{level}] {msg}\n"
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


# ── Start ────────────────────────────────────────────────────────────────────

def main():
    linfo("=" * 50)
    linfo("PiDrive Launcher v0.5.0 gestartet")
    linfo(f"  PID: {os.getpid()}, UID: {os.getuid()}")

    # SIGHUP ignorieren — Sicherheitsnetz falls Kernel HUP sendet
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    linfo("  SIGHUP=SIG_IGN gesetzt")

    # Kontext von systemd pruefen (PAMName=login erzeugt logind-Session)
    try:
        import subprocess
        r = subprocess.run("loginctl | grep tty3", shell=True,
                           capture_output=True, text=True, timeout=2)
        if "tty3" in r.stdout:
            linfo("  ✓ logind-Session auf tty3 vorhanden (PAMName=login OK)")
        else:
            lwarn("  ⚠ Keine logind-Session auf tty3 — PAMName=login im Service pruefen!")
    except Exception:
        pass

    # stdin pruefen
    try:
        stdin_target = os.readlink("/proc/self/fd/0")
        linfo(f"  stdin → {stdin_target}")
    except Exception:
        pass

    # main.py starten — erbt den kompletten systemd/logind Kontext
    here   = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "main.py")

    if not os.path.exists(target):
        lerror(f"main.py nicht gefunden: {target}")
        sys.exit(1)

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
        lerror(f"Launcher Fehler: {e}")
        lerror(traceback.format_exc())
        sys.exit(1)
