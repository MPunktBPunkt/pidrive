#!/usr/bin/env python3
"""td_radio.py — DAB/FM Suchlauf, Webradio, Sendersteuerung  v0.10.49"""
import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log, ipc
from settings import save_settings
from menu_model import build_tree
from modules import source_state
from modules import (
    musik, wifi, bluetooth, audio, system as sys_mod,
    webradio, dab, fm, library, scanner, update, favorites
)


def handle(cmd, menu_state, store, S, settings, bg):
    # ── DAB Suchlauf ───────────────────────────────────────────────────────
    if cmd == "dab_scan":
        def _dab_scan():
            if not _scan_begin("dab"):
                info = _scan_info()
                log.warn("SCAN_BLOCKED source=dab running=" + info.get("source","?"))
                ipc.write_progress("DAB+ Suchlauf",
                    "Schon aktiv: " + info.get("source","?").upper(), color="orange")
                _time_mod.sleep(2)
                ipc.clear_progress()
                return

            ipc.write_progress("DAB+ Suchlauf", "Scanne Band III ...", color="blue")
            log.info("SCAN_START source=dab")

            try:
                results = dab.scan_dab_channels(settings=settings)
                count = len(results)
                if count > 0:
                    store.save_dab(results)
                    log.info(f"SCAN_DONE source=dab count={count}")
                    ipc.write_progress("DAB+ Suchlauf", f"{count} Sender gefunden", color="green")
                    _time_mod.sleep(2)
                    new_root = build_tree(store, S, settings)
                    menu_state.root = new_root
                    menu_state.clamp_cursors()
                    menu_state.rev += 1
                else:
                    log.warn("SCAN_DONE source=dab count=0 — bestehende Liste bleibt")
                    ipc.write_progress("DAB+ Suchlauf", "0 Sender — Liste bleibt erhalten", color="orange")
                    _time_mod.sleep(2)
            except Exception as e:
                log.error(f"SCAN_FAIL source=dab error={e}")
                ipc.write_progress("DAB+ Fehler", str(e)[:48], color="red")
                source_state.commit_source("idle")
                _time_mod.sleep(3)
            finally:
                if not S.get("radio_playing"):
                    S["control_context"] = "idle"
                source_state.end_transition()
                _scan_end()
                ipc.clear_progress()
        bg(_dab_scan)

    elif cmd.startswith("dab_scan_channels:"):
        parts = cmd.split(":", 1)
        if len(parts) == 2:
            raw = parts[1].strip()
            chans = [x.strip().upper() for x in raw.split(",") if x.strip()]

            def _dab_custom(channels=chans):
                owner = f"scan:dab:custom:{','.join(channels)}"
                if not _scan_begin("dab"):
                    ipc.write_progress("DAB+ Suchlauf", "Schon aktiv", color="orange")
                    _time_mod.sleep(2)
                    ipc.clear_progress()
                    return

                if not source_state.begin_transition(owner, "dab"):
                    ipc.write_progress("DAB+ Suchlauf", "Blockiert", color="orange")
                    _time_mod.sleep(2)
                    ipc.clear_progress()
                    _scan_end()
                    return

                try:
                    S["control_context"] = "radio_dab_scan"
                    log.info("SCAN_START source=dab custom=" + ",".join(channels))
                    scan_settings = dict(settings)
                    scan_settings["dab_scan_channels"] = channels
                    results = dab.scan_dab_channels(settings=scan_settings)
                    count = len(results)
                    if count > 0:
                        store.save_dab(results)
                        source_state.commit_source("dab")
                        ipc.write_progress("DAB+ Suchlauf", f"{count} Sender gefunden", color="green")
                        new_root = build_tree(store, S, settings)
                        menu_state.root = new_root
                        menu_state.clamp_cursors()
                        menu_state.rev += 1
                    else:
                        source_state.commit_source("idle")
                        ipc.write_progress("DAB+ Suchlauf", "0 Sender — Liste bleibt", color="orange")
                    _time_mod.sleep(2)
                except Exception as e:
                    log.error(f"SCAN_FAIL dab custom: {e}")
                    source_state.commit_source("idle")
                    _time_mod.sleep(3)
                finally:
                    if not S.get("radio_playing"):
                        S["control_context"] = "idle"
                    source_state.end_transition()
                    _scan_end()
                    ipc.clear_progress()

            bg(_dab_custom)

    # ── FM Suchlauf ────────────────────────────────────────────────────────
    elif cmd == "fm_scan":
        def _fm_scan():
            if not _scan_begin("fm"):
                info = _scan_info()
                log.warn("SCAN_BLOCKED source=fm running=" + info.get("source","?"))
                ipc.write_progress("FM Suchlauf",
                    "Schon aktiv: " + info.get("source","?").upper(), color="orange")
                _time_mod.sleep(2)
                ipc.clear_progress()
                return

            ipc.write_progress("FM Suchlauf", "Scanne UKW 87.5–108.0 MHz ...", color="blue")
            log.info("SCAN_START source=fm")

            try:
                results = fm.scan_stations(S, quick_only=True)
                count = len(results)
                if count > 0:
                    store.save_fm(results)
                    log.info(f"SCAN_DONE source=fm count={count}")
                    ipc.write_progress("FM Suchlauf", f"{count} Sender gefunden ✓", color="green")
                else:
                    log.warn("SCAN_DONE source=fm count=0 — bestehende Liste bleibt")
                    ipc.write_progress("FM Suchlauf", "Kein Sender — Liste bleibt erhalten", color="orange")
                _time_mod.sleep(2)

                if count > 0:
                    new_root = build_tree(store, S, settings)
                    menu_state.root = new_root
                    menu_state.clamp_cursors()
                    menu_state.rev += 1
            except Exception as e:
                log.error(f"SCAN_FAIL source=fm error={e}")
                ipc.write_progress("FM Fehler", str(e)[:48], color="red")
                _time_mod.sleep(3)
            finally:
                _scan_end()
                ipc.clear_progress()

        bg(_fm_scan)

    # ── Reload Stationen ───────────────────────────────────────────────────
    elif cmd.startswith("reload_stations:"):
        _si = _scan_info()
        if _si.get("active"):
            log.warn("STATIONS_RELOAD_BLOCKED scan_running=" + _si.get("source","?"))
            ipc.write_progress(
                "Senderliste",
                "Blockiert: Scan läuft (" + _si.get("source","?").upper() + ")",
                color="orange"
            )
            _time_mod.sleep(2)
            ipc.clear_progress()
        else:
            source = cmd.split(":", 1)[1]
            store.reload_source(source)
            rebuild = True
            log.info(f"STATIONS_RELOAD source={source}")
            ipc.write_progress("Senderliste", f"{source} neu geladen", color="green")
            _time_mod.sleep(1)
            ipc.clear_progress()

    # ── Webradio Play direkt (WebUI) ────────────────────────────────────────
    elif cmd.startswith("webradio_play:"):
        # Format: webradio_play:<station_id>
        # station_id entspricht dem id-Feld in config/stations.json
        _station_id = cmd.split(":", 1)[1].strip()
        try:
            _stations = webradio.load_stations()
            _match = next((s for s in _stations if s.get("id") == _station_id), None)
            if _match and _match.get("enabled", True):
                def _do_webradio_play(m=_match):
                    source_state.begin_transition("webui", "webradio")
                    try:
                        # Alle laufenden Quellen stoppen (kein _stop_all_sources hier im Scope)
                        for _stopper in (dab.stop, fm.stop, scanner.stop):
                            try: _stopper(S)
                            except Exception: pass
                        S["radio_playing"] = False
                        S["radio_type"] = ""
                        webradio.play_station(m, S, settings)
                        source_state.commit_source("webradio")
                    except Exception as _e:
                        log.error(f"WEBRADIO_PLAY inner: {_e}")
                    finally:
                        source_state.end_transition()
                    log.action("WEBRADIO_PLAY", f"id={_station_id} name={m.get('name','?')}")
                bg(_do_webradio_play)
            else:
                log.warn(f"WEBRADIO_PLAY: Station nicht gefunden oder deaktiviert id={_station_id!r}")
        except Exception as e:
            log.error(f"WEBRADIO_PLAY: {e}")
            try: source_state.end_transition()
            except Exception: pass

    # ── FM Next/Prev ────────────────────────────────────────────────────────
    elif cmd == "fm_next":
        bg(lambda: fm.play_next(S, store.fm))
    elif cmd == "fm_prev":
        bg(lambda: fm.play_prev(S, store.fm))
    elif cmd == "fm_manual":
        bg(lambda: _fm_manual(S, settings))

    # ── DAB Next/Prev ───────────────────────────────────────────────────────
    elif cmd == "dab_next":
        bg(lambda: dab.play_next(S, store.dab))
    elif cmd == "dab_prev":
        bg(lambda: dab.play_prev(S, store.dab))

    else:
        return False
    return True
