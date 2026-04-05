"""
modules/update.py - OTA Update via GitHub
PiDrive - GPL-v3

Prueft auf neue Version, laedt Update, startet Service neu.
Funktioniert via: git pull + systemctl restart pidrive
"""

import subprocess
import os
import time
import pygame
from ui import (Item, show_message, pick_list,
                draw_rect, get_font,
                W, H, STATUS_H, C_BG, C_HEADER, C_ACCENT,
                C_WHITE, C_GRAY, C_GREEN, C_RED, C_ORANGE,
                C_DIVIDER, C_BLUE, C_SEL)
import log

INSTALL_DIR = os.path.expanduser("~/pidrive")
REPO_URL    = "https://github.com/MPunktBPunkt/pidrive"
VERSION_FILE = os.path.join(os.path.dirname(__file__), "../VERSION")
REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/pidrive/VERSION"
)

def _run(cmd, capture=False, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        if capture:
            return r.stdout.strip()
        return r.returncode == 0
    except Exception as e:
        log.error(f"Update _run Fehler: {e}")
        return "" if capture else False

def get_local_version():
    try:
        with open(VERSION_FILE) as f:
            return f.read().strip()
    except Exception:
        return "unbekannt"

def get_remote_version():
    """Aktuelle Version von GitHub holen."""
    try:
        result = _run(f"curl -sL --max-time 10 {REMOTE_VERSION_URL}", capture=True)
        return result.strip() if result else None
    except Exception:
        return None

def draw_update_screen(screen, title, lines, color=C_BLUE):
    """Update-Screen mit mehreren Zeilen."""
    screen.fill(C_BG)
    draw_rect(screen, C_HEADER, (0, 0, W, STATUS_H))
    pygame.draw.line(screen, color, (0, STATUS_H - 1), (W, STATUS_H - 1), 2)
    t = get_font(14, bold=True).render("PiDrive Update", True, C_WHITE)
    screen.blit(t, (W//2 - t.get_width()//2,
                     STATUS_H//2 - t.get_height()//2))

    # Titelbox
    box_y = STATUS_H + 20
    draw_rect(screen, (22, 24, 32), (10, box_y, W - 20, H - box_y - 10))
    pygame.draw.rect(screen, color,
                     pygame.Rect(10, box_y, W - 20, H - box_y - 10), 1)

    th = get_font(15, bold=True).render(title, True, C_WHITE)
    screen.blit(th, (W//2 - th.get_width()//2, box_y + 14))

    y = box_y + 44
    for line in lines:
        col = C_GREEN if line.startswith("✓") else \
              C_RED   if line.startswith("✗") else \
              C_ORANGE if line.startswith("→") else C_GRAY
        lbl = get_font(13).render(line[:36], True, col)
        screen.blit(lbl, (20, y))
        y += 22
    pygame.display.flip()

def do_update(screen):
    """Vollstaendiges OTA Update durchfuehren."""
    log.action("OTA Update", "gestartet")

    local_v = get_local_version()
    draw_update_screen(screen, "Update pruefen...",
                       [f"→ Lokale Version: {local_v}",
                        "→ Verbinde mit GitHub..."])
    time.sleep(1)

    # Remote Version pruefen
    remote_v = get_remote_version()
    if not remote_v:
        draw_update_screen(screen, "Fehler",
                           ["✗ Keine Verbindung zu GitHub",
                            "→ WiFi verbunden?"],
                           color=C_RED)
        log.error("OTA Update: GitHub nicht erreichbar")
        time.sleep(3)
        return False

    draw_update_screen(screen, "Versionen",
                       [f"→ Lokal:  {local_v}",
                        f"→ GitHub: {remote_v}"])
    time.sleep(1)

    if local_v == remote_v:
        draw_update_screen(screen, "Bereits aktuell",
                           [f"✓ Version {local_v}",
                            "→ Kein Update noetig"],
                           color=C_GREEN)
        log.info(f"OTA Update: bereits aktuell ({local_v})")
        time.sleep(3)
        return False

    # Update bestaetigen
    draw_update_screen(screen, f"Update verfuegbar!",
                       [f"→ {local_v}  ->  {remote_v}",
                        "",
                        "Enter = Jetzt updaten",
                        "ESC   = Abbrechen"])

    start = time.time()
    while time.time() - start < 30:
        for ev in pygame.event.get():
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    break
                elif ev.key == pygame.K_ESCAPE:
                    log.info("OTA Update: abgebrochen")
                    return False
        else:
            time.sleep(0.1)
            continue
        break

    # git pull
    draw_update_screen(screen, "Update laden...",
                       ["→ git pull von GitHub...",
                        "→ Bitte warten..."])

    result = _run(f"cd {INSTALL_DIR} && git pull", capture=True, timeout=60)

    if not result or "error" in result.lower():
        draw_update_screen(screen, "Update fehlgeschlagen",
                           [f"✗ git pull Fehler",
                            "→ Manuell pruefen"],
                           color=C_RED)
        log.error(f"OTA Update: git pull fehlgeschlagen: {result}")
        time.sleep(4)
        return False

    log.info(f"OTA Update: erfolgreich {local_v} -> {remote_v}")

    draw_update_screen(screen, "Update erfolgreich!",
                       [f"✓ Version {remote_v} installiert",
                        "→ Service wird neugestartet...",
                        "→ Bitte warten (5s)"],
                       color=C_GREEN)
    time.sleep(3)

    # Service neu starten
    subprocess.Popen("sleep 2 && systemctl restart pidrive",
                     shell=True,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return True

def check_update_available():
    """Schneller Check ob Update verfuegbar (fuer Statusanzeige)."""
    local_v  = get_local_version()
    remote_v = get_remote_version()
    if remote_v and local_v != remote_v:
        return remote_v
    return None

def build_items(screen, S, settings):
    """Update-Untermenue-Items."""

    update_available = {"v": None}  # Mutable fuer lambda

    def check_action():
        show_message(screen, "Update", "Prueffe GitHub...", color=C_BLUE)
        remote_v = get_remote_version()
        local_v  = get_local_version()
        if remote_v is None:
            show_message(screen, "Fehler", "Kein Internet", color=C_RED)
        elif remote_v == local_v:
            show_message(screen, "Aktuell", f"Version {local_v}", color=C_GREEN)
        else:
            update_available["v"] = remote_v
            show_message(screen, "Update!", f"{local_v} -> {remote_v}", color=C_ORANGE)
        time.sleep(2)

    def update_action():
        do_update(screen)

    def show_version():
        local_v = get_local_version()
        show_message(screen, "Version", f"PiDrive {local_v}", color=C_BLUE)
        time.sleep(3)

    items = [
        Item("Auf Updates pruefen",
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
    return items
