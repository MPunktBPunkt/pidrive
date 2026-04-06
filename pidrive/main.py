#!/usr/bin/env python3
"""
main.py - PiDrive Hauptprogramm v0.3.0
Raspberry Pi Car Infotainment - GPL-v3

Start:    python3 main.py
Service:  sudo systemctl start pidrive
Logs:     tail -f /var/log/pidrive/pidrive.log
Tastatur: USB (Pfeiltasten+Enter+ESC) oder SSH via pidrive_ctrl.py
"""

import pygame
import sys
import os
import time
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ["SDL_FBDEV"]       = "/dev/fb0"
os.environ["SDL_VIDEODRIVER"] = "fbcon"
os.environ["SDL_NOMOUSE"]     = "1"

import log
import status as S_module
import trigger
from ui import (SplitUI, Category, Item, W, H, FB_W, FB_H,
                C_PURPLE, C_BLUE, C_BT_BLUE, C_ORANGE, C_DAB, C_FM)
from modules import (musik, wifi, bluetooth, audio, system,
                     webradio, dab, fm, library, update)

logger = log.setup()

SETTINGS_FILE = os.path.join(BASE_DIR, "config/settings.json")

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
            log.info(f"Settings geladen")
            return s
    except Exception as e:
        log.warn(f"Settings Defaults ({e})")
        return {"music_path": os.path.expanduser("~/Musik"),
                "audio_output": "auto", "device_name": "PiDrive"}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        log.error(f"Settings speichern: {e}")

KEY_NAMES = {
    pygame.K_UP: "UP", pygame.K_DOWN: "DOWN",
    pygame.K_LEFT: "LEFT", pygame.K_RIGHT: "RIGHT",
    pygame.K_RETURN: "ENTER", pygame.K_KP_ENTER: "ENTER",
    pygame.K_ESCAPE: "ESC",
    pygame.K_w: "W", pygame.K_s: "S",
    pygame.K_a: "A", pygame.K_d: "D",
    pygame.K_F1: "F1", pygame.K_F2: "F2",
    pygame.K_F3: "F3", pygame.K_F4: "F4",
}

def build_menu(screen, S, settings):
    log.info("Menue aufbauen...")

    musik_items = musik.build_category(screen, S, settings)
    musik_items += [
        Item("Bibliothek",
             sub=lambda: S.get("library_track", "")[:20]
                         if S.get("library_playing") else "MP3 Dateien",
             submenu=library.build_items(screen, S, settings)),
        Item("Webradio",
             sub=lambda: S.get("radio_station", "")[:20]
                         if S.get("radio_type") == "WEB" else "Stationen",
             submenu=webradio.build_items(screen, S)),
        Item("DAB+",
             sub=lambda: S.get("radio_station", "")[:20]
                         if S.get("radio_type") == "DAB" else "RTL-SDR",
             submenu=dab.build_items(screen, S, settings)),
        Item("FM Radio",
             sub=lambda: S.get("radio_station", "")[:20]
                         if S.get("radio_type") == "FM" else "UKW",
             submenu=fm.build_items(screen, S, settings)),
    ]

    system_items = (audio.build_items(screen, S, settings) +
                    system.build_items(screen, S, settings) +
                    update.build_items(screen, S, settings))

    categories = [
        Category("Musik",     C_PURPLE,  musik_items),
        Category("WiFi",      C_BLUE,    wifi.build_items(screen, S, settings)),
        Category("Bluetooth", C_BT_BLUE, bluetooth.build_items(screen, S, settings)),
        Category("System",    C_ORANGE,  system_items),
    ]

    log.info(f"Menue: {len(categories)} Kategorien")
    ui = SplitUI(screen, categories, S, settings)
    ui.settings = settings
    return ui

def handle_key(ui, key, S, settings):
    name = KEY_NAMES.get(key, f"KEY_{key}")
    log.key_event(name)

    cat_before  = ui.cat_sel
    item_before = ui.item_sel

    if key in (pygame.K_UP, pygame.K_w):        ui.key_up()
    elif key in (pygame.K_DOWN, pygame.K_s):     ui.key_down()
    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                 pygame.K_RIGHT, pygame.K_d):    ui.key_enter()
    elif key in (pygame.K_ESCAPE, pygame.K_LEFT,
                 pygame.K_a):                    ui.key_back()
    elif key == pygame.K_F1:
        trigger._handle("audio_klinke", ui, S_module, settings)
    elif key == pygame.K_F2:
        trigger._handle("audio_hdmi", ui, S_module, settings)
    elif key == pygame.K_F3:
        trigger._handle("audio_bt", ui, S_module, settings)
    elif key == pygame.K_F4:
        trigger._handle("audio_all", ui, S_module, settings)

    if ui.cat_sel != cat_before or ui.item_sel != item_before:
        cat_name  = ui.categories[ui.cat_sel].label
        items     = ui._items()
        item_name = items[ui.item_sel].label if items else "-"
        log.menu_change(ui.categories[cat_before].label, cat_name, item_name)

def main():
    log.info("=" * 40)
    log.info(f"PiDrive startet - warte auf TTY + Display...")
    log.info(f"TTY:     /dev/tty3")
    log.info(f"Display: SDL_FBDEV={os.environ.get('SDL_FBDEV')}")
    log.info("=" * 40)

    # Warten bis rc.local (chvt 3) fertig ist und tty3 aktiv ist
    time.sleep(8)
    log.info("Warte-Zeit abgelaufen - starte pygame...")

    pygame.init()
    log.info("pygame init OK")

    try:
        real = pygame.display.set_mode((FB_W, FB_H))
        log.info(f"Framebuffer: {FB_W}x{FB_H} OK")
    except Exception as e:
        log.error(f"Display-Fehler: {e}")
        log.error("Hinweis: sudo chvt 3 ausfuehren und Service neu starten")
        sys.exit(1)

    virt = pygame.Surface((W, H))
    pygame.mouse.set_visible(False)

    settings = load_settings()
    S_module.refresh(force=True)
    S = S_module.S
    S["radio_type"] = ""  # WEB / DAB / FM
    log.status_update(S["wifi"], S["bt"], S["spotify"],
                      settings.get("audio_output", "auto"))

    ui = build_menu(virt, S, settings)
    clock      = pygame.time.Clock()
    t_dn       = None
    t_t        = 0
    save_timer = time.time()
    stat_timer = time.time()

    log.info("PiDrive v0.3.0 bereit")
    log.info("USB-Tastatur: Pfeiltasten + Enter + ESC")
    log.info(f"File-Trigger: echo 'cmd' > /tmp/pidrive_cmd")

    while True:
        S_module.refresh()
        if time.time() - stat_timer > 30:
            log.status_update(S["wifi"], S["bt"], S["spotify"],
                              settings.get("audio_output", "auto"))
            stat_timer = time.time()

        trigger.check(ui, S_module, settings)
        ui.draw()

        try:
            rotated = pygame.transform.rotate(virt, 90)
            scaled  = pygame.transform.scale(rotated, (FB_W, FB_H))
            real.blit(scaled, (0, 0))
            pygame.display.flip()
        except Exception as e:
            log.error(f"Render-Fehler: {e}")

        if time.time() - save_timer > 60:
            save_settings(settings)
            save_timer = time.time()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                save_settings(settings)
                pygame.quit(); sys.exit()

            if ev.type == pygame.KEYDOWN:
                handle_key(ui, ev.key, S, settings)

            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                t_dn = (int(ev.x * FB_W), int(ev.y * FB_H)) \
                       if ev.type == pygame.FINGERDOWN else ev.pos
                t_t = time.time()

            if ev.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if t_dn:
                    end = (int(ev.x * FB_W), int(ev.y * FB_H)) \
                          if ev.type == pygame.FINGERUP else ev.pos
                    dy  = end[1] - t_dn[1]
                    dt  = time.time() - t_t
                    vx  = t_dn[1] * W // FB_H
                    vy  = (FB_W - t_dn[0]) * H // FB_W
                    if abs(dy) > 25 and dt < 0.5:
                        if dy < 0: ui.key_down()
                        else:      ui.key_up()
                    else:
                        ui.touch(vx, vy)
                    t_dn = None

        clock.tick(30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("PiDrive beendet")
    except Exception as e:
        log.error(f"Fehler: {e}")
        import traceback
        log.error(traceback.format_exc())
        raise
