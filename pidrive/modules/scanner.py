"""
modules/scanner.py - Funkscanner mit RTL-SDR
PiDrive - GPL-v3

PMR446 (8 Kanaele), Freenet (4), LPD433 (69), VHF (136-174 MHz), UHF (400-470 MHz)
Scan-Funktion: Squelch-Erkennung via rtl_fm -l, stoppt bei Signal.
"""

import subprocess
import time
import ipc
from ui import Item
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
             "label": "VHF (136-174 MHz)", "short": "VHF"}

UHF_RANGE = {"min": 400.0, "max": 470.0, "step_fine": 0.025,
             "label": "UHF (400-470 MHz)", "short": "UHF"}

# ── Player ───────────────────────────────────────────────────────────────────

_player_proc = None
SQUELCH = 25  # 0=immer offen, hoeher=strenger

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
    return bool(_run("lsusb 2>/dev/null | grep -iE 'rtl|2832|2838|0bda'", capture=True))

def is_rtlfm_available():
    return _run("which rtl_fm 2>/dev/null")

def check_hardware(screen):
    if not is_rtlsdr_available():
        ipc.write_progress("RTL-SDR", "Kein Stick gefunden!")
        time.sleep(2)
        return False
    if not is_rtlfm_available():
        ipc.write_progress("rtl_fm fehlt", "sudo apt install rtl-sdr")
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
               f"--demuxer=rawaudio --demuxer-rawaudio-rate={sr} "
               f"--demuxer-rawaudio-channels=1 - 2>/dev/null")
        _player_proc = subprocess.Popen(cmd, shell=True,
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
           f"-s {bandwidth_hz} -l 70 - 2>/dev/null | wc -c")
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout_s + 1)
        return int(r.stdout.strip() or "0") > 500
    except Exception:
        return False

# ── Scan-Screen ───────────────────────────────────────────────────────────────



def _scan_list(S, channels, bw, direction):
    n = len(channels)
    idx = 0 if direction > 0 else n-1
    for step in range(n):
        ch = channels[idx]
        if _detect_signal(ch["freq"], bw):
            log.action("Scanner", f"Signal: {ch['name']} @ {ch['freq']} MHz")
            return ch
        idx = (idx + direction) % n
    ipc.write_progress("Scan beendet", "Kein Signal")
    time.sleep(1.5)
    return None

def _scan_range(S, band, bw, direction):
    step  = band["step_fine"]
    total = round((band["max"] - band["min"]) / step)
    freq  = band["start"]
    for done in range(total):
        if _detect_signal(freq, bw):
            name = f"{band['short']} {freq:.3f} MHz"
            log.action("Scanner", f"Signal @ {freq:.3f} MHz")
            return {"name": name, "freq": freq}
        freq = round(freq + direction * step, 3)
        if freq > band["max"]: freq = band["min"]
        elif freq < band["min"]: freq = band["max"]
    ipc.write_progress("Scan beendet", "Kein Signal")
    time.sleep(1.5)
    return None

# ── Manuell Frequenz ──────────────────────────────────────────────────────────


def _freq_input(band):
    """Frequenz via headless Trigger-Input (up/down/left/right/enter/back)."""
    freq = band["start"]
    deadline = __import__("time").time() + 60
    while __import__("time").time() < deadline:
        ipc.write_progress(
            f"{band['short']} Frequenz",
            f"{freq:.3f} MHz  (↑↓ fein  ←→ grob  Enter=OK  Back=Abbruch)",
            color="blue"
        )
        if not __import__("os").path.exists(ipc.CMD_FILE):
            __import__("time").sleep(0.15)
            continue
        try:
            cmd = open(ipc.CMD_FILE).read().strip()
            __import__("os").remove(ipc.CMD_FILE)
        except Exception:
            continue
        if   cmd == "up":    freq = min(band["max"], round(freq + band["step_fine"],   3))
        elif cmd == "down":  freq = max(band["min"], round(freq - band["step_fine"],   3))
        elif cmd == "right": freq = min(band["max"], round(freq + band["step_coarse"], 3))
        elif cmd == "left":  freq = max(band["min"], round(freq - band["step_coarse"], 3))
        elif cmd in ("enter",):
            ipc.clear_progress(); return freq
        elif cmd in ("back",):
            ipc.clear_progress(); return None
    ipc.clear_progress()
    return None

# ── Menu ─────────────────────────────────────────────────────────────────────

def build_items(screen, S, settings):

    def pmr_select():
        if not check_hardware(None): return
        names = [f"K{c['ch']:02d}  {c['freq']:.5g} MHz  {c['name']}"
                 for c in PMR446_CHANNELS]
        chosen = ipc.headless_pick("PMR446 Kanal", names)
        if chosen:
            idx = names.index(chosen)
            play_freq(PMR446_CHANNELS[idx]["freq"],
                      PMR446_CHANNELS[idx]["name"], 12500, S)

    def freenet_select():
        if not check_hardware(None): return
        names = [f"K{c['ch']}  {c['freq']:.5g} MHz  {c['name']}"
                 for c in FREENET_CHANNELS]
        chosen = ipc.headless_pick("Freenet Kanal", names)
        if chosen:
            idx = names.index(chosen)
            play_freq(FREENET_CHANNELS[idx]["freq"],
                      FREENET_CHANNELS[idx]["name"], 12500, S)

    def lpd_select():
        if not check_hardware(None): return
        names = [f"K{c['ch']:02d}  {c['freq']:.3f} MHz" for c in LPD433_CHANNELS]
        chosen = ipc.headless_pick("LPD433 Kanal", names)
        if chosen:
            idx = names.index(chosen)
            play_freq(LPD433_CHANNELS[idx]["freq"],
                      LPD433_CHANNELS[idx]["name"], 12500, S)

    def mk_list_scan(channels, bw, d):
        def f():
            if not check_hardware(None): return
            ch = _scan_list(S, channels, bw, d)
            if ch: play_freq(ch["freq"], ch["name"], bw, S)
        return f

    def mk_range_scan(band, bw, d):
        def f():
            if not check_hardware(None): return
            r = _scan_range(S, band, bw, d)
            if r: play_freq(r["freq"], r["name"], bw, S)
        return f

    def mk_manual(band, bw):
        def f():
            if not check_hardware(None): return
            freq = _freq_input(band)
            if freq is not None:
                play_freq(freq, band["short"], bw, S)
        return f

    def stop_action():
        stop(S)
        ipc.write_progress("Scanner", "Gestoppt")
        time.sleep(1)

    return [
        Item("PMR446",
             submenu=[
                 Item("Kanal waehlen", sub="K1-K8",    action=pmr_select),
                 Item("Scan aufwaerts", sub="K1 -> K8", action=mk_list_scan(PMR446_CHANNELS, 12500, 1)),
                 Item("Scan abwaerts",  sub="K8 -> K1", action=mk_list_scan(PMR446_CHANNELS, 12500, -1)),
             ]),
        Item("Freenet",
             action=freenet_select),
        Item("LPD433",
             submenu=[
                 Item("Kanal waehlen",  sub="K1-K69",        action=lpd_select),
                 Item("Scan aufwaerts", sub="K01 -> K69",     action=mk_list_scan(LPD433_CHANNELS, 12500, 1)),
                 Item("Scan abwaerts",  sub="K69 -> K01",     action=mk_list_scan(LPD433_CHANNELS, 12500, -1)),
             ]),
        Item("VHF manuell",
             submenu=[
                 Item("Frequenz",       sub="manuell eingeben", action=mk_manual(VHF_RANGE, 25000)),
                 Item("Scan aufwaerts", sub="136 -> 174 MHz",   action=mk_range_scan(VHF_RANGE, 25000, 1)),
                 Item("Scan abwaerts",  sub="174 -> 136 MHz",   action=mk_range_scan(VHF_RANGE, 25000, -1)),
             ]),
        Item("UHF manuell",
             submenu=[
                 Item("Frequenz",       sub="manuell eingeben", action=mk_manual(UHF_RANGE, 25000)),
                 Item("Scan aufwaerts", sub="400 -> 470 MHz",   action=mk_range_scan(UHF_RANGE, 25000, 1)),
                 Item("Scan abwaerts",  sub="470 -> 400 MHz",   action=mk_range_scan(UHF_RANGE, 25000, -1)),
             ]),
        Item("Stop", action=stop_action),
    ]
