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
    webradio, dab, fm, scanner, update, favorites
)
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


def handle(cmd, menu_state, store, S, settings, bg):
    # ── Scanner ─────────────────────────────────────────────────────────────
    if cmd == "scanner_stop":
        scanner.stop(S)
        source_state.commit_source("idle")
        S["radio_playing"] = False
        S["radio_station"] = ""
        S["radio_name"] = ""
        S["radio_type"] = ""
        S["control_context"] = "idle"
        log.info("Scanner via scanner_stop beendet")

    elif cmd.startswith("scan_up:"):
        band = cmd.split(":", 1)[1]
        # Stale Metadaten aus vorheriger Quelle löschen
        for _sk in ("radio_name", "radio_type", "track", "artist", "source_error"):
            if _sk in ("radio_name", "radio_type"): S[_sk] = ""
            else: S.pop(_sk, None)
        def _scan_up(b=band):
            _stop_other_sources(S)
            source_state.begin_transition(f"scan_up:{b}", "scanner")
            try:
                scanner.channel_up(b, S)
                S["scanner_band"] = b if "b" in dir() else band
                source_state.commit_source("scanner")
            finally:
                source_state.end_transition()
        bg(_scan_up)

    elif cmd.startswith("scan_down:"):
        band = cmd.split(":", 1)[1]
        def _scan_down(b=band):
            _stop_other_sources(S)
            source_state.begin_transition(f"scan_down:{b}", "scanner")
            try:
                scanner.channel_down(b, S)
                S["scanner_band"] = b if "b" in dir() else band
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
            if source_state.begin_transition(f"scan_next:{b}", "scanner"):
                try:
                    scanner.scan_next(b, S, settings)
                    S["scanner_band"] = b if "b" in dir() else band
                    source_state.commit_source("scanner")
                finally:
                    source_state.end_transition()
        bg(_scan_next)

    elif cmd.startswith("scan_prev:"):
        band = cmd.split(":", 1)[1]
        def _scan_prev(b=band):
            _stop_other_sources(S)
            if source_state.begin_transition(f"scan_prev:{b}", "scanner"):
                try:
                    scanner.scan_prev(b, S, settings)
                    S["scanner_band"] = b if "b" in dir() else band
                    source_state.commit_source("scanner")
                finally:
                    source_state.end_transition()
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
                # v0.10.55: settings durchreichen + begin_transition wrapper
                def _scan_jump_fn(b=band, d=delta):
                    _stop_other_sources(S)
                    if source_state.begin_transition(f"scan_jump:{b}", "scanner"):
                        try:
                            scanner.channel_jump(b, d, S, settings)
                            S["scanner_band"] = b if "b" in dir() else band
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
                # v0.10.55: begin_transition wrapper
                def _scan_step_fn(b=band, d=delta):
                    _stop_other_sources(S)
                    if source_state.begin_transition(f"scan_step:{b}", "scanner"):
                        try:
                            scanner.freq_step(b, d, S, settings)
                            S["scanner_band"] = b if "b" in dir() else band
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
                # v0.10.55: begin_transition wrapper
                def _scan_setfreq_fn(b=band, f=freq):
                    _stop_other_sources(S)
                    _clear_scanner_metadata(S)
                    if source_state.begin_transition(f"scan_setfreq:{b}", "scanner"):
                        try:
                            scanner.set_freq(b, f, S, settings)
                            S["scanner_band"] = b if "b" in dir() else band
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
                if source_state.begin_transition(f"scan_setch:{b}", "scanner"):
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
            # v0.10.55: begin_transition wrapper
            def _input_and_set(b=band):
                freq = scanner.freq_input_screen(b, settings)
                if freq is not None:
                    _stop_other_sources(S)
                    if source_state.begin_transition(f"scan_inputfreq:{b}", "scanner"):
                        try:
                            scanner.set_freq(b, freq, S, settings)
                            S["scanner_band"] = b if "b" in dir() else band
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

    else:
        return False
    return True
