#!/usr/bin/env python3
"""
launcher.py - PiDrive Launcher v0.5.7

Radikal vereinfacht. Kein TIOCSCTTY, kein setsid.

Warum TIOCSCTTY entfernt:
- Mit TIOCSCTTY denkt SDL es ist auf VT3
- SDL ruft VT_SETMODE(VT_PROCESS) + VT_WAITACTIVE(3) auf
- VT3 ist nicht foreground -> Deadlock, set_mode() haengt ewig
- Ohne TIOCSCTTY: SDL oeffnet /dev/tty0, erkennt aktiven VT (z.B. VT2)
- VT_WAITACTIVE(2) kehrt sofort zurueck -> kein Hang

Tastaturinput:
- pygame liest Keyboard-Events via SDL VT-Management (raw mode auf dem aktiven VT)
- stdin muss KEINE TTY sein - pygame braucht das nicht

Einzige Aufgabe: SIGHUP ignorieren, dann main.py starten.
"""

import os
import sys
import signal
from datetime import datetime

LOG_FILE = "/var/log/pidrive/pidrive.log"

def _log(level, msg):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [LAUNCH/{level}] {msg}\n"
    sys.stderr.write(line)
    try:
        os.makedirs("/var/log/pidrive", exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        pass

def linfo(msg): _log("INFO",  msg)
def lwarn(msg): _log("WARN",  msg)
def lerror(msg): _log("ERROR", msg)


def main():
    linfo("=" * 50)
    linfo(f"PiDrive Launcher v0.5.5  PID={os.getpid()}  UID={os.getuid()}")

    # SIGHUP ignorieren — SDL sendet HUP bei VT-Events
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    linfo("  SIGHUP=SIG_IGN")

    # Aktiven VT loggen (info only)
    try:
        active = open("/sys/class/tty/tty0/active").read().strip()
        linfo(f"  Aktiver VT: {active} (SDL wird diesen VT verwenden)")
    except Exception:
        pass

    # main.py starten — SDL erkennt automatisch den aktiven VT
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
        lerror(f"Launcher Fehler: {e}\n{traceback.format_exc()}")
        sys.exit(1)
