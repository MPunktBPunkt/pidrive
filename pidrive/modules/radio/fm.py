import os
"""
modules/fm.py — FM-Wiedergabe via rtl_fm | mpv (ALSA-direkt)
Aufrufer: main_core.py
Abhängig von: modules/audio.py, modules/source_state.py, ipc.py
Schreibt: settings[last_fm_station], settings[last_source]
Hinweis: kein RDS — rtl_fm liefert nur Audio-PCM an PiDrive
"""


try:
    from modules.platform import CAPS as _CAPS
except ImportError:
    _CAPS = None

import subprocess
try:
    from modules.radio import rtlsdr as _rtlsdr
except Exception as _e:
    _rtlsdr = None
    try:
        from modules import degraded_imports as _deg
        _deg.report("modules.radio.rtlsdr", str(_e))
    except Exception:
        pass
import os
import json
import time
import ipc
import log

STATIONS_FILE = os.path.join(
    os.path.dirname(__file__), "../config/fm_stations.json")

_player_proc      = None
_rtl_proc         = None
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


# ── FM Audio-Filter (Rauschen / Höhen dämpfen) ──────────────────────────────
# WBFM → 32 kHz PCM. Mildes HP/LP schneidet Rumpeln und Zischen bei schwachen Sendern.
FM_HP_STEPS = (20, 40, 60, 80, 100, 120)
FM_LP_STEPS = (8000, 10000, 12000, 14000, 15000, 16000)


def _nearest_step(val, steps):
    try:
        v = int(val)
    except Exception:
        v = int(steps[len(steps) // 2])
    return min(steps, key=lambda s: abs(int(s) - v))


def _step_in_list(val, steps, delta: int):
    cur = _nearest_step(val, steps)
    idx = list(steps).index(cur)
    idx = max(0, min(len(steps) - 1, idx + int(delta)))
    return int(steps[idx])


def _get_fm_hp(settings=None, S=None):
    if S and isinstance(S.get("fm_tune"), dict) and "hp_hz" in S["fm_tune"]:
        try:
            return _nearest_step(S["fm_tune"]["hp_hz"], FM_HP_STEPS)
        except Exception:
            pass
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    try:
        raw = int((settings or {}).get("fm_hp_hz", 60))
    except Exception:
        raw = 60
    return _nearest_step(raw, FM_HP_STEPS)


def _get_fm_lp(settings=None, S=None):
    if S and isinstance(S.get("fm_tune"), dict) and "lp_hz" in S["fm_tune"]:
        try:
            return _nearest_step(S["fm_tune"]["lp_hz"], FM_LP_STEPS)
        except Exception:
            pass
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    try:
        raw = int((settings or {}).get("fm_lp_hz", 12000))
    except Exception:
        raw = 12000
    return _nearest_step(raw, FM_LP_STEPS)


def _fm_af_string(settings=None, S=None):
    hp = _get_fm_hp(settings, S=S)
    lp = _get_fm_lp(settings, S=S)
    if lp <= hp:
        lp = max(hp + 1000, 8000)
    return f"lavfi=[highpass=f={hp},lowpass=f={lp}]"


def _fm_default_dict(settings=None):
    return {
        "hp_hz": _get_fm_hp(settings, S=None),
        "lp_hz": _get_fm_lp(settings, S=None),
    }


def _mark_fm_dirty(tune, settings=None):
    d = _fm_default_dict(settings)
    tune["dirty"] = any(int(tune.get(k, d[k])) != int(d[k]) for k in d)
    return tune["dirty"]


def _ensure_fm_tune(S, settings=None):
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    tune = S.setdefault("fm_tune", {})
    defs = _fm_default_dict(settings)
    for k, v in defs.items():
        if k not in tune:
            tune[k] = v
    _mark_fm_dirty(tune, settings)
    return tune


def seed_fm_tune_from_defaults(S, settings=None):
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    defs = _fm_default_dict(settings)
    defs["dirty"] = False
    S["fm_tune"] = defs
    return dict(S["fm_tune"])


def get_fm_tune_params(settings=None, S=None):
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    if S is not None:
        tune = _ensure_fm_tune(S, settings)
    else:
        tune = dict(_fm_default_dict(settings))
        tune["dirty"] = False
    defs = _fm_default_dict(settings)
    return {
        "hp_hz": int(tune.get("hp_hz", defs["hp_hz"])),
        "lp_hz": int(tune.get("lp_hz", defs["lp_hz"])),
        "dirty": bool(tune.get("dirty")),
        "default_hp_hz": defs["hp_hz"],
        "default_lp_hz": defs["lp_hz"],
        "hp_steps": list(FM_HP_STEPS),
        "lp_steps": list(FM_LP_STEPS),
    }


def step_fm_hp(delta: int, settings=None, S=None):
    if settings is None:
        from settings import load_settings
        settings = load_settings()
    if S is None:
        return _get_fm_hp(settings)
    tune = _ensure_fm_tune(S, settings)
    new = _step_in_list(tune["hp_hz"], FM_HP_STEPS, delta)
    if new >= int(tune.get("lp_hz", 12000)):
        return int(tune["hp_hz"])
    tune["hp_hz"] = new
    _mark_fm_dirty(tune, settings)
    return new


def step_fm_lp(delta: int, settings=None, S=None):
    if settings is None:
        from settings import load_settings
        settings = load_settings()
    if S is None:
        return _get_fm_lp(settings)
    tune = _ensure_fm_tune(S, settings)
    new = _step_in_list(tune["lp_hz"], FM_LP_STEPS, delta)
    if new <= int(tune.get("hp_hz", 60)):
        return int(tune["lp_hz"])
    tune["lp_hz"] = new
    _mark_fm_dirty(tune, settings)
    return new


def save_fm_tune_as_defaults(S, settings=None):
    if settings is None:
        from settings import load_settings
        settings = load_settings()
    tune = _ensure_fm_tune(S, settings)
    settings["fm_hp_hz"] = int(tune["hp_hz"])
    settings["fm_lp_hz"] = int(tune["lp_hz"])
    try:
        from settings import save_settings
        save_settings(settings)
    except Exception:
        pass
    tune["dirty"] = False
    return {"hp_hz": settings["fm_hp_hz"], "lp_hz": settings["fm_lp_hz"]}


def retune_fm_if_playing(S, settings=None):
    """Wenn FM läuft: mit aktuellem HP/LP neu starten."""
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    if S.get("radio_type") != "FM" or not S.get("radio_playing"):
        return False
    last = settings.get("last_fm_station") if isinstance(settings, dict) else None
    if not isinstance(last, dict) or not _get_freq(last):
        # Fallback aus S
        name = str(S.get("radio_name") or S.get("radio_station") or "FM")
        # radio_station oft "Name · 104.4"
        freq = None
        try:
            rs = str(S.get("radio_station") or "")
            for part in rs.replace(",", ".").split():
                try:
                    f = float(part)
                    if 87.0 <= f <= 108.5:
                        freq = f
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if freq is None:
            return False
        last = {"name": name, "freq": freq}
    # Guard in play_station umgehen: stop setzt playing=False
    stop(S)
    return play_station(last, S, settings) is not False


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
        _fm_tmp = STATIONS_FILE + ".tmp"
        with open(_fm_tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(_fm_tmp, STATIONS_FILE)
        log.info(f"FM: {len(stations)} Stationen gespeichert")
    except Exception as e:
        log.error(f"FM Stationen speichern: {e}")


def update_rds_metadata(station_name: str, S: dict):
    """
    FM RDS-Hook (v0.9.26) — aktuell No-Op.
    rtl_fm → mpv Pipe liefert nur Audio, kein RDS an PiDrive.
    Für RDS: separater Decoder (redsea, rtl_fm -R) nötig.
    RDS-Felder: PS (Name), RT (Radiotext), RT+ (Artist/Titel).
    """
    pass  # Kein Fake-RDS


def play_station(station, S, settings=None):
    """FM Station abspielen via rtl_fm | mpv --ao=pulse (v0.8.11: einheitlich)."""
    global _player_proc, _rtl_proc, _last_start_ts, _last_station_key

    freq = _get_freq(station)
    name = station.get("name", "")

    if settings is not None:
        # v0.9.27: last_source setzen + save_settings()
        settings["last_source"] = "fm"
        settings["last_fm_station"] = {
            "name": station.get("name", ""),
            "freq": station.get("freq", ""),
        }
        try:
            from settings import save_settings as _save_s
            _save_s(settings)
        except Exception as _se:
            log.warn(f"FM: save_settings failed: {_se}")

    if not freq:
        log.error(f"FM play: keine Frequenz station={station!r}")
        return False

    # v0.9.5: Low-Risk Start-Guard — gleiche Station läuft bereits
    try:
        if (S.get("radio_playing")
                and S.get("radio_type") == "FM"
                and S.get("radio_name") == name
                and str(freq) in S.get("radio_station", "")):
            log.info(f"FM play: bereits aktiv — kein Neustart name={name!r} freq={freq}")
            return True
    except Exception:
        pass

    try:
        freq_f = float(freq)
    except Exception:
        log.error(f"FM play: ungültige Frequenz: {freq!r}")
        return False

    # Doppelstart-Entprellung: gleicher Sender innerhalb 2s ignorieren
    now     = time.time()
    cur_key = _station_key(name, freq_f)
    if (S.get("radio_type") == "FM"
            and S.get("radio_playing")
            and cur_key == _last_station_key
            and (now - _last_start_ts) < 2.0):
        log.info(f"FM play: entprellt (Doppelstart) name={name!r} freq={freq_f}")
        return False

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
                return False

            # Warten auf echte Freigabe nach stop() — verhindert Race beim Senderwechsel
            if not _rtlsdr.wait_until_free(timeout=2.5, interval=0.05):
                log.warn(f"FM: RTL-SDR nach stop() noch belegt — harter Cleanup für {name} @ {freq_f}")
                try:
                    _rtlsdr.stop_process()
                except Exception:
                    pass
                _bg("pkill -f rtl_fm 2>/dev/null")
                _bg("pkill -f welle-cli 2>/dev/null")  # ALSA-Konflikt verhindern
                _bg("pkill -f aplay 2>/dev/null")
                _bg("pkill -f 'mpv --no-video --really-quiet --title=pidrive_fm' 2>/dev/null")
                time.sleep(0.35)

            if not _rtlsdr.wait_until_free(timeout=1.5, interval=0.05):
                S["radio_playing"] = False
                S["radio_type"]    = "FM"   # Label korrekt auch bei Fehler
                S["source_error"]  = "RTL-SDR belegt"
                log.warn(f"FM: RTL-SDR belegt vor play {name} @ {freq_f}")
                return False

        from modules import audio as _audio
        try:
            _mpv_parts = _audio.get_mpv_args(settings=settings, source="fm")
        except Exception as _ae:
            log.warn(f"FM: get_mpv_args failed: {_ae}")
            _mpv_parts = ["PULSE_SERVER=unix:/var/run/pulse/native", "--ao=pulse"]
        _mpv_env_str = (_mpv_parts[0] if _mpv_parts else "") or ""
        _mpv_extra = [a for a in (_mpv_parts[1:] if len(_mpv_parts) > 1 else ["--ao=pulse"]) if a]
        if "--ao=pulse" not in _mpv_extra and not any(a.startswith("--ao=") for a in _mpv_extra):
            _mpv_extra = ["--ao=pulse"] + _mpv_extra

        # Audio-Filter: HP/LP gegen Rauschen (Live aus fm_tune / Defaults)
        _mpv_af = _fm_af_string(settings, S=S)
        if _mpv_af and not any(a.startswith("--af=") for a in _mpv_extra):
            _mpv_extra = [f"--af={_mpv_af}"] + _mpv_extra

        # Gain und PPM aus Settings aufbauen
        _gain_val  = int(settings.get("fm_gain", -1) if settings else -1)
        # ppm_correction ist der kanonische Key; "ppm" nur Alias
        _ppm_val = 0
        _rtl_sr = 170000
        _offset = True
        if settings:
            _ppm_val = int(settings.get("ppm_correction", settings.get("ppm", 0)) or 0)
            try:
                _rtl_sr = int(settings.get("fm_rtl_sr", 170000) or 170000)
            except Exception:
                _rtl_sr = 170000
            _rtl_sr = max(100000, min(_rtl_sr, 320000))
            _offset = bool(settings.get("rtl_offset_tuning", True))

        def _build_rtl_cmd():
            # -M wbfm ≈ 170k + deemp; -s überschreibt Bandbreite, -E offset gegen DC-Spike
            cmd = ["rtl_fm", "-M", "wbfm",
                   "-f", freq_hz, "-s", str(_rtl_sr), "-r", "32000",
                   "-A", "fast"]
            if _offset:
                cmd += ["-E", "offset"]
            cmd += ["-"]
            if _gain_val >= 0:
                cmd += ["-g", str(_gain_val)]
            if _ppm_val:
                cmd += ["-p", str(_ppm_val)]
            return cmd

        mpv_cmd = ["mpv", "--no-video", "--really-quiet",
                   "--title=pidrive_fm",
                   "--demuxer=rawaudio", "--demuxer-rawaudio-rate=32000",
                   "--demuxer-rawaudio-channels=1"] + _mpv_extra + ["-"]
        mpv_env = dict(os.environ, PULSE_SERVER="unix:/var/run/pulse/native")
        # PULSE_SINK=... aus get_mpv_args-Env-String übernehmen
        for _tok in _mpv_env_str.split():
            if "=" in _tok:
                _k, _v = _tok.split("=", 1)
                mpv_env[_k] = _v

        if _ppm_val or _gain_val >= 0:
            log.info(f"FM play: PPM={_ppm_val} gain={_gain_val} sr={_rtl_sr} offset={_offset}")

        def _proc_wchar(pid):
            """Bytes geschrieben (inkl. Pipe) — write_bytes zählt Pipes nicht."""
            try:
                with open(f"/proc/{pid}/io", "r", encoding="utf-8") as f:
                    for ln in f:
                        if ln.startswith("wchar:"):
                            return int(ln.split(":", 1)[1].strip())
            except Exception:
                return -1
            return -1

        def _start_pipe():
            global _player_proc, _rtl_proc
            rtl_cmd = _build_rtl_cmd()
            log.info(f"FM play: Popen-Pipe freq_hz={freq_hz}")
            rtl = subprocess.Popen(
                rtl_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            mpv = subprocess.Popen(
                mpv_cmd, stdin=rtl.stdout,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=mpv_env
            )
            rtl.stdout.close()
            _player_proc = mpv
            _rtl_proc = rtl
            if _rtlsdr:
                try:
                    _rtlsdr._LOCK_REGISTRY["proc"] = rtl
                    _rtlsdr._LOCK_REGISTRY["proc_name"] = "fm"
                    _rtlsdr._LOCK_REGISTRY["started_ts"] = int(time.time())
                except Exception:
                    pass
            return rtl, mpv

        _rtl_proc_local, _mpv_proc = _start_pipe()

        # Sample-Check kurz; USB-Reset nur bei wchar==0 (nicht bei jedem Senderwechsel).
        _check_s = 0.7 if _last_station_key else 1.2
        time.sleep(_check_s)
        _wc = _proc_wchar(_rtl_proc_local.pid) if _rtl_proc_local.pid else -1
        _alive = (_rtl_proc_local.poll() is None) and (_mpv_proc.poll() is None)
        if _alive and _wc == 0:
            log.warn(f"FM: rtl_fm liefert keine Samples (wchar={_wc}) — USB-Reset + Retry")
            try:
                stop(S)
            except Exception:
                pass
            try:
                if _rtlsdr:
                    _rr = _rtlsdr.usb_reset()
                    log.info(f"FM: usb_reset → {(_rr or {}).get('ok')} steps={(_rr or {}).get('steps')}")
            except Exception as _re:
                log.warn(f"FM: usb_reset failed: {_re}")
            time.sleep(2.0)
            _rtl_proc_local, _mpv_proc = _start_pipe()
            time.sleep(1.0)
            _wc = _proc_wchar(_rtl_proc_local.pid) if _rtl_proc_local.pid else -1
            if _wc == 0:
                log.warn(f"FM: nach Reset weiterhin keine Samples (wchar={_wc})")
            else:
                log.info(f"FM: Samples ok nach Reset wchar={_wc}")
        elif _wc > 0:
            log.info(f"FM: Samples ok wchar={_wc}")

        S["radio_playing"]  = True
        S["radio_station"]  = f"FM: {name} ({freq_f:.1f} MHz)"
        S["radio_name"]     = name
        S["radio_type"]     = "FM"
        S["track"]          = ""
        S["artist"]         = ""
        S["control_context"] = "radio_fm"
        S.pop("source_error", None)
        _last_start_ts      = now
        _last_station_key   = cur_key
        # v0.9.26: RDS-Hook — aktuell No-Op (rtl_fm liefert kein RDS)
        update_rds_metadata(name, S)
        # Q-J / D2: zweiter Metadaten-Push nachdem Abstimmung fertig ist
        S["_mpris_force_push"] = True
        log.action("FM", f"Wiedergabe: {name} ({freq_f:.1f} MHz)")
        return True

    except Exception as e:
        log.error(f"FM play Fehler: {e}")
        raise  # re-raise → td_nav überspringt commit_source("fm")


def stop(S):
    global _player_proc, _rtl_proc
    log.info("FM stop: requested")
    try:
        if _rtlsdr:
            _rtlsdr.stop_process()
    except Exception as e:
        log.warn(f"FM stop: rtlsdr.stop_process: {e}")
    # Eigene Popen-Handles zuerst wait() — sonst bleiben Zombies und blockieren Busy
    for _label, _proc in (("rtl_fm", _rtl_proc), ("mpv", _player_proc)):
        if not _proc:
            continue
        try:
            if _proc.poll() is None:
                try:
                    _proc.terminate()
                    _proc.wait(timeout=1.5)
                except Exception:
                    try:
                        _proc.kill()
                        _proc.wait(timeout=1.0)
                    except Exception:
                        pass
            else:
                try:
                    _proc.wait(timeout=0.3)
                except Exception:
                    pass
        except Exception as e:
            log.warn(f"FM stop: {_label} reap: {e}")
    _rtl_proc = None
    _player_proc = None
    _bg("pkill -f pidrive_fm 2>/dev/null")
    _bg("pkill -f rtl_fm 2>/dev/null")
    _bg("pkill -f welle-cli 2>/dev/null")   # welle-cli haelt ALSA-Karte belegt
    _bg("pkill -f aplay 2>/dev/null")
    _bg("pkill -f 'mpv --no-video --really-quiet --title=pidrive_fm' 2>/dev/null")
    # Kurzes Warten auf echte Freigabe — verhindert sofortiges Busy beim Folgestart
    try:
        if _rtlsdr:
            _rtlsdr.wait_until_free(timeout=3.0, interval=0.1)
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


def _current_freq_mhz(S, settings=None) -> float:
    """Aktuelle FM-Frequenz aus Status oder last_fm_station, sonst 87.5."""
    for src in (
        (S or {}).get("radio_station"),
        ((settings or {}).get("last_fm_station") or {}).get("freq"),
    ):
        if src is None:
            continue
        text = str(src)
        # "FM: Name (99.4 MHz)" oder "99.4"
        try:
            if "(" in text and "mhz" in text.lower():
                part = text.split("(")[-1].replace(")", "").lower().replace("mhz", "").strip()
                return float(part)
            return float(text.replace("MHz", "").replace("mhz", "").strip())
        except Exception:
            continue
    return 87.5


def step_freq(S, settings, delta_mhz: float) -> bool:
    """
    FM-Rasterschritt (Q-H): ±0.1 / ±1.0 MHz, Grenzen 87.5–108.0, kein Umlauf.
    """
    cur = _current_freq_mhz(S, settings)
    try:
        delta = float(delta_mhz)
    except Exception:
        return False
    new = round(cur + delta, 1)
    new = max(87.5, min(108.0, new))
    name = f"{new:.1f} MHz"
    log.info(f"FM step: {cur:.1f} {delta:+.1f} → {new:.1f}")
    return bool(play_station({"name": name, "freq": f"{new:.1f}"}, S, settings))


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
               f"-s 170000 -E offset -l 30 - 2>/dev/null | wc -c")
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
