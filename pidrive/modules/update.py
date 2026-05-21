"""
modules/update.py - OTA Update via GitHub
PiDrive v0.6.1 — pygame-frei, Progress via IPC
"""

import subprocess
import os
import time
import log
import ipc

INSTALL_DIR        = os.path.expanduser("~/pidrive")
REPO_URL           = "https://github.com/MPunktBPunkt/pidrive"
VERSION_FILE       = os.path.join(os.path.dirname(__file__), "../VERSION")
REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/pidrive/VERSION"
)

def _run(cmd, capture=False, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if capture else r.returncode == 0
    except Exception as e:
        log.error(f"Update _run Fehler: {e}")
        return "" if capture else False

def get_local_version():
    try:
        return open(VERSION_FILE).read().strip()
    except Exception:
        return "unbekannt"

def get_remote_version():
    try:
        r = _run(f"curl -sL --max-time 10 {REMOTE_VERSION_URL}", capture=True)
        return r.strip() if r else None
    except Exception:
        return None

def do_update():
    """OTA Update ohne Display-Abhaengigkeit."""
    log.action("OTA Update", "gestartet")
    local_v = get_local_version()

    ipc.write_progress("Update prüfen",
                       f"Lokale Version: {local_v}", color="blue")
    time.sleep(1)

    remote_v = get_remote_version()
    if not remote_v:
        ipc.write_progress("Fehler", "Keine Verbindung zu GitHub", color="red")
        log.error("OTA Update: GitHub nicht erreichbar")
        time.sleep(3)
        ipc.clear_progress()
        return False

    ipc.write_progress("Versionen",
                       lines=[f"Lokal:  {local_v}", f"GitHub: {remote_v}"])
    time.sleep(1)

    if local_v == remote_v:
        ipc.write_progress("Bereits aktuell",
                           f"Version {local_v}", color="green")
        log.info(f"OTA Update: bereits aktuell ({local_v})")
        time.sleep(3)
        ipc.clear_progress()
        return False

    ipc.write_progress("Update verfügbar",
                       lines=[f"{local_v}  →  {remote_v}",
                               "Starte Update..."],
                       color="orange")
    time.sleep(2)

    # git pull
    ipc.write_progress("Update laden", "git pull von GitHub...", color="blue")
    result = _run(f"cd {INSTALL_DIR} && git pull", capture=True, timeout=60)

    if not result or "error" in result.lower():
        ipc.write_progress("Fehlgeschlagen",
                           lines=["git pull Fehler", "Manuell prüfen"],
                           color="red")
        log.error(f"OTA Update: git pull fehlgeschlagen: {result}")
        time.sleep(4)
        ipc.clear_progress()
        return False

    log.info(f"OTA Update: erfolgreich {local_v} -> {remote_v}")
    ipc.write_progress("Update erfolgreich!",
                       lines=[f"Version {remote_v} installiert",
                               "Service wird neugestartet..."],
                       color="green")
    time.sleep(3)

    # Prio C: threading.Timer statt sleep&&cmd in Shell
    import threading as _upd_t
    def _delayed_restart():
        import time as _t; _t.sleep(2)
        subprocess.Popen(
            ["systemctl", "restart", "pidrive_core"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    _upd_t.Thread(target=_delayed_restart, daemon=True).start()
    ipc.clear_progress()
    return True

def check_update_available():
    local_v  = get_local_version()
    remote_v = get_remote_version()
    if remote_v and local_v != remote_v:
        return remote_v
    return None

# build_items entfernt

def run_update(S):
    """OTA Update via install.sh."""
    import subprocess, time, ipc
    ipc.write_progress("Update", "Verbinde GitHub ...", color="blue")
    try:
        result = subprocess.run(
            "curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash",
            shell=True, capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            ipc.write_progress("Update", "Erfolgreich! Neustart ...", color="green")
            time.sleep(3)
            subprocess.run(["sudo","reboot"])
        else:
            ipc.write_progress("Update Fehler", result.stderr[:48], color="red")
            time.sleep(4); ipc.clear_progress()
    except Exception as e:
        ipc.write_progress("Update", f"Fehler: {e}", color="red")
        time.sleep(4); ipc.clear_progress()


def spotify_toggle(S: dict):
    """Spotify Connect starten/stoppen (migriert aus modules/musik.py v0.11.40).
    Startet oder stoppt raspotify/librespot Service.
    """
    import subprocess as _sp
    was_active = bool(S.get("spotify"))
    try:
        if was_active:
            _sp.run(["systemctl", "stop", "raspotify"],
                    capture_output=True, timeout=5)
            S["spotify"] = False
        else:
            _sp.run(["systemctl", "start", "raspotify"],
                    capture_output=True, timeout=5)
            # Status nach 1s prüfen
            import time as _t; _t.sleep(1)
            r = _sp.run(["systemctl", "is-active", "raspotify"],
                        capture_output=True, text=True, timeout=3)
            S["spotify"] = (r.stdout.strip() == "active")
    except Exception as _e:
        import log as _log
        _log.warn(f"spotify_toggle: {_e}")
