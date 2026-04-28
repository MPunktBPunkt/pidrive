"""
modules/dab.py — DAB+ Wiedergabe und Scan via welle-cli (ALSA-Direktmodus)
Aufrufer: main_core.py
Abhängig von: modules/audio.py, modules/source_state.py, ipc.py
Schreibt: /tmp/pidrive_dab_play_debug.json, settings[last_dab_station], dab_stations.json
Hinweis: welle-cli -p = ALSA-direkt, KEIN PulseAudio (OFDM-Timing-sensitiv)
"""


import subprocess
try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None
import os
import time
import json
import urllib.request as _ur

import log
import ipc

C_DAB = (0, 200, 180)

_player_proc = None
_scan_running = False
_scan_results = []
_last_scan_diag = {}
_SCAN_DEBUG_FILE = "/tmp/pidrive_dab_scan_debug.json"


def get_last_scan_diag():
    return dict(_last_scan_diag)


def _write_scan_diag_file():
    try:
        tmp = _SCAN_DEBUG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_last_scan_diag, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _SCAN_DEBUG_FILE)
    except Exception as e:
        log.warn("DAB scan diag file write: " + str(e))


def load_last_scan_diag_file():
    try:
        with open(_SCAN_DEBUG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_station(st):
    out = dict(st or {})
    out.setdefault("service_id", "")
    out.setdefault("ensemble", "")
    out.setdefault("channel", "")
    out.setdefault("url_mp3", "")
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
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        pass


def is_rtlsdr_available():
    out = _run("lsusb 2>/dev/null", capture=True)
    return any(k in out.lower() for k in ["rtl", "realtek", "2838", "0bda"])


def is_welle_available():
    return _run("which welle-cli", capture=True) != ""


def load_stations():
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        return data.get("stations", data) if isinstance(data, dict) else data
    except Exception:
        return []


def save_stations(stations):
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"DAB save Fehler: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Gain Mapping
# ──────────────────────────────────────────────────────────────────────────────

_RTL_GAIN_TABLE = [
    0.0, 0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7,
    16.6, 19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8,
    36.4, 37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6
]


def _get_dab_gain(settings=None):
    """
    welle-cli -g erwartet einen Gain-INDEX (0–28), nicht dB [1].
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
        idx = min(range(len(_RTL_GAIN_TABLE)), key=lambda i: abs(_RTL_GAIN_TABLE[i] - g))
        actual_db = _RTL_GAIN_TABLE[idx]
        log.info(f"DAB gain: {g:.0f} dB → Index {idx} ({actual_db:.1f} dB)")
        return str(idx)
    except Exception:
        return "-1"


# ──────────────────────────────────────────────────────────────────────────────
# Scan
# ──────────────────────────────────────────────────────────────────────────────

def scan_dab_channels(settings=None):
    """
    DAB+ Suchlauf via welle-cli Webserver + mux.json.

    Konfigurierbar via settings.json:
    - dab_scan_wait_lock
    - dab_scan_http_timeout
    - dab_scan_port
    - dab_scan_channels
    """
    import subprocess as _sp
    import time as _t

    if settings is None:
        try:
            from settings import load_settings as _ls
            settings = _ls()
        except Exception:
            settings = {}

    SCAN_PORT = int(settings.get("dab_scan_port", 7981) or 7981)
    WAIT_LOCK = int(settings.get("dab_scan_wait_lock", 20) or 20)
    WAIT_HTTP = int(settings.get("dab_scan_http_timeout", 4) or 4)

    CHANNELS_REGIONAL = ["5C", "5D", "8D", "10A", "10D", "11D", "12D"]
    CHANNELS_FULL = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]

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
    _last_scan_diag = {
        "channels": {},
        "ts": int(time.time()),
        "wait_lock": WAIT_LOCK,
        "port": SCAN_PORT
    }
    _write_scan_diag_file()

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
            data = json.loads(resp.read().decode("utf-8"))

            snr       = float(data.get("demodulator", {}).get("snr", 0) or data.get("demodulator_snr", 0))
            ens_label = (data.get("ensemble", {}).get("label", {}).get("label", "") or "")
            ens_id    = data.get("ensemble", {}).get("id", "")
            fic_crc   = int(data.get("demodulator", {}).get("fic", {}).get("numcrcerrors", -1))
            last_fct0 = int(data.get("demodulator", {}).get("time_last_fct0_frame", 0) or 0)
            freq_corr = int(data.get("receiver", {}).get("hardware", {}).get("freqcorr", 0) or 0)
            rx_gain   = str(data.get("receiver", {}).get("hardware", {}).get("gain", ""))

            raw_svcs = data.get("services", [])
            for svc in raw_svcs:
                # v0.9.14 Fix: label kann ein Dict sein → immer str() casten vor strip()
                _lbl = svc.get("label", "")
                if isinstance(_lbl, dict):
                    _lbl = _lbl.get("label", "") or ""
                name = str(_lbl or "").strip()
                sid  = str(svc.get("sid", "") or "").strip()
                url_mp3 = str(svc.get("url_mp3", "") or "").strip()
                if name:
                    services.append({
                        "name": name,
                        "service_id": sid,
                        "url_mp3": url_mp3
                    })

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
        log.info(
            f"DAB Scan: CHANNEL_INFO ch={ch} ensemble={ens_label!r} "
            f"id={ens_id} services={len(services)} snr={snr:.1f} "
            f"freqcorr={freq_corr} gain={rx_gain} ficcrc={fic_crc} "
            f"lastfct0={last_fct0} lock={lock_state}"
        )

        if int(last_fct0 or 0) == 0:
            log.warn(f"DAB Scan: NO_FCT0_LOCK ch={ch} lastfct0=0 ensemble={ens_id or '0x0000'}")

        if snr >= 2.0 and len(services) == 0:
            log.warn(f"DAB Scan: LOCK_KANDIDAT ch={ch} snr={snr:.1f} keine Services — WAIT_LOCK erhöhen?")

        _last_scan_diag["channels"][ch] = {
            "ensemble": ens_label,
            "ensemble_id": ens_id,
            "services": len(services),
            "snr": snr,
            "freqcorr": freq_corr,
            "gain": rx_gain,
            "ficcrc": fic_crc,
            "lastfct0": last_fct0,
            "service_names": [s["name"] for s in services],
            "lock_state": lock_state,
        }
        _write_scan_diag_file()
        return services, ens_label, ens_id, snr

    # Regionalscan
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
                "service_id": str(svc["service_id"] or "").strip(),
                "url_mp3":    "",  # v0.9.21: welle-cli -p → kein HTTP mehr
                "id":         f"dab_{svc['service_id'] or svc['name']}",
                "favorite":   False,
                "enabled":    True,
            }
            if not any(
                (str(e.get("service_id","") or "").strip() == entry["service_id"] and entry["service_id"])
                or (e["name"] == svc["name"] and e["channel"] == ch)
                for e in found
            ):
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
            scanned.append(ch)
            for svc in svcs:
                entry = {
                    "name":       svc["name"],
                    "channel":    ch,
                    "ensemble":   ens_label,
                    "service_id": str(svc["service_id"] or "").strip(),
                    "url_mp3":    "",  # v0.9.21: welle-cli -p → kein HTTP mehr
                    "id":         f"dab_{svc['service_id'] or svc['name']}",
                    "favorite":   False,
                    "enabled":    True,
                }
                if not any(
                    (str(e.get("service_id","") or "").strip() == entry["service_id"] and entry["service_id"])
                    or (e["name"] == svc["name"] and e["channel"] == ch)
                    for e in found
                ):
                    found.append(entry)

    _last_scan_diag["found"] = len(found)
    log.info(f"DAB Scan: FERTIG — {len(found)} Sender auf {len(scanned)} Kanälen (WAIT_LOCK={WAIT_LOCK}s PORT={SCAN_PORT})")
    _write_scan_diag_file()
    return found


def scan_dab_channels_full(progress_cb=None):
    all_channels = [
        "5A","5B","5C","5D","6A","6B","6C","6D",
        "7A","7B","7C","7D","8A","8B","8C","8D",
        "9A","9B","9C","9D","10A","10B","10C","10D",
        "11A","11B","11C","11D","12A","12B","12C","12D",
        "13A","13B","13C","13D","13E","13F",
    ]
    return scan_dab_channels(progress_cb=progress_cb, channels=all_channels)


# ──────────────────────────────────────────────────────────────────────────────
# Playback
# ──────────────────────────────────────────────────────────────────────────────

def play_station(station, S, settings=None):
    global _player_proc
    stop(S)

    if settings is not None:
        # v0.9.27: last_source setzen + vollständige Stationsdaten + save_settings()
        settings["last_source"] = "dab"
        settings["last_dab_station"] = {
            "name":       station.get("name", ""),
            "channel":    station.get("channel", ""),
            "service_id": station.get("service_id", ""),
            "ensemble":   station.get("ensemble", ""),
            "url_mp3":    station.get("url_mp3", ""),
        }
        try:
            from settings import save_settings as _save_s
            _save_s(settings)
        except Exception as _se:
            log.warn(f"DAB: save_settings failed: {_se}")

    ch   = station.get("channel", "")
    name = station.get("name", "")
    sid  = str(station.get("service_id", "") or "").strip()

    if not ch:
        log.error(f"DAB play: kein channel station={station!r}")
        return

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
        _mpv_raw  = _audio.get_mpv_args(settings, source="dab")
        # Index 0: env-prefix (leer bei ALSA-Modus) oder "PULSE_SERVER=..." bei BT
        _mpv_env  = _mpv_raw[0] if _mpv_raw and not _mpv_raw[0].startswith("--") else ""
        # Leeren ersten Eintrag herausfiltern
        _mpv_opts = [a for a in (_mpv_raw[1:] if _mpv_env is not None else _mpv_raw) if a]
        _mpv_args = " ".join(_mpv_opts)
        _gain     = _get_dab_gain(settings)

        _adec = _audio.get_last_decision()
        if _adec.get("reason") == "pulseaudio_inactive" or _adec.get("effective") == "none":
            S["radio_playing"] = False
            S["radio_station"] = "Audiofehler: PulseAudio inaktiv"
            S["radio_name"]    = name
            S["radio_type"]    = "DAB"
            S["control_context"] = "radio_dab"
            log.error(f"DAB strict-mode: Abbruch name={name!r} channel={ch} sid={sid!r} reason={_adec.get('reason','?')}")
            return

        import shlex
        _ppm_val = int(settings.get("ppm_correction", 0)) if settings else 0
        _name_q  = shlex.quote(name)

        # v0.9.22: welle-cli OHNE PulseAudio-Env starten.
        # PULSE_SERVER/PULSE_SINK verursachen bei RTL2838 einen OFDM-Sync-Fehler.
        # welle-cli läuft via ALSA → PulseAudio routet automatisch (Klinke oder BT).
        # Das ist identisch zum manuellen Start der funktioniert:
        #   welle-cli -c 10A -p "NAME"  (kein PULSE_SERVER, kein PULSE_SINK)
        # v0.9.26 KORREKTUR: -p und -w sind NICHT kombinierbar (welle-io.md §2)
        # -p → AlsaProgrammeHandler (ALSA-Audio direkt)
        # -w → WebRadioInterface (HTTP-Server)
        # Diese sind zwei separate Betriebspfade — gleichzeitig nicht unterstützt.
        # DLS-Polling via mux.json entfällt damit im ALSA-Modus.
        # DLS wird stattdessen aus dem stderr-Log geparst (Abschnitt _dls_from_stderr).
        _welle_cmd = (
            "welle-cli -c " + ch + " -g " + _gain +
            " -p " + _name_q +
            " < /dev/null" +
            " 2>/tmp/pidrive_dab_welle.err"
        )

        log.info(f"DAB play: START name={name!r} channel={ch} sid={sid!r} gain={_gain}")
        if _ppm_val != 0:
            log.info(f"DAB play: PPM konfiguriert: {_ppm_val} ppm")

        if _rtlsdr:
            try:
                _rtlsdr.start_process(
                    _welle_cmd, owner="dab_play", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception as _e:
                S["radio_playing"] = False
                S["radio_station"] = "RTL-SDR Lock-Fehler"
                log.error("DAB: RTL-SDR Lock: " + str(_e))
                return
        else:
            _player_proc = subprocess.Popen(
                _welle_cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # v0.9.31: PRIORITÄT 3 — DAB Lock-Wartezustand (5-8s, dann commit)
        # Phasen: starting → syncing → locked/failed
        _dab_state = "starting"
        _sync_ok   = False
        _last_err  = ""
        _lock_wait_max = 12   # max 12s auf Lock warten

        for _ws in range(_lock_wait_max):
            time.sleep(1)
            if not os.path.exists("/tmp/pidrive_dab_welle.err"):
                continue
            try:
                with open("/tmp/pidrive_dab_welle.err", "r", encoding="utf-8", errors="ignore") as _f:
                    _recent = _f.read()[-3000:]
                lines = [l.strip() for l in _recent.splitlines() if l.strip()]
                # Lock-Kriterien
                if any("found sync" in l.lower() or "superframe sync" in l.lower()
                       or "audio service" in l.lower() for l in lines[-5:]):
                    _sync_ok   = True
                    _dab_state = "locked"
                    log.info(f"DAB Lock: OK nach {_ws+1}s (ch={ch} sid={sid})")
                    break
                elif _ws >= 3:
                    _dab_state = "syncing"
                for _ln in lines[-3:]:
                    if "failed" in _ln.lower() or "lost" in _ln.lower():
                        _last_err = _ln[:120]
            except Exception:
                pass

        if not _sync_ok:
            _dab_state = "no_lock"
            log.warn(f"DAB: kein stabiler Lock nach {_lock_wait_max}s (ch={ch} sid={sid}) — continue anyway")

        # Log letzten Stderr
        try:
            with open("/tmp/pidrive_dab_welle.err", "r", encoding="utf-8", errors="ignore") as _f:
                _err_lines = [l.strip() for l in _f.readlines()[-5:] if l.strip()]
            for _ln in _err_lines:
                log.info("DAB welle-cli: " + _ln[:200])
        except Exception:
            pass

        # v0.9.26: Play-Debug-JSON für Diagnose
        try:
            import json as _json_dbg
            _dbg = {
                "name": name, "channel": ch, "service_id": sid,
                "gain": _gain,
                "ppm": str(settings.get("ppm_correction", 0) if settings else 0),
                "started_ts": time.time(),
                "sync_ok": _sync_ok,
                "dab_state": _dab_state,  # v0.9.31: starting|syncing|locked|no_lock
                "last_error_line": _last_err,
            }
            with open("/tmp/pidrive_dab_play_debug.json", "w") as _dbgf:
                _json_dbg.dump(_dbg, _dbgf)
        except Exception:
            pass



        S["radio_playing"] = True
        S["radio_station"] = "DAB: " + name
        S["radio_name"]    = name
        S["radio_type"]    = "DAB"
        S["track"]         = ""
        S["artist"]        = ""
        S["control_context"] = "radio_dab"
        log.action("DAB", "Wiedergabe: " + name + " (" + ch + ", sid=" + (sid or "-") + ")")

        # v0.9.15: DLS Metadaten-Polling (Dynamic Label Service = Lied/Artist vom Sender)
        # welle-cli liefert DLS-Text per mux.json → alle 8s pollen und S[track]/S[artist] setzen
        def _dls_poller(_name=name, _sid=str(sid or "").strip().lower(), _port=7981):
            # v0.9.26: DLS via mux.json nicht verfügbar im ALSA-Modus (-p ohne -w)
            # welle-cli -p und -w sind zwei getrennte Betriebspfade (welle-io.md §2).
            # DLS wird via stderr-Tail angezeigt sobald welle-cli DLS-Zeilen ausgibt.
            # Vorerst: Poller als kein-op, nur als Hook für spätere Erweiterung.
            import time as _tm
            _last_dls = ""
            # Kurz warten damit welle-cli starten kann
            _tm.sleep(5)
            # Laufzeit-Loop: DLS aus welle-cli stderr lesen (welle-cli schreibt DLS
            # nicht standardmäßig in stderr im -p Modus — TODO wenn welle-cli DLS
            # in stderr-Ausgabe dokumentiert ist)
            while S.get("radio_playing") and S.get("radio_name") == _name:
                _tm.sleep(10)
                if not (S.get("radio_playing") and S.get("radio_name") == _name):
                    break
                # DLS currently not available in ALSA-direct mode (-p without -w)
                # Placeholder for future stderr-based DLS parsing

        import threading as _thr_dls
        _thr_dls.Thread(target=_dls_poller, daemon=True).start()

    except Exception as e:
        S["radio_playing"] = False
        S["radio_station"] = "DAB Fehler"
        log.error(f"DAB play Fehler: {e}")


def stop(S):
    global _player_proc, _scan_running
    log.info("DAB stop: requested")
    _scan_running = False

    # mpv zuerst stoppen (gibt USB frei wenn er via Popen läuft)
    if _player_proc:
        try:
            _player_proc.terminate()
            _player_proc.wait(timeout=2)
        except Exception:
            pass

    # welle-cli via rtlsdr-Lock beenden (gibt RTL-SDR USB frei)
    if _rtlsdr:
        try:
            _rtlsdr.stop_process()
        except Exception:
            pass

    # Sicherheits-pkill synchron — wichtig bei Senderwechsel (v0.9.17)
    import subprocess as _sp
    _sp.run("pkill -f welle-cli 2>/dev/null",
            shell=True, timeout=3, capture_output=True)
    _sp.run("pkill -f 'mpv --no-video --really-quiet --title=pidrive_dab' 2>/dev/null",
            shell=True, timeout=3, capture_output=True)

    _player_proc = None
    S["radio_playing"] = False
    if S.get("radio_type") == "DAB":
        S["radio_station"] = ""

    # RTL-SDR USB braucht ~1s zum Freigeben — sonst usb_claim_interface -6 beim nächsten Start
    time.sleep(1.0)
    log.info("DAB stop: done")


def play_by_name(name, S, service_id=""):
    """
    DAB Station bevorzugt über service_id, sonst über Name.
    """
    path = os.path.join(os.path.dirname(__file__), "../config/dab_stations.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
        stations = data.get("stations", data) if isinstance(data, dict) else data
        service_id = str(service_id or "").strip().lower()

        if service_id:
            for s in stations:
                sid = str(s.get("service_id", "") or "").strip().lower()
                if sid and sid == service_id:
                    log.info(f"DAB play_by_name service_id match name={name!r} sid={service_id}")
                    play_station(_normalize_station(s), S)
                    return

        for s in stations:
            if s.get("name", "") == name:
                log.info(f"DAB play_by_name fallback name={name!r} service_id leer")
                play_station(_normalize_station(s), S)
                return

    except Exception as e:
        log.error(f"DAB play_by_name: {e}")


def play_next(S, stations):
    if not stations:
        return
    current = S.get("radio_station", "")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name", "") == current:
            idx = (i + 1) % len(stations)
            break
    play_station(_normalize_station(stations[idx]), S)


def play_prev(S, stations):
    if not stations:
        return
    current = S.get("radio_station", "")
    idx = 0
    for i, s in enumerate(stations):
        if s.get("name", "") == current:
            idx = (i - 1) % len(stations)
            break
    play_station(_normalize_station(stations[idx]), S)