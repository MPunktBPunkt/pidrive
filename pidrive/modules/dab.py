"""
modules/dab.py - DAB+ Radio
PiDrive v0.6.1 — pygame-frei, Progress via IPC
"""

import subprocess
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
import threading
import os
import time
import log
import ipc

C_DAB = (0, 200, 180)

_player_proc = None
_scan_running = False
_scan_results = []
_last_scan_diag = {}


def get_last_scan_diag():
    """Letzte DAB-Scan-Diagnose als Dict (v0.9.4)."""
    return dict(_last_scan_diag)


def _normalize_station(st):
    """Sichert erwartete Felder für DAB-Stationen."""
    out = dict(st or {})
    out.setdefault("service_id", "")
    out.setdefault("ensemble", "")
    out.setdefault("channel", "")
    out.setdefault("favorite", False)
    out.setdefault("enabled", True)
    return out



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
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def is_rtlsdr_available():
    out = _run("lsusb 2>/dev/null", capture=True)
    return any(k in out.lower() for k in ["rtl", "realtek", "2838", "0bda"])

def is_welle_available():
    return _run("which welle-cli", capture=True) != ""

def load_stations():
    import json
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        return json.load(open(path))
    except Exception:
        return []

def save_stations(stations):
    import json
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        with open(path, "w") as f:
            json.dump(stations, f, indent=2)
    except Exception as e:
        log.error(f"DAB save Fehler: {e}")

def scan_dab_channels(settings=None):
    """
    DAB+ Suchlauf via welle-cli Webserver + mux.json (v0.9.4).

    Konfigurierbar via settings.json:
    - dab_scan_wait_lock: Sekunden pro Kanal (Standard 20s)
    - dab_scan_http_timeout: HTTP Timeout mux.json (Standard 4s)
    - dab_scan_port: getrennt von Diagnose-Port 7979 (Standard 7981)
    - dab_scan_channels: gezielte Kanäle z.B. ["11D","10A","8D"]
    """
    import subprocess as _sp
    import time as _t
    import json as _j
    import urllib.request as _ur

    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}

    SCAN_PORT = int(settings.get("dab_scan_port", 7981) or 7981)
    WAIT_LOCK = int(settings.get("dab_scan_wait_lock", 20) or 20)
    WAIT_HTTP = int(settings.get("dab_scan_http_timeout", 4) or 4)

    CHANNELS_REGIONAL = ["5C","5D","8D","10A","10D","11D","12D"]
    CHANNELS_FULL = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]

    # Gezielte Kanäle aus Settings
    requested_channels = settings.get("dab_scan_channels", []) or []
    if isinstance(requested_channels, str):
        requested_channels = [x.strip().upper() for x in requested_channels.split(",") if x.strip()]
    requested_channels = [str(x).strip().upper() for x in requested_channels if str(x).strip()]

    if requested_channels:
        region_list = [ch for ch in requested_channels if ch in CHANNELS_FULL]
        full_list   = region_list[:]
        log.info(f"DAB Scan: gezielte Kanäle: {region_list} (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")
    else:
        region_list = CHANNELS_REGIONAL
        full_list   = CHANNELS_FULL
        log.info(f"DAB Scan: Standard-Scan (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")

    gain_idx = _get_dab_gain(settings)
    found    = []
    scanned  = []

    def _lock_state_name(snr, ens_label, ens_id, services, fic_crc, last_fct0):
        """Grobe Lock-Interpretation: no_signal / no_fct0_lock / fic_only / ensemble_locked / services_found"""
        if services > 0:
            return "services_found"
        if ens_label or (ens_id and ens_id != "0x0000"):
            return "ensemble_locked"
        if int(last_fct0 or 0) == 0:
            return "no_fct0_lock" if snr >= 2.0 else "no_signal"
        if fic_crc >= 0:
            return "fic_only"
        return "unknown"


    global _last_scan_diag
    _last_scan_diag = {"channels": {}, "ts": int(time.time()),
                       "wait_lock": WAIT_LOCK, "port": SCAN_PORT}

    # Laufende welle-cli beenden
    _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
    _t.sleep(0.5)

    if _rtlsdr:
        usb = _rtlsdr.detect_usb()
        if not usb.get("present"):
            log.error("DAB Scan: RTL-SDR nicht erkannt")
            return []
        if _rtlsdr.is_busy():
            log.warn("DAB Scan: RTL-SDR belegt — warte 2s")
            _t.sleep(2)

    def _scan_channel(ch):
        """Einen DAB-Kanal scannen, mux.json holen, Services extrahieren."""
        _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)
        _t.sleep(0.3)

        cmd = (f"welle-cli -c {ch} -g {gain_idx} -C 1 -w {SCAN_PORT} "
               f"2>/tmp/pidrive_dab_welle.err")
        proc = _sp.Popen(cmd, shell=True, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        _t.sleep(WAIT_LOCK)

        services  = []
        snr       = 0.0
        ens_label = ""
        ens_id    = ""
        freq_corr = 0
        fic_crc   = -1
        last_fct0 = 0
        rx_gain   = ""

        try:
            url  = f"http://127.0.0.1:{SCAN_PORT}/mux.json"
            resp = _ur.urlopen(url, timeout=WAIT_HTTP)
            data = _j.loads(resp.read().decode("utf-8"))

            snr       = float(data.get("demodulator", {}).get("snr", 0)
                               or data.get("demodulator_snr", 0))
            ens_label = (data.get("ensemble", {}).get("label", {})
                           .get("label", "") or "")
            ens_id    = data.get("ensemble", {}).get("id", "")
            fic_crc   = int(data.get("demodulator", {}).get("fic", {})
                              .get("numcrcerrors", -1))
            last_fct0 = int(data.get("demodulator", {})
                              .get("time_last_fct0_frame", 0) or 0)
            freq_corr = int(data.get("receiver", {}).get("hardware", {})
                              .get("freqcorr", 0) or 0)
            rx_gain   = str(data.get("receiver", {}).get("hardware", {})
                              .get("gain", ""))

            raw_svcs = data.get("services", [])
            for svc in raw_svcs:
                name    = (svc.get("label", {}).get("label", "")
                             or svc.get("label", "")).strip()
                sid     = svc.get("sid", "")
                url_mp3 = svc.get("url_mp3", "")
                if name:
                    services.append({"name": name, "service_id": sid, "url_mp3": url_mp3})

        except Exception as e:
            log.info(f"DAB Scan: {ch}: mux.json nicht erreichbar ({e})")

        try:
            proc.terminate()
        except Exception:
            pass
        _sp.run("pkill -f welle-cli 2>/dev/null", shell=True, capture_output=True)

        lock_state = _lock_state_name(
            snr=snr, ens_label=ens_label, ens_id=ens_id,
            services=len(services), fic_crc=fic_crc, last_fct0=last_fct0
        )
        log.info(f"DAB Scan: CHANNEL_INFO ch={ch} ensemble={ens_label!r} "
                 f"id={ens_id} services={len(services)} snr={snr:.1f} "
                 f"freqcorr={freq_corr} gain={rx_gain} ficcrc={fic_crc} "
                 f"lastfct0={last_fct0} lock={lock_state}")
        if int(last_fct0 or 0) == 0:
            log.warn(f"DAB Scan: NO_FCT0_LOCK ch={ch} lastfct0=0 ensemble={ens_id or '0x0000'}")

        if snr >= 2.0 and len(services) == 0:
            log.warn(f"DAB Scan: LOCK_KANDIDAT ch={ch} snr={snr:.1f} keine Services — WAIT_LOCK erhöhen?")

        _last_scan_diag["channels"][ch] = {
            "ensemble": ens_label, "ensemble_id": ens_id,
            "services": len(services), "snr": snr,
            "freqcorr": freq_corr, "gain": rx_gain,
            "ficcrc": fic_crc, "lastfct0": last_fct0,
            "service_names": [s["name"] for s in services],
            "lock_state": lock_state if "lock_state" in dir() else "unknown",
        }
        return services, ens_label, ens_id, snr

    # --- Regionalscan ---
    ipc.write_progress("DAB+ Suchlauf", "Regionale Kanäle...", color="blue")
    for ch in region_list:
        ipc.write_progress("DAB+ Suchlauf", f"Kanal {ch}...", color="blue")
        svcs, ens_label, ens_id, snr = _scan_channel(ch)
        scanned.append(ch)
        for svc in svcs:
            entry = {
                "name":       svc["name"],
                "channel":    ch,
                "ensemble":   ens_label,
                "service_id": svc["service_id"],
                "url_mp3":    svc["url_mp3"],
                "id":         f"dab_{svc['service_id'] or svc['name']}",
                "favorite":   False,
                "enabled":    True,
            }
            if not any(e["name"] == svc["name"] and e["channel"] == ch for e in found):
                found.append(entry)

    # Vollscan wenn nötig
    if len(found) < 3 and not requested_channels:
        log.info("DAB Scan: Regionalscan < 3 Sender — Vollscan...")
        ipc.write_progress("DAB+ Suchlauf", "Vollscan...", color="blue")
        for ch in full_list:
            if ch in scanned:
                continue
            ipc.write_progress("DAB+ Suchlauf", f"Vollscan {ch}...", color="blue")
            svcs, ens_label, ens_id, snr = _scan_channel(ch)
            for svc in svcs:
                entry = {
                    "name":       svc["name"],
                    "channel":    ch,
                    "ensemble":   ens_label,
                    "service_id": svc["service_id"],
                    "url_mp3":    svc["url_mp3"],
                    "id":         f"dab_{svc['service_id'] or svc['name']}",
                    "favorite":   False,
                    "enabled":    True,
                }
                if not any(e["name"] == svc["name"] and e["channel"] == ch for e in found):
                    found.append(entry)

    _last_scan_diag["found"] = len(found)
    log.info(f"DAB Scan: FERTIG — {len(found)} Sender auf {len(scanned)} Kanälen (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")
    return found


def scan_dab_channels_full(progress_cb=None):
    """DAB Vollscan aller Band-III Kanäle (38 Kanäle, ~4 Minuten)."""
    all_channels = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]
    return scan_dab_channels(progress_cb=progress_cb, channels=all_channels)


# RTL-SDR R820T Gain-Tabelle (aus welle-cli / rtlsdr source)
# welle-cli -g N erwartet einen INDEX (0-28), NICHT einen dB-Wert!
# "Unknown gain count40" = Index 40 ist außerhalb des gültigen Bereichs (0-28)
_RTL_GAIN_TABLE = [
    0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7,
    16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8,
    36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6
]  # Index 0 = 0.0 dB, Index 28 = 49.6 dB

def _get_dab_gain(settings=None):
    """
    DAB Gain-Index für welle-cli (v0.9.4 — Gain-Index-Fix).

    WICHTIG: welle-cli -g erwartet einen GAIN-INDEX (0-28), KEIN dB-Wert!
    Quelle: rtl_sdr.cpp setGain(int gain_index) → prüft auf < gains.size()
    "Unknown gain count40" bedeutete: Index 40 ist out-of-range (max=28)

    Mapping: dab_gain (dB aus settings) → nächster Index in _RTL_GAIN_TABLE
    -1 → AGC (welle-cli setzt setAgc(true))
    40 dB → Index 22 (40.2 dB)
    49 dB → Index 28 (49.6 dB)
    """
    try:
        if settings is None:
            from settings import load_settings as _ls
            settings = _ls()
        g = settings.get("dab_gain", -1)
        if isinstance(g, str):
            g = g.strip()
            if not g:
                return "-1"
        g = float(g)
        if g < 0:
            return "-1"
        # dB → nächster Gain-Index
        idx = min(range(len(_RTL_GAIN_TABLE)), key=lambda i: abs(_RTL_GAIN_TABLE[i] - g))
        actual_db = _RTL_GAIN_TABLE[idx]
        log.info(f"DAB gain: {g:.0f} dB → Index {idx} ({actual_db:.1f} dB)")
        return str(idx)
    except Exception:
        return "-1"
        return str(int(float(g)))
    except Exception:
        return "-1"


def play_station(station, S, settings=None):
    global _player_proc
    stop(S)

    if settings is not None:
        settings["last_dab_station"] = station
        try:
            import json as _j
            with open("/home/pi/pidrive/pidrive/config/settings.json", "w") as _f:
                _j.dump(settings, _f, indent=2)
        except Exception:
            pass

    ch   = station.get("channel", "")
    name = station.get("name", "")

    if not ch:
        log.error(f"DAB play: kein channel station={station!r}")
        return

    # v0.9.5: Low-Risk Start-Guard — gleiche Station läuft bereits
    try:
        if (S.get("radio_playing")
                and S.get("radio_type") == "DAB"
                and S.get("radio_name") == name):
            log.info(f"DAB play: bereits aktiv — kein Neustart name={name!r}")
            return
    except Exception:
        pass

    if _rtlsdr:
        if not _rtlsdr.detect_usb().get("present"):
            S["radio_playing"] = False
            S["radio_station"] = "RTL-SDR nicht gefunden"
            log.error("DAB: kein RTL-SDR")
            return
        if _rtlsdr.is_busy():
            S["radio_playing"] = False
            S["radio_station"] = "RTL-SDR belegt"
            log.warn(f"DAB: RTL-SDR belegt vor play {name} [{ch}]")
            return

    try:
        from modules import audio as _audio
        _mpv_args = " ".join(_audio.get_mpv_args(settings, source="dab"))
        _gain     = _get_dab_gain(settings)

        # Strict Mode: abbrechen wenn PulseAudio inaktiv
        _adec = _audio.get_last_decision()
        if _adec.get("reason") == "pulseaudio_inactive" or _adec.get("effective") == "none":
            S["radio_playing"] = False
            S["radio_station"] = "Audiofehler: PulseAudio inaktiv"
            S["radio_name"]    = name
            S["radio_type"]    = "DAB"
            S["control_context"] = "radio_dab"  # Phase 2 state
            log.error(f"DAB strict-mode: Abbruch name={name!r} channel={ch} reason={_adec.get('reason','?')}")
            return

        # name mit shlex quoten fuer Shell-Sicherheit
        import shlex
        _name_q = shlex.quote(name)
        _ppm_val = int(settings.get("ppm_correction", 0)) if settings else 0
        # v0.9.3: -P ist in welle-cli KEIN PPM-Flag sondern Carousel/PAD-Verhalten!
        # PPM-Korrektur wird von welle-cli intern über den Coarse-Corrector gemacht.
        # Der konfigurierte PPM-Wert wird nur geloggt, nicht als CLI-Arg übergeben.
        _ppm_arg = ""  # bewusst leer — kein -P an welle-cli if _ppm_val == 0 else f" -P {_ppm_val}"

        # v0.8.11: welle-cli 2.2 kennt kein '-o -'
        # Korrekte Syntax: -p PROGRAMMNAME gibt Audio nach stdout aus
        # Pipe direkt in mpv
        _cmd = (
            "welle-cli -c " + ch + " -g " + _gain + _ppm_arg +
            " -p " + _name_q + " 2>/tmp/pidrive_dab_welle.err | "
            "mpv --no-video --really-quiet --title=pidrive_dab " + _mpv_args + " - 2>/dev/null"
        )

        if _ppm_val != 0:
            log.info(f"DAB play: PPM konfiguriert: {_ppm_val} ppm (interner welle-cli Coarse-Corrector)")
        log.info(f"DAB play: START name={name!r} channel={ch} gain={_gain}")

        if _rtlsdr:
            try:
                _player_proc = _rtlsdr.start_process(
                    _cmd, owner="dab_play", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as _e:
                S["radio_playing"] = False
                S["radio_station"] = "RTL-SDR Lock-Fehler"
                log.error("DAB: RTL-SDR Lock: " + str(_e))
                return
        else:
            _player_proc = subprocess.Popen(
                _cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # Kurz warten und welle-cli Startausgabe loggen
        import time as _t
        _t.sleep(1.2)
        try:
            if os.path.exists("/tmp/pidrive_dab_welle.err"):
                with open("/tmp/pidrive_dab_welle.err", "r",
                          encoding="utf-8", errors="ignore") as _f:
                    _lines = [ln.strip() for ln in _f.readlines()[-6:] if ln.strip()]
                for _ln in _lines:
                    log.info("DAB welle-cli: " + _ln[:200])
        except Exception:
            pass

        S["radio_playing"] = True
        S["radio_station"] = "DAB: " + name
        S["radio_name"]    = name
        S["radio_type"]    = "DAB"
        S["control_context"] = "radio_dab"  # Phase 2 state
        log.action("DAB", "Wiedergabe: " + name + " (" + ch + ")")

    except Exception as e:
        S["radio_playing"] = False
        S["radio_station"] = "DAB Fehler"
        log.error(f"DAB play Fehler: {e}")

def stop(S):
    global _player_proc, _scan_running
    log.info("DAB stop: requested")
    _scan_running = False
    _bg("pkill -f pidrive_dab 2>/dev/null")
    _bg("pkill -f welle-cli 2>/dev/null")
    _bg("pkill -f 'mpv --no-video --really-quiet --title=pidrive_dab' 2>/dev/null")
    if _rtlsdr:
        try:
            _rtlsdr.stop_process()
        except Exception:
            pass
    if _player_proc:
        try:
            _player_proc.terminate()
        except Exception:
            pass
        _player_proc = None
    S["radio_playing"] = False
    if S.get("radio_type") == "DAB":
        S["radio_station"] = ""
    time.sleep(0.25)
    log.info("DAB stop: done")

# build_items() entfernt in v0.7.1 — Menü wird von menu_model.py gebaut

def play_by_name(name, S, service_id=""):
    """
    DAB Station bevorzugt über service_id, sonst über Name abspielen (v0.9.4).
    Robuster gegen Dubletten und neue Scans.
    """
    import json, os
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path))
        stations = data.get("stations", data) if isinstance(data, dict) else data
        service_id = str(service_id or "").strip().lower()
        if service_id:
            for s in stations:
                sid = str(s.get("service_id", "") or "").strip().lower()
                if sid and sid == service_id:
                    play_station(_normalize_station(s), S)
                    return
        for s in stations:
            if s.get("name","") == name:
                play_station(_normalize_station(s), S)
                return
    except Exception as e:
        log.error(f"DAB play_by_name: {e}")


def play_next(S, stations):
    """Naechste DAB Station."""
    if not stations:
        return
    current = S.get("radio_station","")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name","") == current:
            idx = (i+1) % len(stations); break
    play_station(stations[idx], S)


def play_prev(S, stations):
    """Vorherige DAB Station."""
    if not stations:
        return
    current = S.get("radio_station","")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name","") == current:
            idx = (i-1) % len(stations); break
    play_station(stations[idx], S)
