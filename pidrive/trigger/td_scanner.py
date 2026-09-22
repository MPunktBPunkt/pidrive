#!/usr/bin/env python3
"""td_scanner.py — Scanner-Steuerung  v0.10.55"""
import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log, ipc
from settings import save_settings
from modules import source_state
from modules import (
    wifi, bluetooth, audio, system as sys_mod,
    webradio, update, favorites
)
from modules.radio import dab, fm, scanner
from modules.playback_meta import clear_playback_metadata


def _stop_other_sources(S):
    """Webradio/DAB/FM beenden bevor der Scanner übernimmt."""
    try:
        webradio.stop(S)
    except Exception as e:
        log.warn(f"scanner: webradio.stop: {e}")
    try:
        dab.stop(S)
    except Exception as e:
        log.warn(f"scanner: dab.stop: {e}")
    try:
        fm.stop(S)
    except Exception as e:
        log.warn(f"scanner: fm.stop: {e}")
    S["radio_playing"] = False
    S["radio_name"] = ""
    if str(S.get("radio_type", "")).upper() not in ("SCANNER",):
        S["radio_type"] = ""
    clear_playback_metadata(S)


def _clear_scanner_metadata(S):
    for _sk in ("radio_name", "radio_type", "track", "artist", "source_error"):
        if _sk in ("radio_name", "radio_type"):
            S[_sk] = ""
        else:
            S.pop(_sk, None)


def _blocked(title="Scanner"):
    """W7/Z2: Ablehnung sichtbar melden (Muster td_radio)."""
    ipc.write_progress(title, "Blockiert", color="orange")
    _time_mod.sleep(2)
    ipc.clear_progress()


def handle(cmd, menu_state, store, S, settings, bg):
    # ── Scanner ─────────────────────────────────────────────────────────────
    if cmd == "scanner_stop":
        try:
            scanner.stop_pmr_monitor(S, join=False)
        except Exception:
            pass
        try:
            scanner.stop_airband_monitor(S, join=False)
        except Exception:
            pass
        scanner.stop(S)
        source_state.commit_source("idle")
        S["radio_playing"] = False
        S["radio_station"] = ""
        S["radio_name"] = ""
        S["radio_type"] = ""
        S["control_context"] = "idle"
        log.info("Scanner via scanner_stop beendet")

    elif cmd == "pmr_monitor_start":
        def _pmr_mon_start():
            _stop_other_sources(S)
            # Frische Settings von Disk (CLI kann --no-tune schon gespeichert haben)
            try:
                from settings import load_settings as _ls
                settings.update(_ls())
            except Exception:
                pass
            autotune = bool(settings.get("scanner_pmr_autotune", True))
            hold = settings.get("scanner_pmr_hold_s", 15)
            try:
                hold = float(hold)
            except Exception:
                hold = 15.0
            try:
                watch_s = float(settings.get("scanner_pmr_watch_s", 1.0))
            except Exception:
                watch_s = 1.0
            try:
                trigger_on = float(settings.get("scanner_pmr_trigger_on_db", 25.0))
            except Exception:
                trigger_on = 25.0
            try:
                trigger_off = float(settings.get("scanner_pmr_trigger_off_db", 14.0))
            except Exception:
                trigger_off = 14.0
            ok = scanner.start_pmr_monitor(
                S, settings, band_id="pmr446",
                autotune=autotune, hold_s=hold,
                watch_s=watch_s,
                trigger_on_db=trigger_on,
                trigger_off_db=trigger_off,
            )
            log.info(
                f"pmr_monitor_start: {'ok' if ok else 'already_running'} "
                f"autotune={autotune} hold={hold} watch={watch_s} "
                f"trigger_on={trigger_on} trigger_off={trigger_off}"
            )
            ipc.write_progress(
                "PMR-Monitor",
                (
                    f"on={trigger_on:g}dB watch={watch_s:g}s"
                    if ok or scanner.is_pmr_monitor_running()
                    else "Fehler"
                ),
                color="green" if ok or scanner.is_pmr_monitor_running() else "orange",
            )
            _time_mod.sleep(1.2)
            ipc.clear_progress()
        bg(_pmr_mon_start)

    elif cmd == "pmr_monitor_stop":
        def _pmr_mon_stop():
            scanner.stop_pmr_monitor(S, join=True)
            scanner.stop(S)
            source_state.commit_source("idle")
            S["radio_playing"] = False
            S["radio_type"] = ""
            log.info("pmr_monitor_stop")
        bg(_pmr_mon_stop)

    elif cmd == "airband_monitor_start":
        def _air_mon_start():
            _stop_other_sources(S)
            try:
                from settings import load_settings as _ls
                settings.update(_ls())
            except Exception:
                pass
            autotune = bool(settings.get("scanner_airband_autotune", True))
            try:
                hold = float(settings.get("scanner_airband_hold_s", 20))
            except Exception:
                hold = 20.0
            ok = scanner.start_airband_monitor(
                S, settings, autotune=autotune, hold_s=hold,
            )
            log.info(
                f"airband_monitor_start: {'ok' if ok else 'already_running'} "
                f"autotune={autotune} hold={hold}"
            )
            running = ok or scanner.is_airband_monitor_running()
            ipc.write_progress(
                "Airband-Monitor",
                f"hold={hold:g}s" if running else "Fehler",
                color="green" if running else "orange",
            )
            _time_mod.sleep(1.2)
            ipc.clear_progress()
        bg(_air_mon_start)

    elif cmd == "airband_monitor_stop":
        def _air_mon_stop():
            scanner.stop_airband_monitor(S, join=True)
            scanner.stop(S)
            source_state.commit_source("idle")
            S["radio_playing"] = False
            S["radio_type"] = ""
            log.info("airband_monitor_stop")
        bg(_air_mon_stop)

    elif cmd.startswith("scan_up:"):
        band = cmd.split(":", 1)[1]
        # Stale Metadaten aus vorheriger Quelle löschen
        for _sk in ("radio_name", "radio_type", "track", "artist", "source_error"):
            if _sk in ("radio_name", "radio_type"): S[_sk] = ""
            else: S.pop(_sk, None)
        def _scan_up(b=band):
            _stop_other_sources(S)
            if not source_state.begin_transition(f"scan_up:{b}", "scanner"):
                _blocked()
                return
            try:
                scanner.channel_up(b, S, settings)
                S["scanner_band"] = b
                source_state.commit_source("scanner")
            finally:
                source_state.end_transition()
        bg(_scan_up)

    elif cmd.startswith("scan_down:"):
        band = cmd.split(":", 1)[1]
        def _scan_down(b=band):
            _stop_other_sources(S)
            if not source_state.begin_transition(f"scan_down:{b}", "scanner"):
                _blocked()
                return
            try:
                scanner.channel_down(b, S, settings)
                S["scanner_band"] = b
                source_state.commit_source("scanner")
            finally:
                source_state.end_transition()
        bg(_scan_down)

    elif cmd.startswith("scan_next:"):
        band = cmd.split(":", 1)[1]
        for _sk in ("radio_name", "radio_type", "track", "artist", "source_error"):
            if _sk in ("radio_name", "radio_type"): S[_sk] = ""
            else: S.pop(_sk, None)
        def _scan_next(b=band):
            _stop_other_sources(S)
            # Scan ohne Audio — play_freq erst nach Transition (Ownership)
            found = scanner.scan_next(b, S, settings, autoplay=False)
            if found:
                if not source_state.begin_transition(f"scan_next:{b}", "scanner"):
                    _blocked()
                    return
                try:
                    S["scanner_band"] = b
                    rt = scanner._get_band_runtime(b)
                    scanner.play_freq(
                        found["freq"], found["name"], rt["bw"], S,
                        settings=settings,
                        modulation=rt["modulation"], band_id=b,
                        audio_profile=rt["audio_profile"],
                    )
                    source_state.commit_source("scanner")
                finally:
                    source_state.end_transition()
            else:
                log.info(f"scan_next:{b} — kein Treffer")
        bg(_scan_next)

    elif cmd.startswith("scan_prev:"):
        band = cmd.split(":", 1)[1]
        def _scan_prev(b=band):
            _stop_other_sources(S)
            found = scanner.scan_prev(b, S, settings, autoplay=False)
            if found:
                if not source_state.begin_transition(f"scan_prev:{b}", "scanner"):
                    _blocked()
                    return
                try:
                    S["scanner_band"] = b
                    rt = scanner._get_band_runtime(b)
                    scanner.play_freq(
                        found["freq"], found["name"], rt["bw"], S,
                        settings=settings,
                        modulation=rt["modulation"], band_id=b,
                        audio_profile=rt["audio_profile"],
                    )
                    source_state.commit_source("scanner")
                finally:
                    source_state.end_transition()
            else:
                log.info(f"scan_prev:{b} — kein Treffer")
        bg(_scan_prev)

    elif cmd.startswith("scan_jump:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                delta = int(parts[2])
            except Exception:
                delta = 0
            if delta:
                def _scan_jump_fn(b=band, d=delta):
                    _stop_other_sources(S)
                    if not source_state.begin_transition(f"scan_jump:{b}", "scanner"):
                        _blocked()
                        return
                    try:
                        scanner.channel_jump(b, d, S, settings)
                        S["scanner_band"] = b
                        source_state.commit_source("scanner")
                    finally:
                        source_state.end_transition()
                bg(_scan_jump_fn)

    elif cmd.startswith("scan_step:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                delta = float(parts[2])
            except Exception:
                delta = 0.0
            if delta:
                def _scan_step_fn(b=band, d=delta):
                    _stop_other_sources(S)
                    if not source_state.begin_transition(f"scan_step:{b}", "scanner"):
                        _blocked()
                        return
                    try:
                        scanner.freq_step(b, d, S, settings)
                        S["scanner_band"] = b
                        source_state.commit_source("scanner")
                    finally:
                        source_state.end_transition()
                bg(_scan_step_fn)

    elif cmd.startswith("scan_setfreq:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                freq = float(parts[2])
            except Exception:
                freq = 0.0
            if freq:
                def _scan_setfreq_fn(b=band, f=freq):
                    _stop_other_sources(S)
                    _clear_scanner_metadata(S)
                    if not source_state.begin_transition(f"scan_setfreq:{b}", "scanner"):
                        _blocked()
                        return
                    try:
                        scanner.set_freq(b, f, S, settings)
                        S["scanner_band"] = b
                        source_state.commit_source("scanner")
                    finally:
                        source_state.end_transition()
                bg(_scan_setfreq_fn)

    elif cmd.startswith("scan_setch:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                ch_num = int(parts[2])
            except Exception:
                ch_num = 1
            def _scan_setch_fn(b=band, c=ch_num):
                _stop_other_sources(S)
                _clear_scanner_metadata(S)
                if not source_state.begin_transition(f"scan_setch:{b}", "scanner"):
                    _blocked()
                    return
                try:
                    scanner.set_channel(b, c, S, settings)
                    S["scanner_band"] = b
                    source_state.commit_source("scanner")
                finally:
                    source_state.end_transition()
            bg(_scan_setch_fn)

    elif cmd.startswith("scan_inputfreq:"):
        parts = cmd.split(":")
        if len(parts) >= 2:
            band = parts[1]
            def _input_and_set(b=band):
                freq = scanner.freq_input_screen(b, settings)
                if freq is not None:
                    _stop_other_sources(S)
                    if not source_state.begin_transition(f"scan_inputfreq:{b}", "scanner"):
                        _blocked()
                        return
                    try:
                        scanner.set_freq(b, freq, S, settings)
                        S["scanner_band"] = b
                        source_state.commit_source("scanner")
                    finally:
                        source_state.end_transition()
            bg(_input_and_set)

    elif cmd.startswith("set_scanner_squelch:"):
        try:
            sq = int(cmd.split(":", 1)[1])
            settings["scanner_squelch"] = sq
            save_settings(settings)
            S["scanner_squelch"] = sq
            log.info(f"Scanner Squelch gesetzt: {sq}")
            # Laufenden Scanner mit neuem Squelch neu starten
            if source_state.current_source() == "scanner":
                band = S.get("scanner_band")
                if band:
                    import re as _re_sq
                    label = S.get("radio_station") or S.get(f"scanner_{band}", "")
                    m = _re_sq.search(r"([\d.]+)\s*MHz", label or "")
                    if m:
                        scanner.set_freq(band, float(m.group(1)), S, settings)
                        log.info(f"Scanner Squelch angewendet: {sq} auf {band} {m.group(1)} MHz")
        except Exception as e:
            log.error(f"set_scanner_squelch Fehler: {e}")

    elif cmd.startswith("set_ppm:"):
        try:
            ppm = int(cmd.split(":", 1)[1])
            settings["ppm_correction"] = ppm
            save_settings(settings)
            log.info(f"PPM-Korrektur gesetzt: {ppm}")
        except Exception as e:
            log.error(f"set_ppm Fehler: {e}")

    elif cmd.startswith("airband_gain_step:"):
        # ±1 Stufe Gain (Live), Retune; Save übernimmt Defaults
        try:
            delta = int(cmd.split(":", 1)[1].strip())
            delta = 1 if delta >= 0 else -1
            new = scanner.step_airband_gain(delta, settings, S=S, persist=False)
            dirty = bool((S.get("airband_tune") or {}).get("dirty"))
            mark = " *" if dirty else ""
            ipc.write_progress("Airband Gain", f"{new} dB{mark}", color="green")
            scanner.retune_airband_if_playing(S, settings)
            log.info(f"airband_gain_step → {new} dirty={dirty}")
            import time as _tag
            _tag.sleep(0.6)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"airband_gain_step: {e}")

    elif cmd.startswith("airband_sr_step:"):
        try:
            delta = int(cmd.split(":", 1)[1].strip())
            delta = 1 if delta >= 0 else -1
            new = scanner.step_airband_sample_rate(delta, settings, S=S, persist=False)
            dirty = bool((S.get("airband_tune") or {}).get("dirty"))
            mark = " *" if dirty else ""
            ipc.write_progress("Airband SR", f"{new} Hz{mark}", color="green")
            scanner.retune_airband_if_playing(S, settings)
            log.info(f"airband_sr_step → {new} dirty={dirty}")
            import time as _tas
            _tas.sleep(0.6)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"airband_sr_step: {e}")

    elif cmd.startswith("airband_gain:"):
        # Absolut setzen (Live)
        try:
            val = int(cmd.split(":", 1)[1].strip())
            tune = scanner._ensure_airband_tune(S, settings)
            tune["gain"] = scanner._nearest_step(val, scanner.AIRBAND_GAIN_STEPS)
            def_g = scanner._get_airband_gain(settings, S=None)
            def_sr = scanner._get_airband_sample_rate(settings, S=None)
            tune["dirty"] = (tune["gain"] != def_g) or (int(tune["sample_rate"]) != def_sr)
            ipc.write_progress("Airband Gain", f"{tune['gain']} dB", color="green")
            scanner.retune_airband_if_playing(S, settings)
            import time as _tag2
            _tag2.sleep(0.6)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"airband_gain: {e}")

    elif cmd.startswith("airband_sr:"):
        try:
            val = int(cmd.split(":", 1)[1].strip())
            tune = scanner._ensure_airband_tune(S, settings)
            tune["sample_rate"] = scanner._nearest_step(val, scanner.AIRBAND_SR_STEPS)
            def_g = scanner._get_airband_gain(settings, S=None)
            def_sr = scanner._get_airband_sample_rate(settings, S=None)
            tune["dirty"] = (int(tune["gain"]) != def_g) or (tune["sample_rate"] != def_sr)
            ipc.write_progress("Airband SR", f"{tune['sample_rate']} Hz", color="green")
            scanner.retune_airband_if_playing(S, settings)
            import time as _tas2
            _tas2.sleep(0.6)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"airband_sr: {e}")

    elif cmd == "airband_tune_save":
        try:
            saved = scanner.save_airband_tune_as_defaults(S, settings)
            ipc.write_progress(
                "Airband Default",
                f"Gain {saved['gain']} · SR {saved['sample_rate']}",
                color="green",
            )
            log.info(f"airband_tune_save {saved}")
            import time as _tave
            _tave.sleep(1.0)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"airband_tune_save: {e}")

    else:
        return False
    return True
