"""
modules/scanner.py - Funkscanner mit RTL-SDR
PiDrive - GPL-v3

Empfaengt lizenzfreie und gewerbliche Funkdienste:
  PMR446  — 8 Kanaele, 446 MHz, NFM 12.5 kHz (Walkie-Talkie, analog)
  Freenet — 4 Kanaele, 149 MHz, NFM 12.5 kHz (lizenzfrei, DE)
  LPD433  — 69 Kanaele, 433 MHz, NFM 12.5 kHz (lizenzfrei)
  VHF     — 136-174 MHz, manuell (Betriebsfunk, Flugfunk, etc.)
  UHF     — 400-470 MHz, manuell (Betriebsfunk, Rettungsdienste, etc.)

Hardware: RTL-SDR Stick (RTL2832U)
Software: rtl-sdr Paket (rtl_fm) + mpv
"""

import subprocess
import time
import pygame
from ui import (Item, show_message, pick_list,
                draw_rect, get_font,
                W, H, STATUS_H, C_BG, C_WHITE, C_GRAY,
                C_GREEN, C_RED, C_SCANNER)
import log

# ── Kanaltabellen ────────────────────────────────────────────────────────────

PMR446_CHANNELS = [
    {"ch": 1, "name": "PMR Kanal 1",  "freq": 446.00625},
    {"ch": 2, "name": "PMR Kanal 2",  "freq": 446.01875},
    {"ch": 3, "name": "PMR Kanal 3",  "freq": 446.03125},
    {"ch": 4, "name": "PMR Kanal 4",  "freq": 446.04375},
    {"ch": 5, "name": "PMR Kanal 5",  "freq": 446.05625},
    {"ch": 6, "name": "PMR Kanal 6",  "freq": 446.06875},
    {"ch": 7, "name": "PMR Kanal 7",  "freq": 446.08125},
    {"ch": 8, "name": "PMR Kanal 8",  "freq": 446.09375},
]

FREENET_CHANNELS = [
    {"ch": 1, "name": "Freenet Kanal 1", "freq": 149.02500},
    {"ch": 2, "name": "Freenet Kanal 2", "freq": 149.03750},
    {"ch": 3, "name": "Freenet Kanal 3", "freq": 149.05000},
    {"ch": 4, "name": "Freenet Kanal 4", "freq": 149.08750},
]

# LPD433: Kanal 1-69, Startfrequenz 433.075 MHz, Raster 25 kHz
LPD433_CHANNELS = [
    {"ch": i + 1,
     "name": f"LPD Kanal {i + 1}",
     "freq": round(433.075 + i * 0.025, 3)}
    for i in range(69)
]

# VHF Betriebsfunk: 136-174 MHz
VHF_RANGE = {"min": 136.0, "max": 174.0, "step_fine": 0.025, "step_coarse": 1.0,
             "start": 156.8, "label": "VHF (136–174 MHz)"}

# UHF Betriebsfunk: 400-470 MHz
UHF_RANGE = {"min": 400.0, "max": 470.0, "step_fine": 0.025, "step_coarse": 1.0,
             "start": 446.0, "label": "UHF (400–470 MHz)"}

# ── Player ───────────────────────────────────────────────────────────────────

_player_proc = None

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _run(cmd, capture=False, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if capture else r.returncode == 0
    except Exception:
        return "" if capture else False

def is_rtlsdr_available():
    out = _run("lsusb 2>/dev/null | grep -iE 'rtl|2832|2838|0bda'", capture=True)
    return bool(out)

def is_rtlfm_available():
    return _run("which rtl_fm 2>/dev/null")

def check_hardware(screen):
    """Prueft Hardware und zeigt Fehlermeldung. Gibt True zurueck wenn OK."""
    if not is_rtlsdr_available():
        show_message(screen, "RTL-SDR", "Kein Stick gefunden!", color=C_RED)
        time.sleep(2)
        return False
    if not is_rtlfm_available():
        show_message(screen, "rtl_fm fehlt",
                     "sudo apt install rtl-sdr", color=C_RED)
        time.sleep(3)
        return False
    return True

def play_freq(freq_mhz, name, bandwidth_hz, S):
    """
    Spielt eine Frequenz ab via rtl_fm | mpv.
    bandwidth_hz: 12500 fuer NFM, 25000 fuer FM-Betriebsfunk
    """
    global _player_proc
    stop(S)

    freq_hz = f"{freq_mhz * 1e6:.0f}"
    bw = bandwidth_hz
    # Abtastrate: mindestens 2x Bandbreite, minimum 48000 fuer mpv
    sample_rate = max(48000, bw * 4)

    try:
        cmd = (
            f"rtl_fm -M fm -f {freq_hz} -s {bw} -r {sample_rate} - 2>/dev/null | "
            f"mpv --no-video --really-quiet --title=pidrive_scanner "
            f"--demuxer=rawaudio --demuxer-rawaudio-rate={sample_rate} "
            f"--demuxer-rawaudio-channels=1 - 2>/dev/null"
        )
        _player_proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        S["radio_playing"]  = True
        S["radio_station"]  = f"{name} ({freq_mhz:.5g} MHz)"
        S["radio_type"]     = "SCANNER"
        log.action("Scanner", f"{name} @ {freq_mhz} MHz ({bw} Hz BW)")
    except Exception as e:
        log.error(f"Scanner play Fehler: {e}")

def stop(S):
    global _player_proc
    _bg("pkill -f pidrive_scanner 2>/dev/null")
    if _player_proc:
        try:
            _player_proc.terminate()
        except Exception:
            pass
        _player_proc = None
    if S.get("radio_type") == "SCANNER":
        S["radio_playing"] = False
        S["radio_station"] = ""

# ── Manuelle Frequenzeingabe ─────────────────────────────────────────────────

def _draw_freq_input(screen, freq, band_cfg):
    screen.fill(C_BG)
    draw_rect(screen, (18, 19, 26), (0, 0, W, STATUS_H))
    pygame.draw.line(screen, C_SCANNER,
                     (0, STATUS_H - 1), (W, STATUS_H - 1), 2)
    t = get_font(13, bold=True).render(band_cfg["label"], True, C_WHITE)
    screen.blit(t, (W // 2 - t.get_width() // 2,
                    STATUS_H // 2 - t.get_height() // 2))

    cy = H // 2 - 35
    draw_rect(screen, (25, 27, 38), (30, cy, W - 60, 54))
    pygame.draw.rect(screen, C_SCANNER, pygame.Rect(30, cy, W - 60, 54), 2)

    freq_lbl = get_font(26, bold=True).render(f"{freq:.3f} MHz", True, C_SCANNER)
    screen.blit(freq_lbl, (W // 2 - freq_lbl.get_width() // 2, cy + 12))

    hints = [
        ("↑/↓",         f"±{band_cfg['step_fine']*1000:.0f} kHz"),
        ("Links/Rechts", f"±{band_cfg['step_coarse']:.0f} MHz"),
        ("Enter",        "Empfangen"),
        ("ESC",          "Abbrechen"),
    ]
    y = cy + 68
    for key, action in hints:
        k = get_font(11, bold=True).render(key, True, C_SCANNER)
        a = get_font(11).render(action, True, C_GRAY)
        screen.blit(k, (35, y))
        screen.blit(a, (35 + k.get_width() + 8, y))
        y += 18
    pygame.display.flip()

def freq_input_screen(screen, band_cfg):
    """
    Interaktive Frequenzeingabe fuer VHF/UHF.
    Gibt Frequenz als float zurueck oder None bei Abbruch.
    """
    freq = band_cfg["start"]
    f_min, f_max = band_cfg["min"], band_cfg["max"]
    step_f = band_cfg["step_fine"]
    step_c = band_cfg["step_coarse"]

    while True:
        _draw_freq_input(screen, freq, band_cfg)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return None
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP:
                    freq = min(f_max, round(freq + step_f, 3))
                elif ev.key == pygame.K_DOWN:
                    freq = max(f_min, round(freq - step_f, 3))
                elif ev.key == pygame.K_RIGHT:
                    freq = min(f_max, round(freq + step_c, 3))
                elif ev.key == pygame.K_LEFT:
                    freq = max(f_min, round(freq - step_c, 3))
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return freq
                elif ev.key == pygame.K_ESCAPE:
                    return None
        pygame.time.wait(50)

# ── Kanalauswahl ─────────────────────────────────────────────────────────────

def _play_from_list(screen, S, channels, bandwidth_hz, title):
    """Zeigt Kanalliste und spielt ausgewaehlten Kanal ab."""
    names = [f"K{c['ch']:02d}  {c['freq']:.5g} MHz  {c['name']}" for c in channels]
    chosen = pick_list(screen, title, names, color=C_SCANNER)
    if not chosen:
        return
    idx = names.index(chosen)
    if not check_hardware(screen):
        return
    play_freq(channels[idx]["freq"], channels[idx]["name"], bandwidth_hz, S)

# ── Menue-Items ──────────────────────────────────────────────────────────────

def build_items(screen, S, settings):
    """Scanner Untermenue-Items."""

    def play_pmr():
        _play_from_list(screen, S, PMR446_CHANNELS, 12500, "PMR446 Kanaele")

    def play_freenet():
        _play_from_list(screen, S, FREENET_CHANNELS, 12500, "Freenet Kanaele")

    def play_lpd():
        _play_from_list(screen, S, LPD433_CHANNELS, 12500, "LPD433 Kanaele")

    def play_vhf():
        if not check_hardware(screen):
            return
        freq = freq_input_screen(screen, VHF_RANGE)
        if freq is not None:
            play_freq(freq, "VHF Betriebsfunk", 25000, S)

    def play_uhf():
        if not check_hardware(screen):
            return
        freq = freq_input_screen(screen, UHF_RANGE)
        if freq is not None:
            play_freq(freq, "UHF Betriebsfunk", 25000, S)

    def stop_action():
        stop(S)
        show_message(screen, "Scanner", "Gestoppt")
        time.sleep(1)

    def _station_sub():
        if S.get("radio_type") == "SCANNER" and S.get("radio_playing"):
            return S.get("radio_station", "")[:22]
        return "RTL-SDR Empfaenger"

    return [
        Item("PMR446",
             sub=lambda: S.get("radio_station", "") if S.get("radio_type") == "SCANNER"
                         else "8 Kanaele · 446 MHz",
             action=play_pmr),
        Item("Freenet",
             sub="4 Kanaele · 149 MHz",
             action=play_freenet),
        Item("LPD433",
             sub="69 Kanaele · 433 MHz",
             action=play_lpd),
        Item("VHF manuell",
             sub="136–174 MHz · Betriebsfunk",
             action=play_vhf),
        Item("UHF manuell",
             sub="400–470 MHz · Betriebsfunk",
             action=play_uhf),
        Item("Stop",
             action=stop_action),
    ]
