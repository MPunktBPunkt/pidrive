#!/usr/bin/env python3
"""
launcher.py - PiDrive TTY-Launcher v0.5.1

systemd mit PAMName=login + TTYPath=/dev/tty3 sollte stdin automatisch
auf tty3 setzen — tut es aber nicht zuverlaessig wenn tty3 beim Start
noch nicht vollstaendig bereit ist.

Loesung: tty3 explizit oeffnen und stdin uebergeben.
Nur stdin (fd 0) wird auf tty3 gesetzt — stdout bleibt /dev/null
damit kein Text auf dem Display erscheint.

SIGHUP=SIG_IGN verhindert exit() beim VT-Wechsel.
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

def linfo(msg):  _log("INFO",  msg)
def lwarn(msg):  _log("WARN",  msg)
def lerror(msg): _log("ERROR", msg)


def main():
    linfo("=" * 50)
    linfo(f"PiDrive Launcher v0.5.1  PID={os.getpid()}  UID={os.getuid()}")

    # SIGHUP ignorieren — Sicherheitsnetz
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    linfo("  SIGHUP=SIG_IGN gesetzt")

    # ── tty3 explizit oeffnen ─────────────────────────────────────────────
    # systemd setzt stdin nicht immer auf tty3 obwohl StandardInput=tty
    # konfiguriert ist (Race Condition wenn tty3 noch nicht bereit).
    # Loesung: selbst oeffnen. NUR stdin (fd 0) — stdout bleibt /dev/null.
    try:
        fd = os.open("/dev/tty3", os.O_RDWR | os.O_NOCTTY)
        os.dup2(fd, 0)   # stdin → /dev/tty3  (fuer SDL + USB-Tastatur)
        if fd > 0:
            os.close(fd)
        linfo("  ✓ stdin → /dev/tty3")
    except OSError as e:
        lwarn(f"  ⚠ tty3 oeffnen fehlgeschlagen: {e.strerror} — weiter mit /dev/null")

    # ── Verifikation ──────────────────────────────────────────────────────
    try:
        linfo(f"  stdin (fd 0) → {os.readlink('/proc/self/fd/0')}")
    except Exception:
        pass

    # logind-Session pruefen
    try:
        import subprocess
        r = subprocess.run("loginctl | grep tty3", shell=True,
                           capture_output=True, text=True, timeout=2)
        if "tty3" in r.stdout:
            linfo("  ✓ logind-Session auf tty3 vorhanden")
        else:
            lwarn("  ⚠ Noch keine logind-Session auf tty3")
            lwarn("    (wird evtl. erst nach pygame.init() registriert)")
    except Exception:
        pass

    # ── main.py starten ───────────────────────────────────────────────────
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
