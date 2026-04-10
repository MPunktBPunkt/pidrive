#!/usr/bin/env python3
"""
main_core.py - PiDrive Core v0.6.6
Headless: kein pygame, kein Display.

Verantwortlich fuer:
- File-Trigger lesen (/tmp/pidrive_cmd)
- Menuezustand verwalten
- Status sammeln (WiFi, BT, Spotify)
- Audio-/Systemmodule steuern
- Status+Menue als JSON schreiben (fuer Display-Prozess)
"""

import sys
import os
import time
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import log
import status as S_module
import trigger
import ipc
from modules import (musik, wifi, bluetooth, audio, system,
                     webradio, dab, fm, library, update, scanner)

logger = log.setup("core")

SETTINGS_FILE = os.path.join(BASE_DIR, "config/settings.json")


# ── Settings ──────────────────────────────────────────────────────────────────

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


# ── Menuemodell (ohne pygame) ──────────────────────────────────────────────────

class MenuItem:
    def __init__(self, label, action=None, submenu=None):
        self.label   = label
        self.action  = action   # callable
        self.submenu = submenu  # list of MenuItem


class MenuState:
    """Leichtgewichtiger Menuezustand ohne UI-Renderer."""

    def __init__(self, categories):
        self.categories  = categories   # list of (label, [MenuItem])
        self.cat_sel     = 0
        self.item_sel    = 0
        self.stack       = []           # (cat, item) fuer Back-Navigation

    @property
    def current_cat(self):
        return self.categories[self.cat_sel]

    @property
    def current_items(self):
        _, items = self.current_cat
        return items

    def key_up(self):
        if self.item_sel > 0:
            self.item_sel -= 1

    def key_down(self):
        items = self.current_items
        if self.item_sel < len(items) - 1:
            self.item_sel += 1

    def key_left(self):
        if self.cat_sel > 0:
            self.cat_sel -= 1
            self.item_sel = 0

    def key_right(self):
        if self.cat_sel < len(self.categories) - 1:
            self.cat_sel += 1
            self.item_sel = 0

    def key_enter(self):
        items = self.current_items
        if not items:
            return
        item = items[self.item_sel]
        if item.submenu:
            self.stack.append((self.cat_sel, self.item_sel))
            self.categories.append((item.label, item.submenu))
            self.cat_sel  = len(self.categories) - 1
            self.item_sel = 0
        elif item.action:
            # GPT-5.4: defensiv — Modul-Fehler stoppen nicht den Core
            try:
                item.action()
            except Exception as _e:
                import log as _log
                _log.error(f"Aktion '{item.label}' fehlgeschlagen: {_e}")
                import ipc as _ipc
                _ipc.write_progress("Fehler", str(_e)[:48], color="red")

    def key_back(self):
        if self.stack:
            # Temporaere Kategorie entfernen
            self.categories.pop()
            self.cat_sel, self.item_sel = self.stack.pop()

    def set_cat(self, val):
        try:
            idx = int(val)
            if 0 <= idx < len(self.categories):
                self.cat_sel  = idx
                self.item_sel = 0
                self.stack.clear()
        except (ValueError, TypeError):
            for i, (lbl, _) in enumerate(self.categories):
                if lbl.lower() == str(val).lower():
                    self.cat_sel  = i
                    self.item_sel = 0
                    self.stack.clear()
                    break

    def export(self):
        cat_lbl  = self.categories[self.cat_sel][0]
        items    = self.current_items
        item_lbl = items[self.item_sel].label if items else ""
        # GPT-5.4: vollstaendige Listen fuer Display-Renderer
        cat_labels  = [c[0] for c in self.categories[:10]]
        item_labels = [it.label for it in items[:12]]
        return self.cat_sel, cat_lbl, self.item_sel, item_lbl, cat_labels, item_labels


# ── Trigger (Core-Version ohne ui-Objekt) ─────────────────────────────────────

def handle_trigger(cmd, menu, S, settings):
    import subprocess

    def bg(c):
        try:
            subprocess.Popen(c, shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception:
            pass

    if   cmd == "up":    menu.key_up()
    elif cmd == "down":  menu.key_down()
    elif cmd == "left":  menu.key_left()
    elif cmd == "right": menu.key_right()
    elif cmd == "enter": menu.key_enter()
    elif cmd == "back":  menu.key_back()

    elif cmd == "wifi_on":
        bg("rfkill unblock wifi; ip link set wlan0 up; dhcpcd wlan0")
        S_module.invalidate()
    elif cmd == "wifi_off":
        bg("rfkill block wifi"); S_module.invalidate()

    elif cmd == "bt_on":
        bg("rfkill unblock bluetooth; hciconfig hci0 up"); S_module.invalidate()
    elif cmd == "bt_off":
        bg("hciconfig hci0 down"); S_module.invalidate()

    elif cmd == "audio_klinke":
        bg("amixer -c 0 cset numid=3 1 2>/dev/null")
        settings["audio_output"] = "Klinke"
    elif cmd == "audio_hdmi":
        bg("amixer -c 0 cset numid=3 2 2>/dev/null")
        settings["audio_output"] = "HDMI"
    elif cmd == "audio_bt":
        sink = S.get("bt_sink", "")
        if sink:
            bg(f"pactl set-default-sink {sink} 2>/dev/null")
            settings["audio_output"] = "Bluetooth"
    elif cmd == "audio_all":
        bg("pactl load-module module-combine-sink sink_name=combined 2>/dev/null; "
           "pactl set-default-sink combined 2>/dev/null")
        settings["audio_output"] = "Alle"

    elif cmd == "spotify_on":
        bg("systemctl start raspotify"); S_module.invalidate()
    elif cmd == "spotify_off":
        bg("systemctl stop raspotify"); S_module.invalidate()

    elif cmd == "radio_stop":
        bg("pkill -f mpv 2>/dev/null; pkill -f vlc 2>/dev/null")
        S["radio_playing"] = False

    elif cmd == "library_stop":
        bg("pkill -f mpv 2>/dev/null")
        S["library_playing"] = False

    elif cmd == "reboot":   bg("reboot")
    elif cmd == "shutdown": bg("poweroff")

    elif cmd.startswith("cat:"):
        menu.set_cat(cmd[4:])

    log.info(f"Trigger: {cmd}")


def check_trigger(menu, S, settings):
    if not os.path.exists(ipc.CMD_FILE):
        return
    try:
        with open(ipc.CMD_FILE) as f:
            cmd = f.read().strip()
        os.remove(ipc.CMD_FILE)
        if cmd:
            handle_trigger(cmd, menu, S, settings)
    except Exception:
        pass


# ── Einfache Kategorien fuer Core (Labels ohne pygame) ────────────────────────

def build_menu_model(S, settings):
    """Auto-Menue: Jetzt laeuft / Quellen / Verbindungen / System.
    GPT-5.4: Nutzungssituationen statt technische Module."""
    from modules import (musik as _musik, wifi as _wifi, bluetooth as _bt,
                         audio as _audio, system as _sys, webradio as _web,
                         dab as _dab, fm as _fm, update as _upd)

    categories = [
        # ── Jetzt laeuft ─────────────────────────────────────────────────────
        # Wichtigster Bereich — zeigt aktuelle Wiedergabe
        ("Jetzt laeuft", [
            MenuItem("Wiedergabe",
                     action=lambda: _musik.spotify_toggle(S) if not S.get("spotify") else None),
            MenuItem("Spotify",
                     action=lambda: _musik.spotify_toggle(S)),
            MenuItem("Audioausgang",
                     action=lambda: _audio.build_items(None, S, settings)[0].action()),
            MenuItem("Lauter",
                     action=lambda: _audio.build_items(None, S, settings)[1].action()),
            MenuItem("Leiser",
                     action=lambda: _audio.build_items(None, S, settings)[2].action()),
        ]),
        # ── Quellen ──────────────────────────────────────────────────────────
        # Audioquelle waehlen → aktiviert Quelle und springt zu "Jetzt laeuft"
        ("Quellen", [
            MenuItem("Spotify",
                     action=lambda: _musik.spotify_toggle(S)),
            MenuItem("Bibliothek"),
            MenuItem("Webradio"),
            MenuItem("DAB+"),
            MenuItem("FM Radio"),
            MenuItem("Scanner"),
        ]),
        # ── Verbindungen ─────────────────────────────────────────────────────
        # Selten benoetigt — BT + WiFi Management
        ("Verbindungen", [
            MenuItem("Bluetooth An/Aus"),
            MenuItem("Geraete scannen"),
            MenuItem("WiFi An/Aus",
                     action=lambda: _wifi.wifi_toggle(S)),
            MenuItem("Netzwerke scannen",
                     action=lambda: _wifi.build_items(None, S, settings)[2].action()),
            MenuItem("Status"),
        ]),
        # ── System ───────────────────────────────────────────────────────────
        ("System", [
            MenuItem("IP Adresse"),
            MenuItem("System-Info",
                     action=lambda: _sys.build_items(None, S, settings)[2].action()),
            MenuItem("Version",
                     action=lambda: _sys.build_items(None, S, settings)[3].action()),
            MenuItem("Neustart",
                     action=lambda: _sys.build_items(None, S, settings)[4].action()),
            MenuItem("Ausschalten",
                     action=lambda: _sys.build_items(None, S, settings)[5].action()),
            MenuItem("Update",
                     action=lambda: _upd.build_items(None, S, settings)[0].action()
                                    if _upd.build_items(None, S, settings) else None),
        ]),
    ]
    return MenuState(categories)


# ── System-Check (Core-Version) ────────────────────────────────────────────────

def system_check():
    import subprocess
    log.info("--- Core System-Check ---")
    try:
        ver = open(os.path.join(BASE_DIR, "VERSION")).read().strip()
        log.info(f"  PiDrive Core v{ver}")
    except Exception:
        pass
    try:
        r = subprocess.run("systemctl is-active raspotify",
                           shell=True, capture_output=True, text=True)
        log.info(f"  raspotify: {r.stdout.strip()}")
    except Exception:
        pass
    try:
        r = subprocess.run("ip a show wlan0", shell=True,
                           capture_output=True, text=True)
        if "inet " in r.stdout:
            ip = [l.split()[1] for l in r.stdout.splitlines() if "inet " in l][0]
            log.info(f"  WLAN: {ip}")
    except Exception:
        pass
    log.info("--- Core System-Check OK ---")


# ── Hauptschleife ──────────────────────────────────────────────────────────────

def main():
    log.info("=" * 50)
    log.info("PiDrive Core v0.6.6 gestartet")
    log.info(f"  PID={os.getpid()}  UID={os.getuid()}")
    log.info("  Headless — kein Display benoetigt")
    log.info(f"  Trigger: echo 'cmd' > {ipc.CMD_FILE}")
    log.info("=" * 50)

    system_check()

    settings    = load_settings()
    S_module.refresh(force=True)
    S           = S_module.S
    S["radio_type"] = ""

    menu        = build_menu_model(S, settings)
    save_timer  = time.time()
    stat_timer  = time.time()
    ipc_timer   = time.time()

    log.info("Core-Loop gestartet")
    _ready_written = False

    while True:
        # Status aktualisieren
        S_module.refresh()
        S = S_module.S

        # Trigger pruefen
        check_trigger(menu, S, settings)

        # IPC-Dateien schreiben (jede Sekunde)
        if time.time() - ipc_timer > 1.0:
            ipc.write_status(S, settings)
            cat_idx, cat_lbl, item_idx, item_lbl, cats, items_list = menu.export()
            ipc.write_menu(cat_idx, cat_lbl, item_idx, item_lbl,
                           S.get("radio_type", ""), cats, items_list)
            ipc_timer = time.time()
            # GPT-5.4: /tmp/pidrive_ready als IPC-Bereit-Signal
            if not _ready_written:
                try:
                    open("/tmp/pidrive_ready","w").write("1")
                    _ready_written = True
                    log.info("IPC ready — /tmp/pidrive_ready geschrieben")
                except Exception: pass

        # Status-Log (alle 30s)
        if time.time() - stat_timer > 30:
            log.status_update(S["wifi"], S["bt"], S["spotify"],
                              settings.get("audio_output", "auto"))
            stat_timer = time.time()

        # Settings speichern (jede Minute)
        if time.time() - save_timer > 60:
            save_settings(settings)
            save_timer = time.time()

        time.sleep(0.1)   # 10 Hz — reicht fuer Trigger-Response


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Core beendet (KeyboardInterrupt)")
    except Exception as e:
        import traceback
        log.error(f"Core Fehler: {e}\n{traceback.format_exc()}")
        raise
