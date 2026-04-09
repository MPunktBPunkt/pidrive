#!/usr/bin/env python3
"""
main_display.py - PiDrive Display v0.6.4

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
import sys

logger = log.setup("display")

signal.signal(signal.SIGHUP, signal.SIG_IGN)

# Display-Groesse: direkt auf SPI-Display fb1
W, H = 480, 320

# Farben
C_BG        = ( 15,  15,  35)   # Dunkelblau Hintergrund
C_HEADER    = ( 40,  40,  90)   # Header-Leiste
C_LEFT_BG   = ( 25,  25,  55)   # Linke Kategorie-Spalte
C_SEL_BG    = ( 60,  80, 160)   # Ausgewaehltes Element
C_SEL_CAT   = ( 80, 100, 180)   # Ausgewaehlte Kategorie
C_TEXT      = (220, 220, 235)   # Haupttext
C_DIM       = (110, 110, 140)   # Gedaempfter Text
C_ACCENT    = ( 80, 160, 255)   # Akzentfarbe blau
C_GREEN     = ( 60, 210,  80)   # Gruen (aktiv/OK)
C_RED       = (210,  60,  60)   # Rot (Fehler)
C_ORANGE    = (255, 155,  30)   # Orange (Radio/Warnung)
C_PURPLE    = (160,  80, 220)   # Lila (Spotify)
C_DIVIDER   = ( 50,  50,  90)   # Trennlinie


def init_display():
    """Display initialisieren mit Timeout-Schutz."""
    log.info("Display: pygame.display.init() ...")
    pygame.display.init()
    pygame.font.init()
    # vtcon1 direkt vor set_mode unbinden — verhindert Rebinding durch Kernel
    try:
        with open("/sys/class/vtconsole/vtcon1/bind", "w") as _f:
            _f.write("0")
        log.info("vtcon1/bind=0 OK")
    except Exception as _e:
        log.warn(f"vtcon1 unbind: {_e}")
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


def draw_status_icons(screen, font_sm, status):
    """Status-Icons rechts im Header."""
    icons = [
        ("wifi",    "WiFi",  status.get("wifi",    False)),
        ("bt",      "BT",    status.get("bt",      False)),
        ("spotify", "Spot",  status.get("spotify", False)),
    ]
    x = W - 8
    for _, label, active in reversed(icons):
        color = C_GREEN if active else C_DIM
        t = font_sm.render(label, True, color)
        x -= t.get_width() + 6
        screen.blit(t, (x, 7))


def render(screen, fonts, status, menu):
    """Split-Screen: Links Kategorien, rechts Item-Liste + Now Playing."""
    font_big, font_med, font_sm = fonts

    # Layout
    HEADER_H  = 28
    FOOTER_H  = 24
    LEFT_W    = 110   # Kategorie-Spalte links
    CONTENT_Y = HEADER_H + 2
    CONTENT_H = H - HEADER_H - FOOTER_H - 2

    screen.fill(C_BG)

    # ── Header ──────────────────────────────────────────────────────
    pygame.draw.rect(screen, C_HEADER, (0, 0, W, HEADER_H))
    t = font_med.render("PiDrive", True, C_ACCENT)
    screen.blit(t, (8, 6))
    ip = status.get("ip", "")
    if ip and ip != "-":
        t = font_sm.render(ip, True, C_DIM)
        screen.blit(t, (80, 9))
    draw_status_icons(screen, font_sm, status)

    # ── Kategorie-Spalte links ───────────────────────────────────────
    pygame.draw.rect(screen, C_LEFT_BG, (0, CONTENT_Y, LEFT_W, CONTENT_H))

    categories = menu.get("categories", [])
    sel_cat    = menu.get("cat", 0)
    cat_colors = [C_ACCENT, (100, 180, 255), C_ORANGE, (180, 130, 255)]

    for i, cat in enumerate(categories[:8]):
        cy = CONTENT_Y + 4 + i * 36
        if i == sel_cat:
            pygame.draw.rect(screen, C_SEL_CAT, (0, cy - 2, LEFT_W, 30))
            col = (255, 255, 255)
        else:
            col = cat_colors[i % len(cat_colors)]
        # Kategorie-Kuerzel (erste 7 Zeichen)
        t = font_sm.render(cat[:9], True, col)
        screen.blit(t, (6, cy + 6))

    # Trennlinie Kategorie/Items
    pygame.draw.line(screen, C_DIVIDER, (LEFT_W, CONTENT_Y), (LEFT_W, H - FOOTER_H), 1)

    # ── Item-Liste rechts ────────────────────────────────────────────
    items    = menu.get("items", [])
    sel_item = menu.get("item", 0)
    item_x   = LEFT_W + 8
    item_w   = W - LEFT_W - 8

    # Scrolling: zeige max 7 Items, sel_item zentriert
    max_vis = 7
    row_h   = (CONTENT_H) // max_vis
    scroll  = max(0, sel_item - max_vis // 2)
    scroll  = min(scroll, max(0, len(items) - max_vis))

    for idx in range(max_vis):
        i = idx + scroll
        if i >= len(items):
            break
        iy = CONTENT_Y + idx * row_h + 2
        if i == sel_item:
            pygame.draw.rect(screen, C_SEL_BG, (LEFT_W + 1, iy, W - LEFT_W - 1, row_h - 1))
            col = (255, 255, 255)
            prefix = "›"
        else:
            col = C_TEXT
            prefix = " "
        label = items[i][:26]
        t = font_med.render(f"{prefix} {label}", True, col)
        screen.blit(t, (item_x, iy + (row_h - t.get_height()) // 2))

    # Scroll-Indikator
    if len(items) > max_vis:
        bar_h  = max(20, CONTENT_H * max_vis // max(1, len(items)))
        bar_y  = CONTENT_Y + (CONTENT_H - bar_h) * scroll // max(1, len(items) - max_vis)
        pygame.draw.rect(screen, C_DIM, (W - 5, bar_y, 4, bar_h))

    # ── Now Playing (overlay unter Items wenn aktiv) ─────────────────
    radio_type = menu.get("radio_type", "")
    np_text = ""
    np_col  = C_DIM

    if status.get("spotify") and status.get("track"):
        t = status.get("track","")[:28]
        a = status.get("artist","")[:22]
        np_text = f"♫ {a} – {t}" if a else f"♫ {t}"
        np_col  = C_PURPLE
    elif status.get("radio") and status.get("radio_name"):
        label = {"WEB":"Webradio","DAB":"DAB+","FM":"FM","SCANNER":"Scanner"}.get(radio_type,"Radio")
        np_text = f"♪ {label}: {status.get('radio_name','')[:22]}"
        np_col  = C_ORANGE
    elif status.get("library") and status.get("lib_track"):
        np_text = f"♫ {status.get('lib_track','')[:28]}"
        np_col  = C_ACCENT

    # ── Footer ──────────────────────────────────────────────────────
    footer_y = H - FOOTER_H
    pygame.draw.line(screen, C_DIVIDER, (0, footer_y), (W, footer_y), 1)
    pygame.draw.rect(screen, C_LEFT_BG, (0, footer_y + 1, W, FOOTER_H))

    if np_text:
        t = font_sm.render(np_text[:52], True, np_col)
        screen.blit(t, (8, footer_y + 5))
    else:
        audio_out = status.get("audio_out", "auto")
        t = font_sm.render(f"Audio: {audio_out}", True, C_DIM)
        screen.blit(t, (8, footer_y + 5))

    # ── Progress / Overlay ──────────────────────────────────────────
    prog = ipc.read_json(ipc.PROGRESS_FILE, {})
    if prog.get("active"):
        oy = H // 2 - 55
        pygame.draw.rect(screen, (10, 10, 30), (20, oy, W - 40, 110))
        pygame.draw.rect(screen, C_ACCENT, (20, oy, W - 40, 110), 2)
        col = {"green": C_GREEN, "red": C_RED, "orange": C_ORANGE}.get(
              prog.get("color",""), C_ACCENT)
        t = font_big.render(prog.get("title","")[:24], True, col)
        screen.blit(t, (30, oy + 10))
        t = font_med.render(prog.get("message","")[:36], True, C_TEXT)
        screen.blit(t, (30, oy + 42))
        pct = prog.get("pct")
        if pct is not None:
            bw = int((W - 80) * pct / 100)
            pygame.draw.rect(screen, C_DIM,    (30, oy + 72, W - 80, 12))
            pygame.draw.rect(screen, C_ACCENT, (30, oy + 72, bw,     12))

    # ── Pick-List Overlay ────────────────────────────────────────────
    lst = ipc.read_json(ipc.LIST_FILE, {})
    if lst.get("active"):
        items_l = lst.get("items", [])
        sel_l   = lst.get("selected", 0)
        pygame.draw.rect(screen, (10, 10, 30), (0, 0, W, H))
        pygame.draw.rect(screen, C_HEADER, (0, 0, W, HEADER_H))
        t = font_med.render(lst.get("title","")[:28], True, C_ACCENT)
        screen.blit(t, (8, 6))
        draw_status_icons(screen, font_sm, status)
        scroll_l = max(0, sel_l - 5)
        for i in range(min(10, len(items_l))):
            ii = i + scroll_l
            if ii >= len(items_l): break
            iy = HEADER_H + 4 + i * 28
            if ii == sel_l:
                pygame.draw.rect(screen, C_SEL_BG, (0, iy, W, 27))
                col = (255, 255, 255)
            else:
                col = C_TEXT
            t = font_med.render(str(items_l[ii])[:36], True, col)
            screen.blit(t, (10, iy + 4))

    pygame.display.flip()


def main():
    log.info("=" * 50)
    log.info("PiDrive Display v0.6.4 gestartet")
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
    _render_count = 0
    _last_debug   = 0

    while True:
        # Status und Menue von Core lesen
        status = ipc.read_json(ipc.STATUS_FILE, {})
        menu   = ipc.read_json(ipc.MENU_FILE,   {})

        # GPT-5.4: Fallback wenn Core noch nicht bereit
        core_ready = os.path.exists(ipc.READY_FILE)

        # Rendern
        try:
            if not core_ready or not status:
                # Fallback-Screen: "Core wartet..."
                screen.fill(C_BG)
                font_big, font_med, font_sm = fonts
                t = font_big.render("PiDrive", True, C_ACCENT)
                screen.blit(t, (W//2 - t.get_width()//2, 60))
                msg = "Core startet..." if not core_ready else "Warte auf Daten..."
                t = font_med.render(msg, True, C_DIM)
                screen.blit(t, (W//2 - t.get_width()//2, 110))
                pygame.display.flip()
            else:
                render(screen, fonts, status, menu)
                _render_count += 1
        except Exception as e:
            log.error(f"Render-Fehler: {e}")

        # GPT-5.4: Display-Debug JSON schreiben (alle 5s)
        now = time.time()
        if now - _last_debug > 5:
            ipc.write_json(ipc.DEBUG_FILE, {
                "display_loop": True,
                "last_render":  int(now),
                "core_ready":   core_ready,
                "status_ok":    bool(status),
                "menu_ok":      bool(menu),
                "render_count": _render_count,
                "driver":       "fbcon",
                "fbdev":        "/dev/fb1",
            })
            _last_debug = now

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
