"""
modules/update.py - OTA Update via GitHub
PiDrive v0.6.1 — pygame-frei, Progress via IPC
"""

import subprocess
import os
import time
import log
import ipc
from ui import Item

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

    subprocess.Popen("sleep 2 && systemctl restart pidrive_core pidrive_display",
                     shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ipc.clear_progress()
    return True

def check_update_available():
    local_v  = get_local_version()
    remote_v = get_remote_version()
    if remote_v and local_v != remote_v:
        return remote_v
    return None

def build_items(screen, S, settings):
    update_available = {"v": None}

    def check_action():
        ipc.write_progress("Update", "Prüfe GitHub...", color="blue")
        remote_v = get_remote_version()
        local_v  = get_local_version()
        if remote_v is None:
            ipc.write_progress("Fehler", "Kein Internet", color="red")
        elif remote_v == local_v:
            ipc.write_progress("Aktuell", f"Version {local_v}", color="green")
        else:
            update_available["v"] = remote_v
            ipc.write_progress("Update!", f"{local_v} → {remote_v}", color="orange")
        time.sleep(2)
        ipc.clear_progress()

    def update_action():
        do_update()

    def show_version():
        local_v = get_local_version()
        ipc.write_progress("Version", f"PiDrive {local_v}", color="blue")
        time.sleep(3)
        ipc.clear_progress()

    return [
        Item("Auf Updates prüfen",
             sub=lambda: f"Neu: {update_available['v']}"
                         if update_available["v"] else "Aktuell",
             action=check_action),
        Item("Update installieren",
             sub=lambda: get_local_version(),
             action=update_action),
        Item("Version anzeigen",
             sub=lambda: get_local_version(),
             action=show_version),
    ]


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
