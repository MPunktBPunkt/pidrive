#!/usr/bin/env python3
"""
main_display.py - PiDrive Display v0.6.0

Nur Anzeige — kein Audio, kein Trigger, keine Kernlogik.
Liest Status von /tmp/pidrive_status.json (geschrieben von Core).
Zeichnet direkt auf fb1 (SPI-Display, 480x320, 16bpp).
Kein fbcp noetig.

Wenn dieser Prozess haengt oder crasht:
  - Core laeuft weiter
  - Audio laeuft weiter
  - Steuerung via File-Trigger funktioniert weiter
"""

import sys
import os
import time
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# SDL direkt auf fb1 — kein HDMI, kein fbcp
os.environ["SDL_FBDEV"]              = "/dev/fb1"
os.environ["SDL_VIDEODRIVER"]        = "fbcon"
os.environ["SDL_NOMOUSE"]            = "1"
os.environ["SDL_AUDIODRIVER"]        = "dummy"
os.environ["SDL_VIDEO_FBCON_KEEP_TTY"] = "1"

import pygame
import log
import ipc

logger = log.setup()

signal.signal(signal.SIGHUP, signal.SIG_IGN)

# Display-Groesse: direkt auf SPI-Display fb1
W, H = 480, 320

# Farben
C_BG      = (20,  20,  40)
C_HEADER  = (60,  60, 120)
C_TEXT    = (220, 220, 220)
C_DIM     = (120, 120, 140)
C_ACCENT  = (100, 160, 255)
C_GREEN   = ( 80, 200,  80)
C_RED     = (200,  80,  80)
C_ORANGE  = (255, 160,  40)


def init_display():
    """Display initialisieren mit Timeout-Schutz."""
    log.info("Display: pygame.display.init() ...")
    pygame.display.init()
    pygame.font.init()
    log.info("Display: set_mode(480x320, 0, 16) ...")
    screen = pygame.display.set_mode((W, H), 0, 16)
    log.info(f"Display OK — Treiber: {pygame.display.get_driver()}")
    return screen


def load_fonts():
    try:
        font_big  = pygame.font.SysFont("DejaVuSans", 22)
        font_med  = pygame.font.SysFont("DejaVuSans", 16)
        font_sm   = pygame.font.SysFont("DejaVuSans", 13)
    except Exception:
        font_big  = pygame.font.Font(None, 26)
        font_med  = pygame.font.Font(None, 20)
        font_sm   = pygame.font.Font(None, 16)
    return font_big, font_med, font_sm


def draw_icon(screen, x, y, kind, active, font_sm):
    """Einfache Text-Icons fuer Status-Leiste."""
    color = C_GREEN if active else C_DIM
    labels = {"wifi": "W", "bt": "B", "spotify": "S"}
    txt = font_sm.render(labels.get(kind, "?"), True, color)
    screen.blit(txt, (x, y))


def render(screen, fonts, status, menu):
    """Vollstaendiger Frame."""
    font_big, font_med, font_sm = fonts
    screen.fill(C_BG)

    # ── Status-Leiste oben ──────────────────────────────────────────
    pygame.draw.rect(screen, C_HEADER, (0, 0, W, 28))

    # PiDrive Titel
    t = font_med.render("PiDrive", True, C_ACCENT)
    screen.blit(t, (8, 5))

    # Status-Icons rechts
    wifi    = status.get("wifi",    False)
    bt      = status.get("bt",      False)
    spotify = status.get("spotify", False)
    draw_icon(screen, W - 60, 6, "wifi",    wifi,    font_sm)
    draw_icon(screen, W - 44, 6, "bt",      bt,      font_sm)
    draw_icon(screen, W - 28, 6, "spotify", spotify, font_sm)

    # IP-Adresse
    ip = status.get("ip", "-")
    t = font_sm.render(ip, True, C_DIM)
    screen.blit(t, (90, 8))

    # ── Aktuelle Kategorie und Item ─────────────────────────────────
    cat_label  = menu.get("cat_label",  "")
    item_label = menu.get("item_label", "")
    radio_type = menu.get("radio_type", "")

    y = 40
    t = font_big.render(cat_label, True, C_TEXT)
    screen.blit(t, (12, y))

    y = 72
    t = font_med.render(f"  › {item_label}", True, C_ACCENT)
    screen.blit(t, (12, y))

    # ── Now Playing ─────────────────────────────────────────────────
    y = 110
    playing = False

    if status.get("spotify") and status.get("track"):
        playing = True
        track  = status.get("track",  "")[:32]
        artist = status.get("artist", "")[:28]
        t = font_sm.render("♫ Spotify", True, C_GREEN)
        screen.blit(t, (12, y)); y += 20
        t = font_med.render(track, True, C_TEXT)
        screen.blit(t, (12, y)); y += 22
        t = font_sm.render(artist, True, C_DIM)
        screen.blit(t, (12, y)); y += 20

    elif status.get("radio") and status.get("radio_name"):
        playing = True
        name = status.get("radio_name", "")[:28]
        label = {"WEB": "♪ Webradio", "DAB": "♪ DAB+",
                 "FM": "♪ FM", "SCANNER": "♪ Scanner"}.get(
                 radio_type, "♪ Radio")
        t = font_sm.render(label, True, C_ORANGE)
        screen.blit(t, (12, y)); y += 20
        t = font_med.render(name, True, C_TEXT)
        screen.blit(t, (12, y)); y += 22

    elif status.get("library") and status.get("lib_track"):
        playing = True
        track = status.get("lib_track", "")[:28]
        t = font_sm.render("♫ Bibliothek", True, C_ACCENT)
        screen.blit(t, (12, y)); y += 20
        t = font_med.render(track, True, C_TEXT)
        screen.blit(t, (12, y)); y += 22

    # ── Audioausgang ────────────────────────────────────────────────
    audio_out = status.get("audio_out", "auto")
    t = font_sm.render(f"Audio: {audio_out}", True, C_DIM)
    screen.blit(t, (12, H - 20))

    # ── Trennlinien ─────────────────────────────────────────────────
    pygame.draw.line(screen, C_HEADER, (0, 30), (W, 30), 1)
    pygame.draw.line(screen, C_HEADER, (0, H - 26), (W, H - 26), 1)

    pygame.display.flip()


def main():
    log.info("=" * 50)
    log.info("PiDrive Display v0.6.0 gestartet")
    log.info("  SDL_FBDEV=/dev/fb1 (direkt, kein fbcp)")
    log.info("=" * 50)

    try:
        screen = init_display()
    except Exception as e:
        log.error(f"Display init fehlgeschlagen: {e}")
        log.error("  Core laeuft weiter — nur Display nicht verfuegbar")
        sys.exit(1)

    fonts = load_fonts()
    clock = pygame.time.Clock()

    # Startbild
    screen.fill(C_BG)
    font_big, _, _ = fonts
    t = font_big.render("PiDrive startet...", True, C_ACCENT)
    screen.blit(t, (W//2 - t.get_width()//2, H//2 - 15))
    pygame.display.flip()

    log.info("Display-Loop gestartet")

    while True:
        # Status und Menue von Core lesen
        status = ipc.read_json(ipc.STATUS_FILE, {})
        menu   = ipc.read_json(ipc.MENU_FILE,   {})

        # Rendern
        try:
            render(screen, fonts, status, menu)
        except Exception as e:
            log.error(f"Render-Fehler: {e}")

        # Events (QUIT behandeln)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        clock.tick(10)   # 10 fps reicht fuer Status-Anzeige


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Display beendet (KeyboardInterrupt)")
        pygame.quit()
    except Exception as e:
        import traceback
        log.error(f"Display Fehler: {e}\n{traceback.format_exc()}")
        raise
