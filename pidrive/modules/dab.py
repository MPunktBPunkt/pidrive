"""
modules/dab.py - DAB+ Radio mit RTL-SDR und welle.io
PiDrive - GPL-v3

Hardware: RTL-SDR Stick (z.B. RTL2832U)
Software: welle-cli (aus welle.io Paket)

Installation:
  sudo apt install welle.io  # oder
  sudo apt install rtl-sdr
  # welle-cli separat kompilieren:
  # https://github.com/AlbrechtL/welle.io

Senderliste wird in config/dab_stations.json gespeichert.
"""

import subprocess
import os
import json
import time
import threading
import pygame
from ui import (Item, show_message, pick_list,
                draw_rect, get_font,
                W, H, STATUS_H, C_BG, C_HEADER,
                C_WHITE, C_GRAY, C_GREEN, C_RED,
                C_DIVIDER, C_SEL, C_DAB)
import log

STATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "../config/dab_stations.json")

_player_proc  = None
_scan_thread  = None
_scan_running = False
_scan_results = []

def _run(cmd, capture=False, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if capture else r.returncode == 0
    except Exception:
        return "" if capture else False

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def is_rtlsdr_available():
    """Prueft ob RTL-SDR Stick angeschlossen ist."""
    out = _run("lsusb 2>/dev/null | grep -i 'RTL\\|2832\\|2838'", capture=True)
    return bool(out)

def is_welle_available():
    """Prueft ob welle-cli installiert ist."""
    out = _run("which welle-cli 2>/dev/null", capture=True)
    return bool(out)

def load_stations():
    """Gespeicherte DAB-Stationen laden."""
    try:
        with open(STATIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_stations(stations):
    """DAB-Stationen speichern."""
    try:
        os.makedirs(os.path.dirname(STATIONS_FILE), exist_ok=True)
        with open(STATIONS_FILE, "w") as f:
            json.dump(stations, f, indent=2, ensure_ascii=False)
        log.info(f"DAB: {len(stations)} Stationen gespeichert")
    except Exception as e:
        log.error(f"DAB Stationen speichern: {e}")

def scan_dab_channels(progress_cb=None):
    """
    DAB+ Kanaele scannen via welle-cli.
    progress_cb(pct, msg) wird bei Fortschritt aufgerufen.
    Gibt Liste von {"name": ..., "channel": ..., "ensemble": ...} zurueck.
    """
    global _scan_running, _scan_results
    _scan_running = True
    _scan_results = []

    # DAB+ Band III Kanaele (5A - 13F)
    channels = [
        "5A","5B","5C","5D",
        "6A","6B","6C","6D",
        "7A","7B","7C","7D",
        "8A","8B","8C","8D",
        "9A","9B","9C","9D",
        "10A","10B","10C","10D",
        "11A","11B","11C","11D",
        "12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]

    found = []
    total = len(channels)

    for i, ch in enumerate(channels):
        if not _scan_running:
            break

        if progress_cb:
            pct = int(i / total * 100)
            progress_cb(pct, f"Scanne {ch}... ({i}/{total})")

        # welle-cli Kanal scannen (2 Sekunden pro Kanal)
        out = _run(
            f"timeout 3 welle-cli -D 0 -c {ch} -p 2>/dev/null",
            capture=True, timeout=5
        )

        if out:
            for line in out.splitlines():
                if "Service:" in line or "Programme:" in line:
                    name = line.split(":", 1)[-1].strip()
                    if name and name not in [s["name"] for s in found]:
                        found.append({
                            "name":     name,
                            "channel":  ch,
                            "ensemble": "",
                        })
                        log.info(f"DAB gefunden: {name} auf {ch}")

    _scan_results = found
    _scan_running = False
    return found

def play_station(station, S):
    """DAB+ Station abspielen."""
    global _player_proc
    stop(S)

    ch   = station.get("channel", "")
    name = station.get("name", "")

    if not ch:
        log.error("DAB play: kein Kanal")
        return

    try:
        _player_proc = subprocess.Popen(
            f"welle-cli -D 0 -c {ch} -s '{name}' -o - 2>/dev/null | "
            f"mpv --no-video --really-quiet --title=pidrive_dab - 2>/dev/null",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        S["radio_playing"]  = True
        S["radio_station"]  = f"DAB: {name}"
        S["radio_type"]     = "DAB"
        log.action("DAB", f"Wiedergabe: {name} ({ch})")
    except Exception as e:
        log.error(f"DAB play Fehler: {e}")

def stop(S):
    global _player_proc, _scan_running
    _scan_running = False
    _bg("pkill -f pidrive_dab 2>/dev/null")
    _bg("pkill -f welle-cli 2>/dev/null")
    if _player_proc:
        try: _player_proc.terminate()
        except Exception: pass
        _player_proc = None
    S["radio_playing"] = False
    if S.get("radio_type") == "DAB":
        S["radio_station"] = ""

def draw_scan_screen(screen, pct, msg, found_count):
    """Fortschrittsanzeige beim Scannen."""
    screen.fill(C_BG)
    draw_rect(screen, C_HEADER, (0, 0, W, STATUS_H))
    pygame.draw.line(screen, C_DAB, (0, STATUS_H - 1), (W, STATUS_H - 1), 2)
    t = get_font(14, bold=True).render("DAB+ Sendersuche", True, C_WHITE)
    screen.blit(t, (W//2 - t.get_width()//2,
                     STATUS_H//2 - t.get_height()//2))

    cy = H // 2 - 40
    # Fortschrittsbalken
    bar_w = W - 40
    bar_h = 20
    draw_rect(screen, (30, 32, 45), (20, cy, bar_w, bar_h))
    fill_w = int(bar_w * pct / 100)
    if fill_w > 0:
        draw_rect(screen, C_DAB, (20, cy, fill_w, bar_h))
    pygame.draw.rect(screen, C_DAB, pygame.Rect(20, cy, bar_w, bar_h), 1)

    pct_lbl = get_font(13, bold=True).render(f"{pct}%", True, C_WHITE)
    screen.blit(pct_lbl, (W//2 - pct_lbl.get_width()//2, cy + 2))

    msg_lbl = get_font(12).render(msg[:36], True, C_GRAY)
    screen.blit(msg_lbl, (20, cy + 28))

    found_lbl = get_font(13, bold=True).render(
        f"Gefunden: {found_count} Sender", True, C_GREEN)
    screen.blit(found_lbl, (W//2 - found_lbl.get_width()//2, cy + 52))

    hint = get_font(11).render("ESC = Abbrechen", True, (60, 65, 85))
    screen.blit(hint, (W//2 - hint.get_width()//2, H - 25))
    pygame.display.flip()

def build_items(screen, S, settings):
    """DAB+ Untermenue-Items."""

    def check_hardware():
        if not is_rtlsdr_available():
            show_message(screen, "RTL-SDR", "Kein Stick gefunden!", color=C_RED)
            time.sleep(2)
            return False
        if not is_welle_available():
            show_message(screen, "welle-cli", "Nicht installiert!", color=C_RED)
            time.sleep(2)
            log.warn("DAB: welle-cli fehlt")
            return False
        return True

    def scan_action():
        if not check_hardware():
            return

        global _scan_running, _scan_results
        _scan_running = True
        _scan_results = []
        progress = {"pct": 0, "msg": "Starte...", "found": 0}

        def do_scan():
            def cb(pct, msg):
                progress["pct"] = pct
                progress["msg"] = msg
                progress["found"] = len(_scan_results)
            scan_dab_channels(cb)

        t = threading.Thread(target=do_scan, daemon=True)
        t.start()

        while _scan_running or t.is_alive():
            draw_scan_screen(screen,
                             progress["pct"],
                             progress["msg"],
                             progress["found"])
            for ev in pygame.event.get():
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        _scan_running = False
                        break
            pygame.time.wait(200)

        if _scan_results:
            save_stations(_scan_results)
            show_message(screen, "Scan fertig",
                         f"{len(_scan_results)} Sender gefunden",
                         color=C_GREEN)
        else:
            show_message(screen, "Scan fertig",
                         "Keine Sender gefunden", color=C_RED)
        time.sleep(2)

    def play_action():
        stations = load_stations()
        if not stations:
            show_message(screen, "DAB+",
                         "Erst Sendersuche starten!", color=C_RED)
            time.sleep(2)
            return
        names = [s["name"] for s in stations]
        chosen = pick_list(screen, "DAB+ Sender", names, color=C_DAB)
        if chosen:
            idx = names.index(chosen)
            play_station(stations[idx], S)

    def stop_action():
        stop(S)
        show_message(screen, "DAB+", "Gestoppt")
        time.sleep(1)

    def install_hint():
        show_message(screen, "Installation",
                     "sudo apt install welle.io", color=C_DAB)
        time.sleep(4)

    stations = load_stations()
    station_count = len(stations)

    items = [
        Item("Sender abspielen",
             sub=lambda: S.get("radio_station", "") if S.get("radio_type") == "DAB"
                         else f"{len(load_stations())} Sender gespeichert",
             action=play_action),
        Item("Sendersuche",
             sub=f"{station_count} Sender bekannt",
             action=scan_action),
        Item("Stop",
             action=stop_action),
        Item("Hinweis",
             sub="welle-cli noetig",
             action=install_hint),
    ]
    return items
