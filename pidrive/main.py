#!/usr/bin/env python3
"""
main.py - PiDrive Hauptprogramm
PiDrive Project - GPL-v3

Start: python3 main.py
Service: sudo systemctl start ipod
"""

import pygame
import sys
import os
import time
import json

# Pfad zum pidrive Verzeichnis
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Display-Umgebungsvariablen (vor pygame.init!)
os.environ["SDL_FBDEV"]       = "/dev/fb0"
os.environ["SDL_VIDEODRIVER"] = "fbcon"
os.environ["SDL_NOMOUSE"]     = "1"

import status as S_module
import trigger
from ui import (SplitUI, Category, Item, W, H, FB_W, FB_H,
                C_PURPLE, C_BLUE, C_BT_BLUE, C_ORANGE)
from modules import musik, wifi, bluetooth, audio, system, webradio, dabfm, library

# ── Settings laden ─────────────────────────────────────────────
def load_settings():
    path = os.path.join(BASE_DIR, "config/settings.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"music_path": os.path.expanduser("~/Musik"),
                "audio_output": "auto",
                "device_name": "PiDrive"}

def save_settings(settings):
    path = os.path.join(BASE_DIR, "config/settings.json")
    try:
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

# ── Menü aufbauen ──────────────────────────────────────────────
def build_menu(screen, S, settings):
    """Alle Kategorien mit ihren Modulen zusammenbauen."""

    musik_items = musik.build_category(screen, S, settings)
    # Untermenues zu Musik hinzufuegen
    musik_items += [
        Item("Bibliothek",
             sub=lambda: S.get("library_track", "")[:20] if S.get("library_playing") else "MP3 Dateien",
             submenu=library.build_items(screen, S, settings)),
        Item("Webradio",
             sub=lambda: S.get("radio_station", "")[:20] if S.get("radio_playing") else "Stationen",
             submenu=webradio.build_items(screen, S)),
        Item("DAB+ / FM",
             sub="In Planung",
             submenu=dabfm.build_items(screen, S, settings)),
    ]

    categories = [
        Category("Musik",    C_PURPLE,  musik_items),
        Category("WiFi",     C_BLUE,    wifi.build_items(screen, S, settings)),
        Category("Bluetooth",C_BT_BLUE, bluetooth.build_items(screen, S, settings)),
        Category("System",   C_ORANGE,
                 audio.build_items(screen, S, settings) +
                 system.build_items(screen, S, settings)),
    ]

    return SplitUI(screen, categories, S, settings)

# ── Main Loop ──────────────────────────────────────────────────
def main():
    pygame.init()
    real   = pygame.display.set_mode((FB_W, FB_H))
    virt   = pygame.Surface((W, H))
    pygame.mouse.set_visible(False)

    settings = load_settings()

    # Initialer Status-Load
    S_module.refresh(force=True)
    S = S_module.S

    ui    = build_menu(virt, S, settings)
    clock = pygame.time.Clock()
    t_dn  = None
    t_t   = 0
    save_timer = time.time()

    while True:
        S_module.refresh()
        trigger.check(ui, S_module, settings)
        ui.draw()

        # Rotation 90° + skalieren auf Framebuffer
        rotated = pygame.transform.rotate(virt, 90)
        scaled  = pygame.transform.scale(rotated, (FB_W, FB_H))
        real.blit(scaled, (0, 0))
        pygame.display.flip()

        # Settings periodisch speichern
        if time.time() - save_timer > 60:
            save_settings(settings)
            save_timer = time.time()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                save_settings(settings)
                pygame.quit()
                sys.exit()

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP:
                    ui.key_up()
                elif ev.key == pygame.K_DOWN:
                    ui.key_down()
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_RIGHT):
                    ui.key_enter()
                elif ev.key in (pygame.K_ESCAPE, pygame.K_LEFT):
                    ui.key_back()

            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                t_dn = (int(ev.x * FB_W), int(ev.y * FB_H)) \
                       if ev.type == pygame.FINGERDOWN else ev.pos
                t_t = time.time()

            if ev.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if t_dn:
                    end = (int(ev.x * FB_W), int(ev.y * FB_H)) \
                          if ev.type == pygame.FINGERUP else ev.pos
                    dy = end[1] - t_dn[1]
                    dt = time.time() - t_t
                    # Koordinaten in virtuellen Raum umrechnen
                    rx = t_dn[0]
                    ry = t_dn[1]
                    vx = ry * W // FB_H
                    vy = (FB_W - rx) * H // FB_W
                    if abs(dy) > 25 and dt < 0.5:
                        if dy < 0: ui.key_down()
                        else:      ui.key_up()
                    else:
                        ui.touch(vx, vy)
                    t_dn = None

        clock.tick(30)

if __name__ == "__main__":
    main()
