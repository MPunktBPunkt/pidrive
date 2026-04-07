#!/usr/bin/env python3
"""
launcher.py - PiDrive TTY-Launcher v0.3.7
Richtet /dev/tty3 als Controlling Terminal ein und startet main.py.
Laeuft als root via systemd, gibt tty3-Kontext an main.py weiter.

Log: /var/log/pidrive/pidrive.log  (und journalctl -u pidrive)
"""

import os
import sys
import fcntl
import termios
import subprocess
import stat
import grp
import pwd
from datetime import datetime

# ── Logging (vor log.py Import, da das erst in main.py initialisiert wird) ──

LOG_FILE = "/var/log/pidrive/pidrive.log"

def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _write(level, msg):
    line = f"{_ts()} [LAUNCH/{level}] {msg}\n"
    sys.stderr.write(line)          # → journalctl -u pidrive
    try:
        os.makedirs("/var/log/pidrive", exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception:
        pass

def linfo(msg):  _write("INFO",  msg)
def lwarn(msg):  _write("WARN",  msg)
def lerror(msg): _write("ERROR", msg)


# ── Berechtigungs-Check ──────────────────────────────────────────────────────

def check_permissions():
    """Prueft alle notwendigen Berechtigungen und loggt Details."""
    linfo("=" * 50)
    linfo("PiDrive Launcher gestartet")
    linfo(f"  Python:  {sys.version.split()[0]}")
    linfo(f"  PID:     {os.getpid()}")
    linfo(f"  UID:     {os.getuid()} ({_uid_name(os.getuid())})")
    linfo(f"  GID:     {os.getgid()}")
    linfo(f"  Gruppen: {_group_names()}")
    linfo("=" * 50)

    ok = True

    # /dev/fb0
    linfo("--- Berechtigungs-Check ---")
    _check_device("/dev/fb0",  need_rw=True,  label="Framebuffer")

    # /dev/tty3
    tty_ok = _check_device("/dev/tty3", need_rw=True, label="TTY3")
    if not tty_ok:
        ok = False
        lerror("  Fix: sudo chmod 660 /dev/tty3")
        lerror("       oder udev-Regel: KERNEL==\"tty3\", MODE=\"0660\"")

    # stdin
    try:
        stdin_target = os.readlink("/proc/self/fd/0")
    except Exception:
        stdin_target = "unbekannt"
    linfo(f"  stdin (fd 0) -> {stdin_target}")

    # aktives VT
    try:
        r = subprocess.run("fgconsole", shell=True,
                           capture_output=True, text=True, timeout=2)
        vt = r.stdout.strip()
        if vt == "3":
            linfo(f"  ✓ Aktives VT: tty{vt}")
        else:
            lwarn(f"  ⚠ Aktives VT: tty{vt} (erwartet 3) — chvt 3 folgt")
    except Exception:
        lwarn("  ⚠ fgconsole nicht verfuegbar")

    linfo(f"--- Berechtigungs-Check {'OK' if ok else 'FEHLER'} ---")
    return ok

def _check_device(path, need_rw, label):
    """Prueft ein Device und gibt True zurueck wenn alles OK."""
    if not os.path.exists(path):
        lerror(f"  ✗ {label} ({path}) fehlt!")
        return False
    try:
        s = os.stat(path)
        mode_oct  = oct(s.st_mode)[-4:]
        mode_str  = _mode_str(s.st_mode)
        owner     = _uid_name(s.st_uid)
        group     = _gid_name(s.st_gid)
        linfo(f"  ✓ {label}: {path}  [{mode_str} {owner}:{group} ({mode_oct})]")
    except Exception as e:
        lwarn(f"  ⚠ {label}: stat fehler: {e}")

    # O_RDWR oeffnen testen
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
        os.close(fd)
        linfo(f"  ✓ {label}: O_RDWR erfolgreich")
        return True
    except OSError as e:
        lerror(f"  ✗ {label}: O_RDWR fehlgeschlagen: {e.strerror} (errno {e.errno})")
        return False

def _uid_name(uid):
    try:    return pwd.getpwuid(uid).pw_name
    except: return str(uid)

def _gid_name(gid):
    try:    return grp.getgrgid(gid).gr_name
    except: return str(gid)

def _group_names():
    try:
        return ", ".join(_gid_name(g) for g in os.getgroups())
    except:
        return "unbekannt"

def _mode_str(mode):
    """z.B. 'crw-rw----'"""
    chars = ["c" if stat.S_ISCHR(mode) else
             "b" if stat.S_ISBLK(mode) else "-"]
    for who in [(stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
                (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
                (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH)]:
        chars += ["r" if mode & who[0] else "-",
                  "w" if mode & who[1] else "-",
                  "x" if mode & who[2] else "-"]
    return "".join(chars)


# ── Controlling Terminal einrichten ─────────────────────────────────────────

TTY = "/dev/tty3"

def setup_tty():
    """
    Richtet /dev/tty3 als Controlling Terminal ein.
    Danach zeigt open('/dev/tty') auf /dev/tty3 — genau was SDL/fbcon braucht.
    """
    linfo("--- TTY Setup ---")

    # chvt 3 — VT3 in den Vordergrund
    try:
        r = subprocess.run(["/bin/chvt", "3"], timeout=3)
        if r.returncode == 0:
            linfo("  ✓ chvt 3 OK")
        else:
            lwarn(f"  ⚠ chvt 3 returncode: {r.returncode}")
    except Exception as e:
        lwarn(f"  ⚠ chvt 3 fehler: {e}")

    # /dev/tty3 oeffnen (O_NOCTTY = noch NICHT als ctty setzen)
    try:
        fd = os.open(TTY, os.O_RDWR | os.O_NOCTTY)
        linfo(f"  ✓ {TTY} geoeffnet (fd={fd})")
    except OSError as e:
        lerror(f"  ✗ {TTY} oeffnen fehlgeschlagen: {e.strerror}")
        lerror("    Launcher kann nicht fortfahren.")
        sys.exit(1)

    # Neue Session — macht diesen Prozess zum Session-Leader
    try:
        os.setsid()
        linfo(f"  ✓ setsid() OK (neue Session, SID={os.getsid(0)})")
    except OSError as e:
        lwarn(f"  ⚠ setsid() fehlgeschlagen: {e} (evtl. bereits Session-Leader)")

    # TIOCSCTTY — tty3 als Controlling Terminal registrieren
    # Danach: open("/dev/tty") == /dev/tty3
    try:
        fcntl.ioctl(fd, termios.TIOCSCTTY, 1)
        linfo(f"  ✓ TIOCSCTTY: {TTY} ist jetzt Controlling Terminal")
    except OSError as e:
        lerror(f"  ✗ TIOCSCTTY fehlgeschlagen: {e.strerror} (errno {e.errno})")
        lerror("    SDL wird 'Unable to open a console terminal' melden.")
        os.close(fd)
        sys.exit(1)

    # stdin auf tty3 — fuer USB-Tastatur-Input
    os.dup2(fd, 0)
    linfo(f"  ✓ stdin → {TTY}")

    if fd > 0:
        os.close(fd)

    # Verifikation
    try:
        ctty = os.readlink("/proc/self/fd/0")
        linfo(f"  ✓ /proc/self/fd/0 → {ctty}")
    except Exception:
        pass

    linfo("--- TTY Setup OK ---")


# ── main.py starten ──────────────────────────────────────────────────────────

def launch():
    here   = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "main.py")

    if not os.path.exists(target):
        lerror(f"main.py nicht gefunden: {target}")
        sys.exit(1)

    linfo(f"Starte: {sys.executable} {target}")
    linfo("=" * 50)

    # execv ersetzt diesen Prozess — main.py erbt den tty3-Kontext
    os.execv(sys.executable, [sys.executable, target])


# ── Einstiegspunkt ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        perm_ok = check_permissions()
        if not perm_ok:
            lwarn("Berechtigungsfehler erkannt — versuche trotzdem fortzufahren")
        setup_tty()
        launch()
    except KeyboardInterrupt:
        linfo("Launcher abgebrochen (KeyboardInterrupt)")
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        lerror(f"Unbehandelter Fehler im Launcher: {e}")
        lerror(traceback.format_exc())
        sys.exit(1)
