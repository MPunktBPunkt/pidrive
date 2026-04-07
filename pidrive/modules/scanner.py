"""
modules/scanner.py - Funkscanner mit RTL-SDR
PiDrive - GPL-v3

PMR446 (8 Kanaele), Freenet (4), LPD433 (69), VHF (136-174 MHz), UHF (400-470 MHz)
Scan-Funktion: Squelch-Erkennung via rtl_fm -l, stoppt bei Signal.
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
    {"ch": i+1, "name": f"PMR Kanal {i+1}",
     "freq": round(446.00625 + i * 0.01250, 5)}
    for i in range(8)
]

FREENET_CHANNELS = [
    {"ch": 1, "name": "Freenet K1", "freq": 149.02500},
    {"ch": 2, "name": "Freenet K2", "freq": 149.03750},
    {"ch": 3, "name": "Freenet K3", "freq": 149.05000},
    {"ch": 4, "name": "Freenet K4", "freq": 149.08750},
]

LPD433_CHANNELS = [
    {"ch": i+1, "name": f"LPD K{i+1:02d}",
     "freq": round(433.075 + i * 0.025, 3)}
    for i in range(69)
]

VHF_RANGE = {"min": 136.0, "max": 174.0, "step_fine": 0.025,
             "step_coarse": 1.0, "start": 156.8,
             "label": "VHF (136-174 MHz)", "short": "VHF"}

UHF_RANGE = {"min": 400.0, "max": 470.0, "step_fine": 0.025,
             "step_coarse": 1.0, "start": 446.0,
             "label": "UHF (400-470 MHz)", "short": "UHF"}

# ── Player ───────────────────────────────────────────────────────────────────

_player_proc = None
SQUELCH = 25  # 0=immer offen, hoeher=strenger

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    return bool(_run("lsusb 2>/dev/null | grep -iE 'rtl|2832|2838|0bda'",
                     capture=True))

def is_rtlfm_available():
    return _run("which rtl_fm 2>/dev/null")

def check_hardware(screen):
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
    global _player_proc
    stop(S)
    freq_hz = int(freq_mhz * 1e6)
    sr = max(48000, bandwidth_hz * 4)
    try:
        cmd = (f"rtl_fm -M fm -f {freq_hz} -s {bandwidth_hz} -r {sr} - 2>/dev/null | "
               f"mpv --no-video --really-quiet --title=pidrive_scanner "
               f"--demuxer=rawaudio --demuxer-rawaudio-rate={sr} "
               f"--demuxer-rawaudio-channels=1 - 2>/dev/null")
        _player_proc = subprocess.Popen(cmd, shell=True,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
        S["radio_playing"] = True
        S["radio_station"] = f"{name} ({freq_mhz:.5g} MHz)"
        S["radio_type"]    = "SCANNER"
        log.action("Scanner", f"{name} @ {freq_mhz} MHz")
    except Exception as e:
        log.error(f"Scanner play: {e}")

def stop(S):
    global _player_proc
    _bg("pkill -f pidrive_scanner 2>/dev/null")
    if _player_proc:
        try: _player_proc.terminate()
        except Exception: pass
        _player_proc = None
    if S.get("radio_type") == "SCANNER":
        S["radio_playing"] = False
        S["radio_station"] = ""

# ── Signal-Erkennung ──────────────────────────────────────────────────────────

def _detect_signal(freq_mhz, bandwidth_hz, timeout_s=0.4):
    """
    Prueft Signal via rtl_fm Squelch.
    Bei Signal: rtl_fm gibt Audio aus -> viele Bytes.
    Ohne Signal: Squelch zu -> 0 Bytes.
    """
    freq_hz = int(freq_mhz * 1e6)
    cmd = (f"timeout {timeout_s}s rtl_fm -M fm -f {freq_hz} "
           f"-s {bandwidth_hz} -l {SQUELCH} -r 8000 - 2>/dev/null | wc -c")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout_s + 2)
        return int(r.stdout.strip() or "0") > 500
    except Exception:
        return False

# ── Scan-Screen ───────────────────────────────────────────────────────────────

def _draw_scan(screen, freq_str, label_str, direction, progress):
    screen.fill(C_BG)
    draw_rect(screen, (18, 19, 26), (0, 0, W, STATUS_H))
    pygame.draw.line(screen, C_SCANNER, (0, STATUS_H-1), (W, STATUS_H-1), 2)
    t = get_font(13, bold=True).render("SCAN AKTIV", True, C_SCANNER)
    screen.blit(t, (W//2 - t.get_width()//2, STATUS_H//2 - t.get_height()//2))

    arrow = "SCAN  ▲" if direction > 0 else "SCAN  ▼"
    a = get_font(16, bold=True).render(arrow, True, C_SCANNER)
    screen.blit(a, (W//2 - a.get_width()//2, STATUS_H + 18))

    draw_rect(screen, (22, 25, 38), (20, STATUS_H+42, W-40, 52))
    pygame.draw.rect(screen, C_SCANNER, pygame.Rect(20, STATUS_H+42, W-40, 52), 2)
    f = get_font(26, bold=True).render(freq_str, True, C_WHITE)
    screen.blit(f, (W//2 - f.get_width()//2, STATUS_H+54))

    n = get_font(12).render(label_str, True, C_GRAY)
    screen.blit(n, (W//2 - n.get_width()//2, STATUS_H+102))

    bx, by, bw, bh = 20, H-45, W-40, 8
    draw_rect(screen, (35, 40, 58), (bx, by, bw, bh))
    fw = int(bw * max(0, min(1, progress)))
    if fw > 0:
        pygame.draw.rect(screen, C_SCANNER, pygame.Rect(bx, by, fw, bh))

    esc = get_font(11).render("ESC - Abbrechen", True, C_GRAY)
    screen.blit(esc, (W//2 - esc.get_width()//2, H-28))
    pygame.display.flip()

def _draw_found(screen, freq_str, label_str):
    screen.fill(C_BG)
    draw_rect(screen, (18, 19, 26), (0, 0, W, STATUS_H))
    pygame.draw.line(screen, C_GREEN, (0, STATUS_H-1), (W, STATUS_H-1), 2)
    t = get_font(13, bold=True).render("SIGNAL GEFUNDEN", True, C_GREEN)
    screen.blit(t, (W//2 - t.get_width()//2, STATUS_H//2 - t.get_height()//2))
    cy = H//2 - 20
    f = get_font(26, bold=True).render(freq_str, True, C_WHITE)
    screen.blit(f, (W//2 - f.get_width()//2, cy))
    n = get_font(13).render(label_str, True, C_GREEN)
    screen.blit(n, (W//2 - n.get_width()//2, cy+38))
    pygame.display.flip()

# ── Scan-Funktionen ───────────────────────────────────────────────────────────

def _scan_list(screen, S, channels, bw, direction):
    n = len(channels)
    idx = 0 if direction > 0 else n-1
    for step in range(n):
        ch = channels[idx]
        _draw_scan(screen, f"{ch['freq']:.5g} MHz", ch["name"], direction, step/n)
        for ev in pygame.event.get():
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return None
        if _detect_signal(ch["freq"], bw):
            _draw_found(screen, f"{ch['freq']:.5g} MHz", ch["name"])
            pygame.time.wait(800)
            log.action("Scanner", f"Signal: {ch['name']} @ {ch['freq']} MHz")
            return ch
        idx = (idx + direction) % n
    show_message(screen, "Scan beendet", "Kein Signal", color=C_GRAY)
    time.sleep(1.5)
    return None

def _scan_range(screen, S, band, bw, direction):
    step  = band["step_fine"]
    total = round((band["max"] - band["min"]) / step)
    freq  = band["start"]
    for done in range(total):
        _draw_scan(screen, f"{freq:.3f} MHz", band["label"], direction, done/total)
        for ev in pygame.event.get():
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return None
        if _detect_signal(freq, bw):
            name = f"{band['short']} {freq:.3f} MHz"
            _draw_found(screen, f"{freq:.3f} MHz", band["label"])
            pygame.time.wait(800)
            log.action("Scanner", f"Signal @ {freq:.3f} MHz")
            return {"name": name, "freq": freq}
        freq = round(freq + direction * step, 3)
        if freq > band["max"]: freq = band["min"]
        elif freq < band["min"]: freq = band["max"]
    show_message(screen, "Scan beendet", "Kein Signal", color=C_GRAY)
    time.sleep(1.5)
    return None

# ── Manuell Frequenz ──────────────────────────────────────────────────────────

def _draw_freq_input(screen, freq, band):
    screen.fill(C_BG)
    draw_rect(screen, (18, 19, 26), (0, 0, W, STATUS_H))
    pygame.draw.line(screen, C_SCANNER, (0, STATUS_H-1), (W, STATUS_H-1), 2)
    t = get_font(13, bold=True).render(band["label"], True, C_WHITE)
    screen.blit(t, (W//2 - t.get_width()//2, STATUS_H//2 - t.get_height()//2))
    cy = H//2 - 35
    draw_rect(screen, (25, 27, 38), (30, cy, W-60, 54))
    pygame.draw.rect(screen, C_SCANNER, pygame.Rect(30, cy, W-60, 54), 2)
    fl = get_font(26, bold=True).render(f"{freq:.3f} MHz", True, C_SCANNER)
    screen.blit(fl, (W//2 - fl.get_width()//2, cy+12))
    hints = [("Up/Down", f"+-{band['step_fine']*1000:.0f} kHz"),
             ("L/R", f"+-{band['step_coarse']:.0f} MHz"),
             ("Enter", "Empfangen"), ("ESC", "Abbrechen")]
    y = cy + 68
    for key, act in hints:
        k = get_font(11, bold=True).render(key, True, C_SCANNER)
        a = get_font(11).render(act, True, C_GRAY)
        screen.blit(k, (35, y))
        screen.blit(a, (35 + k.get_width() + 8, y))
        y += 18
    pygame.display.flip()

def _freq_input(screen, band):
    freq = band["start"]
    while True:
        _draw_freq_input(screen, freq, band)
        for ev in pygame.event.get():
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP:
                    freq = min(band["max"], round(freq + band["step_fine"], 3))
                elif ev.key == pygame.K_DOWN:
                    freq = max(band["min"], round(freq - band["step_fine"], 3))
                elif ev.key == pygame.K_RIGHT:
                    freq = min(band["max"], round(freq + band["step_coarse"], 3))
                elif ev.key == pygame.K_LEFT:
                    freq = max(band["min"], round(freq - band["step_coarse"], 3))
                elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return freq
                elif ev.key == pygame.K_ESCAPE:
                    return None
        pygame.time.wait(50)

# ── Menu ─────────────────────────────────────────────────────────────────────

def build_items(screen, S, settings):

    def pmr_select():
        if not check_hardware(screen): return
        names = [f"K{c['ch']:02d}  {c['freq']:.5g} MHz  {c['name']}"
                 for c in PMR446_CHANNELS]
        chosen = pick_list(screen, "PMR446 Kanaele", names, color=C_SCANNER)
        if chosen:
            idx = names.index(chosen)
            play_freq(PMR446_CHANNELS[idx]["freq"],
                      PMR446_CHANNELS[idx]["name"], 12500, S)

    def freenet_select():
        if not check_hardware(screen): return
        names = [f"K{c['ch']}  {c['freq']:.5g} MHz  {c['name']}"
                 for c in FREENET_CHANNELS]
        chosen = pick_list(screen, "Freenet Kanaele", names, color=C_SCANNER)
        if chosen:
            idx = names.index(chosen)
            play_freq(FREENET_CHANNELS[idx]["freq"],
                      FREENET_CHANNELS[idx]["name"], 12500, S)

    def lpd_select():
        if not check_hardware(screen): return
        names = [f"K{c['ch']:02d}  {c['freq']:.3f} MHz" for c in LPD433_CHANNELS]
        chosen = pick_list(screen, "LPD433 Kanaele", names, color=C_SCANNER)
        if chosen:
            idx = names.index(chosen)
            play_freq(LPD433_CHANNELS[idx]["freq"],
                      LPD433_CHANNELS[idx]["name"], 12500, S)

    def mk_list_scan(channels, bw, d):
        def f():
            if not check_hardware(screen): return
            ch = _scan_list(screen, S, channels, bw, d)
            if ch: play_freq(ch["freq"], ch["name"], bw, S)
        return f

    def mk_range_scan(band, bw, d):
        def f():
            if not check_hardware(screen): return
            r = _scan_range(screen, S, band, bw, d)
            if r: play_freq(r["freq"], r["name"], bw, S)
        return f

    def mk_manual(band, bw):
        def f():
            if not check_hardware(screen): return
            freq = _freq_input(screen, band)
            if freq is not None:
                play_freq(freq, band["short"], bw, S)
        return f

    def stop_action():
        stop(S)
        show_message(screen, "Scanner", "Gestoppt")
        time.sleep(1)

    return [
        Item("PMR446",
             sub=lambda: S["radio_station"][:22] if S.get("radio_type") == "SCANNER"
                         else "8 Kanaele · 446 MHz",
             submenu=[
                 Item("Kanal waehlen", sub="K1-K8",    action=pmr_select),
                 Item("Scan aufwaerts", sub="K1 -> K8", action=mk_list_scan(PMR446_CHANNELS, 12500, 1)),
                 Item("Scan abwaerts",  sub="K8 -> K1", action=mk_list_scan(PMR446_CHANNELS, 12500, -1)),
             ]),
        Item("Freenet",
             sub="4 Kanaele · 149 MHz",
             action=freenet_select),
        Item("LPD433",
             sub="69 Kanaele · 433 MHz",
             submenu=[
                 Item("Kanal waehlen",  sub="K1-K69",        action=lpd_select),
                 Item("Scan aufwaerts", sub="K01 -> K69",     action=mk_list_scan(LPD433_CHANNELS, 12500, 1)),
                 Item("Scan abwaerts",  sub="K69 -> K01",     action=mk_list_scan(LPD433_CHANNELS, 12500, -1)),
             ]),
        Item("VHF manuell",
             sub="136-174 MHz",
             submenu=[
                 Item("Frequenz",       sub="manuell eingeben", action=mk_manual(VHF_RANGE, 25000)),
                 Item("Scan aufwaerts", sub="136 -> 174 MHz",   action=mk_range_scan(VHF_RANGE, 25000, 1)),
                 Item("Scan abwaerts",  sub="174 -> 136 MHz",   action=mk_range_scan(VHF_RANGE, 25000, -1)),
             ]),
        Item("UHF manuell",
             sub="400-470 MHz",
             submenu=[
                 Item("Frequenz",       sub="manuell eingeben", action=mk_manual(UHF_RANGE, 25000)),
                 Item("Scan aufwaerts", sub="400 -> 470 MHz",   action=mk_range_scan(UHF_RANGE, 25000, 1)),
                 Item("Scan abwaerts",  sub="470 -> 400 MHz",   action=mk_range_scan(UHF_RANGE, 25000, -1)),
             ]),
        Item("Stop", action=stop_action),
    ]
