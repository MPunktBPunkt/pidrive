"""
modules/fm.py - FM Radio mit RTL-SDR
PiDrive - GPL-v3

Hardware: RTL-SDR Stick
Software: rtl-sdr Paket (rtl_fm) + mpv --ao=pulse (v0.8.11)

Frequenzen werden in config/fm_stations.json gespeichert.
Format: [{"name": "Bayern 3", "freq": "99.4"}]
        oder {"stations": [...], "freq_mhz": ...}  (Scan-Format)

v0.8.7:
- _get_freq(): liest 'freq' ODER 'freq_mhz' — behebt fm_next/fm_prev Bug
- play_station(): Doppelstart-Entprellung (_last_station_key / _last_start_ts)
- play_next/prev(): robustes Matching nach Name UND Frequenz
"""

import subprocess
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
import os
import json
import time
import ipc
import log

STATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "../config/fm_stations.json")

_player_proc      = None
_last_start_ts    = 0.0
_last_station_key = ""

DEFAULT_STATIONS = [
    {"name": "Bayern 3",      "freq": "99.4"},
    {"name": "Lokal FM",      "freq": "104.4"},
    {"name": "Bayern 1",      "freq": "95.8"},
    {"name": "Antenne Bayern","freq": "102.2"},
    {"name": "Radio BOB",     "freq": "89.0"},
    {"name": "DLF",           "freq": "91.3"},
    {"name": "DLF Nova",      "freq": "98.7"},
    {"name": "SWR3",          "freq": "96.9"},
    {"name": "NDR 2",         "freq": "87.9"},
]


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


def _get_freq(station):
    """Liest Frequenz aus Station-Dict — akzeptiert 'freq' UND 'freq_mhz'."""
    return station.get("freq", station.get("freq_mhz", ""))


def _station_key(name, freq):
    """Eindeutiger Key für Doppelstart-Entprellung."""
    return f"{(name or '').strip().lower()}|{str(freq).strip()}"


def is_rtlsdr_available():
    out = _run("lsusb 2>/dev/null | grep -i 'RTL\\|2832\\|2838'", capture=True)
    return bool(out)


def is_rtlfm_available():
    out = _run("which rtl_fm 2>/dev/null", capture=True)
    return bool(out)


def load_stations():
    try:
        with open(STATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("stations", [])
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return list(DEFAULT_STATIONS)


def save_stations(stations):
    try:
        os.makedirs(os.path.dirname(STATIONS_FILE), exist_ok=True)
        data = {
            "version":    1,
            "updated_at": int(time.time()),
            "stations":   stations
        }
        with open(STATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log.info(f"FM: {len(stations)} Stationen gespeichert")
    except Exception as e:
        log.error(f"FM Stationen speichern: {e}")


def play_station(station, S, settings=None):
    """FM Station abspielen via rtl_fm | mpv --ao=pulse (v0.8.11: einheitlich)."""
    global _player_proc, _last_start_ts, _last_station_key

    freq = _get_freq(station)
    name = station.get("name", "")

    if settings is not None:
        settings["last_fm_station"] = station
        try:
            import json as _j
            with open("/home/pi/pidrive/pidrive/config/settings.json", "w") as _f:
                _j.dump(settings, _f, indent=2)
        except Exception:
            pass

    if not freq:
        log.error(f"FM play: keine Frequenz station={station!r}")
        return

    # v0.9.5: Low-Risk Start-Guard — gleiche Station läuft bereits
    try:
        if (S.get("radio_playing")
                and S.get("radio_type") == "FM"
                and S.get("radio_name") == name
                and str(freq) in S.get("radio_station", "")):
            log.info(f"FM play: bereits aktiv — kein Neustart name={name!r} freq={freq}")
            return
    except Exception:
        pass

    try:
        freq_f = float(freq)
    except Exception:
        log.error(f"FM play: ungültige Frequenz: {freq!r}")
        return

    # Doppelstart-Entprellung: gleicher Sender innerhalb 2s ignorieren
    now     = time.time()
    cur_key = _station_key(name, freq_f)
    if (S.get("radio_type") == "FM"
            and S.get("radio_playing")
            and cur_key == _last_station_key
            and (now - _last_start_ts) < 2.0):
        log.info(f"FM play: entprellt (Doppelstart) name={name!r} freq={freq_f}")
        return

    stop(S)

    freq_hz = f"{freq_f * 1e6:.0f}"
    log.info(f"FM play: START name={name!r} freq={freq_f}")

    try:
        if _rtlsdr:
            # Aufräumen vor neuem Start
            try:
                _rtlsdr.reap_process()
            except Exception:
                pass

            if not _rtlsdr.detect_usb().get("present"):
                S["radio_playing"] = False
                S["radio_station"] = "RTL-SDR nicht gefunden"
                log.error("FM: kein RTL-SDR")
                return

            # Warten auf echte Freigabe nach stop() — verhindert Race beim Senderwechsel
            if not _rtlsdr.wait_until_free(timeout=2.5, interval=0.05):
                log.warn(f"FM: RTL-SDR nach stop() noch belegt — harter Cleanup für {name} @ {freq_f}")
                try:
                    _rtlsdr.stop_process()
                except Exception:
                    pass
                _bg("pkill -f rtl_fm 2>/dev/null")
                _bg("pkill -f aplay 2>/dev/null")
                _bg("pkill -f 'mpv --no-video --really-quiet --title=pidrive_fm' 2>/dev/null")
                time.sleep(0.35)

            if not _rtlsdr.wait_until_free(timeout=1.5, interval=0.05):
                S["radio_playing"] = False
                S["radio_station"] = "RTL-SDR belegt"
                log.warn(f"FM: RTL-SDR belegt vor play {name} @ {freq_f}")
                return

        # v0.8.12: Zielarchitektur Option B — immer über zentrales PulseAudio
        from modules import audio as _audio
        _mpv_raw2  = _audio.get_mpv_args(settings, source="fm")
        # Index 0: env-prefix (leer bei ALSA-Modus) oder "PULSE_SERVER=..." bei BT
        _mpv_env2  = _mpv_raw2[0] if _mpv_raw2 and not _mpv_raw2[0].startswith("--") else ""
        _mpv_extra = _mpv_raw2[1:] if _mpv_env2 is not None else _mpv_raw2
        # Leeren env-prefix herausfiltern
        if not _mpv_env2:
            _mpv_extra = [a for a in _mpv_raw2 if a and not a == ""]

        # Strict Mode: abbrechen wenn PulseAudio inaktiv
        _adec = _audio.get_last_decision()
        if _adec.get("reason") == "pulseaudio_inactive" or _adec.get("effective") == "none":
            S["radio_playing"] = False
            S["radio_station"] = "Audiofehler: PulseAudio inaktiv"
            S["radio_name"]    = name
            S["radio_type"]    = "FM"
            S["control_context"] = "radio_fm"  # Phase 2 state
            log.error(f"FM strict-mode: Abbruch name={name!r} freq={freq_f} reason={_adec.get('reason','?')}")
            return


        _fm_gain_val = settings.get("fm_gain", -1) if settings else -1
        _fm_gain_arg = "" if str(_fm_gain_val) == "-1" else f" -g {_fm_gain_val}"
        _ppm_val     = int(settings.get("ppm_correction", 0)) if settings else 0
        _ppm_arg     = "" if _ppm_val == 0 else f" -p {_ppm_val}"
        # v0.9.15: PULSE_SERVER vor mpv — ohne env findet mpv den System-Daemon nicht
        cmd = (
            "rtl_fm -M wbfm -f " + freq_hz + " -s 250000 -r 32000" + _fm_gain_arg + _ppm_arg + " -A fast - 2>/dev/null | "
            + (_mpv_env2 + " " if _mpv_env2 else "") +
            "mpv --no-video --really-quiet --title=pidrive_fm "
            "--demuxer=rawaudio --demuxer-rawaudio-rate=32000 "
            "--demuxer-rawaudio-channels=1 " + " ".join(_mpv_extra) + " - 2>/dev/null"
        )

        if _ppm_val != 0:
            log.info(f"FM play: PPM-Korrektur aktiv: {_ppm_val} ppm")
        log.info(f"FM play: PIPE zentral/mpv freq_hz={freq_hz}")

        if _rtlsdr:
            _player_proc = _rtlsdr.start_process(
                cmd, owner="fm_play", shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            _player_proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        S["radio_playing"]  = True
        S["radio_station"]  = f"FM: {name} ({freq_f:.1f} MHz)"
        S["radio_name"]     = name
        S["radio_type"]     = "FM"
        S["control_context"] = "radio_fm"  # Phase 2 state
        _last_start_ts      = now
        _last_station_key   = cur_key

        log.action("FM", f"Wiedergabe: {name} ({freq_f:.1f} MHz)")

    except Exception as e:
        log.error(f"FM play Fehler: {e}")


def stop(S):
    global _player_proc
    log.info("FM stop: requested")
    try:
        if _rtlsdr:
            _rtlsdr.stop_process()
    except Exception as e:
        log.warn(f"FM stop: rtlsdr.stop_process: {e}")
    _bg("pkill -f pidrive_fm 2>/dev/null")
    _bg("pkill -f rtl_fm 2>/dev/null")
    _bg("pkill -f aplay 2>/dev/null")
    _bg("pkill -f 'mpv --no-video --really-quiet --title=pidrive_fm' 2>/dev/null")
    if _player_proc:
        try:
            _player_proc.terminate()
        except Exception:
            pass
        _player_proc = None
    # Kurzes Warten auf echte Freigabe — verhindert sofortiges Busy beim Folgestart
    try:
        if _rtlsdr:
            _rtlsdr.wait_until_free(timeout=1.5, interval=0.05)
    except Exception:
        pass
    if S.get("radio_type") == "FM":
        S["radio_playing"] = False
        S["radio_station"] = ""
    time.sleep(0.10)
    log.info("FM stop: done")


def play_next(S, stations):
    """Nächste FM Station — robust mit freq UND freq_mhz."""
    if not stations:
        log.warn("FM next: keine Stationen")
        return
    current = S.get("radio_station", "")
    idx = 0
    for i, s in enumerate(stations):
        freq = _get_freq(s)
        name = s.get("name", "")
        if name and name in current:
            idx = (i + 1) % len(stations)
            break
        if freq and str(freq) in current:
            idx = (i + 1) % len(stations)
            break
    log.info(f"FM next: idx={idx} station={stations[idx]}")
    play_station(stations[idx], S)


def play_prev(S, stations):
    """Vorherige FM Station — robust mit freq UND freq_mhz."""
    if not stations:
        log.warn("FM prev: keine Stationen")
        return
    current = S.get("radio_station", "")
    idx = 0
    for i, s in enumerate(stations):
        freq = _get_freq(s)
        name = s.get("name", "")
        if name and name in current:
            idx = (i - 1) % len(stations)
            break
        if freq and str(freq) in current:
            idx = (i - 1) % len(stations)
            break
    log.info(f"FM prev: idx={idx} station={stations[idx]}")
    play_station(stations[idx], S)


def freq_input_screen(screen=None):
    """Headless Frequenz-Eingabe via File-Trigger. Gibt Frequenz-String zurück."""
    freq = 87.5
    deadline = time.time() + 60
    while time.time() < deadline:
        ipc.write_progress(
            "FM Frequenz",
            f"{freq:.1f} MHz  (↑↓ 0.1  ←→ 1.0  Enter=OK  Back=Abbruch)",
            color="blue"
        )
        if not os.path.exists(ipc.CMD_FILE):
            time.sleep(0.15)
            continue
        try:
            cmd = open(ipc.CMD_FILE).read().strip()
            os.remove(ipc.CMD_FILE)
        except Exception:
            continue
        if   cmd == "up":    freq = min(108.0, round(freq + 0.1, 1))
        elif cmd == "down":  freq = max(87.5,  round(freq - 0.1, 1))
        elif cmd == "right": freq = min(108.0, round(freq + 1.0, 1))
        elif cmd == "left":  freq = max(87.5,  round(freq - 1.0, 1))
        elif cmd == "enter":
            ipc.clear_progress()
            return f"{freq:.1f}"
        elif cmd == "back":
            ipc.clear_progress()
            return None
    ipc.clear_progress()
    return None


def scan_stations(S):
    """FM Suchlauf via rtl_fm Squelch. Gibt Liste von Stationen zurück.

    1.5s Timeout: USB-Init (~0.5s) + Tuning (~0.3s) + Daten (~0.7s).
    Squelch -l 30: empfindlich genug für Innenräume mit Fensterantenne.
    """
    results = []

    if _rtlsdr:
        usb = _rtlsdr.detect_usb()
        if not usb.get("present"):
            log.error("FM Scan: kein RTL-SDR erkannt")
            return []
        if _rtlsdr.is_busy():
            log.warn("FM Scan: RTL-SDR belegt — Scan abgebrochen")
            return []

    freq = 87.6
    while freq <= 107.9:
        freq_hz = int(freq * 1e6)
        cmd = (f"timeout 1.5s rtl_fm -M wbfm -f {freq_hz} "
               f"-s 200000 -l 30 - 2>/dev/null | wc -c")
        try:
            r = subprocess.run(cmd, shell=True,
                               capture_output=True, text=True, timeout=3)
            count = int(r.stdout.strip() or "0")
            if count > 5000:
                results.append({
                    "id":       f"fm_{str(freq).replace('.', '_')}",
                    "name":     f"FM {freq:.1f} MHz",
                    "freq_mhz": freq,
                    "enabled":  True,
                    "favorite": False
                })
                log.info(f"FM Scan: Signal @ {freq:.1f} MHz ({count} bytes)")
        except Exception:
            pass
        freq = round(freq + 0.2, 1)

    log.info(f"FM Scan abgeschlossen: {len(results)} Sender")
    return results
