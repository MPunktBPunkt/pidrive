#!/usr/bin/env python3
"""
main.py - PiDrive Hauptprogramm v0.5.1
Raspberry Pi Car Infotainment - GPL-v3
"""

import pygame
import sys
import os
import time
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

os.environ["SDL_FBDEV"]        = "/dev/fb0"
os.environ["SDL_VIDEODRIVER"]  = "fbcon"
os.environ["SDL_NOMOUSE"]      = "1"
os.environ["SDL_AUDIODRIVER"]  = "dummy"  # Verhindert ALSA-Konflikt mit raspotify
                                           # SDL_Init(EVERYTHING) wuerde sonst exit(0)
                                           # aufrufen wenn hw:1,0 von raspotify belegt

import log
import status as S_module
import trigger
from ui import (SplitUI, Category, Item, W, H, FB_W, FB_H,
                C_PURPLE, C_BLUE, C_BT_BLUE, C_ORANGE, C_DAB, C_FM, C_SCANNER)
from modules import (musik, wifi, bluetooth, audio, system,
                     webradio, dab, fm, library, update, scanner)

logger = log.setup()

# ── System-Check ──────────────────────────────────────────────
def _stat_perms(path):
    """Gibt Berechtigungen als lesbaren String zurueck, z.B. 'crw-rw---- root:tty (0660)'."""
    import stat as stat_mod
    import grp
    import pwd
    try:
        st = os.stat(path)
        mode = st.st_mode
        perm_oct  = oct(mode)[-4:]
        perm_str  = stat_mod.filemode(mode)
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except Exception:
            owner = str(st.st_uid)
        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except Exception:
            group = str(st.st_gid)
        return f"{perm_str} {owner}:{group} ({perm_oct})"
    except Exception as e:
        return f"stat fehler: {e}"

def _proc_groups():
    """Gibt Gruppennamen des aktuellen Prozesses zurueck."""
    import grp
    try:
        gids = os.getgroups()
        names = []
        for gid in gids:
            try:
                names.append(grp.getgrgid(gid).gr_name)
            except Exception:
                names.append(str(gid))
        return ", ".join(names)
    except Exception as e:
        return f"fehler: {e}"

def _stdin_target():
    """Wohin zeigt stdin (/proc/self/fd/0)?"""
    try:
        return os.readlink("/proc/self/fd/0")
    except Exception:
        return "unbekannt"

def _try_open_tty3():
    """Versucht /dev/tty3 O_RDWR zu oeffnen - genau wie systemd/openvt es braucht."""
    import fcntl
    try:
        fd = os.open("/dev/tty3", os.O_RDWR | os.O_NOCTTY)
        os.close(fd)
        return True, "OK"
    except OSError as e:
        return False, f"{e.strerror} (errno {e.errno})"

def system_check():
    """Prueft ob alle Voraussetzungen erfuellt sind."""
    import subprocess
    import pwd
    ok = True
    log.info("--- System-Check ---")

    # Version
    try:
        with open(os.path.join(BASE_DIR, "VERSION")) as f:
            ver = f.read().strip()
        log.info(f"  ✓ PiDrive Version: {ver}")
    except Exception:
        log.warn("  ⚠ VERSION Datei nicht lesbar")

    # ── Prozess-Kontext ────────────────────────────────────────
    try:
        uid  = os.getuid()
        gid  = os.getgid()
        try:
            uname = pwd.getpwuid(uid).pw_name
        except Exception:
            uname = str(uid)
        log.info(f"  ✓ Prozess laeuft als: {uname} (uid={uid} gid={gid})")
        log.info(f"  ✓ Gruppen: {_proc_groups()}")
    except Exception as e:
        log.warn(f"  ⚠ Prozessinfo fehler: {e}")

    # ── stdin ──────────────────────────────────────────────────
    stdin_dest = _stdin_target()
    log.info(f"  ✓ stdin (fd 0) -> {stdin_dest}")

    # ── Framebuffer ────────────────────────────────────────────
    if os.path.exists("/dev/fb0"):
        perms = _stat_perms("/dev/fb0")
        if os.access("/dev/fb0", os.R_OK | os.W_OK):
            log.info(f"  ✓ /dev/fb0 OK  [{perms}]")
        else:
            log.warn(f"  ⚠ /dev/fb0 keine Berechtigung  [{perms}]")
    else:
        log.error("  ✗ /dev/fb0 fehlt! Display-Treiber installiert?")
        ok = False

    # ── fbcp ───────────────────────────────────────────────────
    try:
        r = subprocess.run("pgrep fbcp", shell=True,
                           capture_output=True, text=True)
        if r.returncode == 0:
            log.info(f"  ✓ fbcp laeuft (pid: {r.stdout.strip()})")
        else:
            log.warn("  ⚠ fbcp laeuft nicht (SPI Display bleibt dunkel)")
    except Exception:
        pass

    # ── Aktives VT ─────────────────────────────────────────────
    try:
        r = subprocess.run("fgconsole", shell=True,
                           capture_output=True, text=True, timeout=2)
        tty_nr = r.stdout.strip()
        if tty_nr == "3":
            log.info(f"  ✓ Aktives VT: tty{tty_nr} (korrekt)")
        else:
            log.warn(f"  ⚠ Aktives VT: tty{tty_nr} (erwartet 3) -> chvt 3 noetig!")
    except Exception:
        log.warn("  ⚠ fgconsole nicht verfuegbar")

    # ── /dev/tty3 Berechtigungen ───────────────────────────────
    if os.path.exists("/dev/tty3"):
        perms = _stat_perms("/dev/tty3")
        log.info(f"  ✓ /dev/tty3 vorhanden  [{perms}]")

        # O_RDWR Test - genau was systemd/openvt braucht
        can_open, reason = _try_open_tty3()
        if can_open:
            log.info("  ✓ /dev/tty3 O_RDWR: erfolgreich")
        else:
            log.warn(f"  ⚠ /dev/tty3 O_RDWR fehlgeschlagen: {reason}")
            log.warn("    -> Fix: chmod 660 /dev/tty3 in rc.local")
            ok = False
    else:
        log.error("  ✗ /dev/tty3 fehlt!")
        ok = False

    # ── SDL Umgebung ───────────────────────────────────────────
    log.info(f"  ✓ SDL_FBDEV={os.environ.get('SDL_FBDEV', 'NICHT GESETZT')}")
    log.info(f"  ✓ SDL_VIDEODRIVER={os.environ.get('SDL_VIDEODRIVER', 'NICHT GESETZT')}")

    # ── pygame ─────────────────────────────────────────────────
    try:
        log.info(f"  ✓ pygame {pygame.version.ver}")
    except Exception as e:
        log.error(f"  ✗ pygame fehlt: {e}")
        ok = False

    # ── Raspotify ──────────────────────────────────────────────
    try:
        r = subprocess.run("systemctl is-active raspotify",
                           shell=True, capture_output=True, text=True)
        status = r.stdout.strip()
        if status == "active":
            log.info("  ✓ raspotify laeuft")
        else:
            log.warn(f"  ⚠ raspotify: {status}")
    except Exception:
        pass

    # ── WLAN ───────────────────────────────────────────────────
    try:
        r = subprocess.run("ip a show wlan0",
                           shell=True, capture_output=True, text=True)
        if "inet " in r.stdout:
            ip = [l.split()[1] for l in r.stdout.splitlines()
                  if "inet " in l][0]
            log.info(f"  ✓ WLAN: {ip}")
        else:
            log.warn("  ⚠ WLAN nicht verbunden")
    except Exception:
        pass

    # ── RTL-SDR ────────────────────────────────────────────────
    try:
        r = subprocess.run("lsusb", shell=True,
                           capture_output=True, text=True, timeout=3)
        rtl_found = any(k in r.stdout.lower()
                        for k in ["rtl", "realtek", "2838", "0bda"])
        if rtl_found:
            log.info("  ✓ RTL-SDR: USB Stick erkannt")
        else:
            log.warn("  ⚠ RTL-SDR: kein USB Stick gefunden (DAB+/FM deaktiviert)")
    except Exception:
        pass
    try:
        r = subprocess.run("which rtl_fm", shell=True,
                           capture_output=True, text=True)
        if r.returncode == 0:
            log.info("  ✓ rtl_fm: vorhanden")
        else:
            log.warn("  ⚠ rtl_fm fehlt -> sudo apt install rtl-sdr")
    except Exception:
        pass
    try:
        r = subprocess.run("which welle-cli", shell=True,
                           capture_output=True, text=True)
        if r.returncode == 0:
            log.info("  ✓ welle-cli: vorhanden (DAB+)")
        else:
            log.warn("  ⚠ welle-cli fehlt -> sudo apt install welle.io")
    except Exception:
        pass

    # ── Log ────────────────────────────────────────────────────
    if os.access("/var/log/pidrive", os.W_OK):
        log.info("  ✓ Log-Verzeichnis schreibbar")
    else:
        log.warn("  ⚠ Log nicht schreibbar")

    log.info(f"--- System-Check {'OK' if ok else 'FEHLER (Details oben)'} ---")
    return ok

SETTINGS_FILE = os.path.join(BASE_DIR, "config/settings.json")

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
            log.info("Settings geladen")
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
        Item("Scanner",
             sub=lambda: S.get("radio_station", "")[:20]
                         if S.get("radio_type") == "SCANNER" else "PMR/VHF/UHF",
             submenu=scanner.build_items(screen, S, settings)),
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
    # System-Check
    system_check()

    # pygame initialisieren
    # SDL_AUDIODRIVER=dummy: kein ALSA-Konflikt mit raspotify
    # PAMName=login im Service: echte logind-Session -> kein SIGHUP mehr
    log.info("pygame.init() ...")
    pygame.init()
    log.info("pygame.init() OK")

    log.info("pygame.display.set_mode() ...")
    try:
        real = pygame.display.set_mode((FB_W, FB_H))
        log.info(f"Display: {FB_W}x{FB_H} OK — Treiber: {pygame.display.get_driver()}")
    except Exception as e:
        log.error(f"Display-Fehler: {e}")
        sys.exit(1)

    virt = pygame.Surface((W, H))
    pygame.mouse.set_visible(False)
    log.info("Display initialisiert")

    settings = load_settings()
    S_module.refresh(force=True)
    S = S_module.S
    S["radio_type"] = ""
    log.status_update(S["wifi"], S["bt"], S["spotify"],
                      settings.get("audio_output", "auto"))

    ui = build_menu(virt, S, settings)
    log.info("Menue bereit")

    clock      = pygame.time.Clock()
    t_dn       = None
    t_t        = 0
    save_timer = time.time()
    stat_timer = time.time()

    try:
        with open(os.path.join(BASE_DIR, "VERSION")) as f:
            ver = f.read().strip()
    except Exception:
        ver = "?"
    log.info(f"PiDrive v{ver} laeuft!")
    log.info("Tastatur: Pfeiltasten + Enter + ESC")
    log.info("Trigger:  echo 'cmd' > /tmp/pidrive_cmd")

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
        log.info("PiDrive beendet (KeyboardInterrupt)")
    except Exception as e:
        log.error(f"Unbehandelter Fehler: {e}")
        import traceback
        log.error(traceback.format_exc())
        raise
