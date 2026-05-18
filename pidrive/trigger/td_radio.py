#!/usr/bin/env python3
"""td_radio.py — DAB/FM Suchlauf, Webradio, Sendersteuerung  v0.10.55"""
import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log, ipc
from settings import save_settings
from menu.menu_model import build_tree
from modules import source_state
from modules import (
    musik, wifi, bluetooth, audio, system as sys_mod,
    webradio, dab, fm, library, scanner, update, favorites
)


# ── Scan-Guards (werden von main_core.py per _set_radio_guards() gesetzt) ────
_scan_begin = lambda source: True   # Platzhalter bis main_core Guards setzt
_scan_end   = lambda: None
_scan_info  = lambda: {}


def _set_radio_guards(begin_fn, end_fn, info_fn):
    """Guards von main_core.py empfangen — same pattern wie td_nav._set_nav_guards()"""
    global _scan_begin, _scan_end, _scan_info
    _scan_begin = begin_fn
    _scan_end   = end_fn
    _scan_info  = info_fn


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

    # ── pidrivectl High-Level Play-Trigger ─────────────────────────────────
    elif cmd.startswith("play_dab:"):
        # Format: play_dab:<name_or_service_id>
        _query = cmd.split(":", 1)[1].strip()
        try:
            _sid = _query if _query.startswith("0x") else ""
            try: webradio.stop(S)
            except Exception: pass
            try: fm.stop(S)
            except Exception: pass
            dab.play_by_name(_query, S, settings=settings, service_id=_sid)
            source_state.commit_source("dab")
            log.info(f"CLI play_dab: {_query!r}")
        except Exception as e:
            log.error(f"CLI play_dab Fehler: {e}")

    elif cmd.startswith("play_fm:"):
        _query = cmd.split(":", 1)[1].strip()
        try:
            import json as _fj
            _cfg_dir = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "config")
            _fm_path = os.path.join(_cfg_dir, "fm_stations.json")
            _fm_data = _fj.load(open(_fm_path))
            _fm_all  = _fm_data.get("stations", []) if isinstance(_fm_data, dict) else _fm_data
            _match = next((s for s in _fm_all if
                           _query.lower() in s.get("name","").lower()
                           or _query == str(s.get("freq",""))
                           or _query == str(s.get("freq_mhz",""))), None)
            if not _match and _query.replace(".","").isdigit():
                _match = {"name": f"FM {_query}", "freq_mhz": float(_query)}
            if _match:
                try: webradio.stop(S)
                except Exception: pass
                try: dab.stop(S)
                except Exception: pass
                _freq = str(_match.get("freq") or _match.get("freq_mhz",""))
                fm.play_station({"name": _match["name"], "freq": _freq}, S, settings)
                source_state.commit_source("fm")
                log.info(f"CLI play_fm: {_match['name']} ({_freq} MHz)")
            else:
                log.warn(f"CLI play_fm: Sender nicht gefunden: {_query!r}")
        except Exception as e:
            log.error(f"CLI play_fm Fehler: {e}")

    elif cmd.startswith("play_web:"):
        # Format: play_web:<name_or_id>
        _query = cmd.split(":", 1)[1].strip()
        try:
            _stations = webradio.load_stations()
            _match = next((s for s in _stations if
                           _query.lower() in (s.get("name","")).lower()
                           or _query == str(s.get("id","")))
                          , None)
            if _match:
                try: dab.stop(S)
                except Exception: pass
                try: fm.stop(S)
                except Exception: pass
                webradio.play_station(_match, S, settings)
                source_state.commit_source("webradio")
                log.info(f"CLI play_web: {_match['name']}")
            else:
                log.warn(f"CLI play_web: Sender nicht gefunden: {_query!r}")
        except Exception as e:
            log.error(f"CLI play_web Fehler: {e}")

    elif cmd.startswith("favorites_play:"):
        # Format: favorites_play:<index_or_name>
        _query = cmd.split(":", 1)[1].strip()
        try:
            from modules import favorites as _fav
            _favs = _fav.load_favorites()
            if _query.isdigit():
                _item = _favs[int(_query) - 1] if 0 < int(_query) <= len(_favs) else None
            else:
                _item = next((f for f in _favs if _query.lower() in f.get("name","").lower()), None)
            if _item:
                _src = _item.get("source","")
                if _src == "dab":
                    dab.play_by_name(_item["name"], S, settings=settings)
                    source_state.commit_source("dab")
                elif _src == "fm":
                    fm.play_station({"name": _item["name"], "freq": _item.get("freq","")}, S, settings)
                    source_state.commit_source("fm")
                elif _src in ("webradio","web"):
                    _stations = webradio.load_stations()
                    _st = next((s for s in _stations if s.get("name") == _item["name"]), None)
                    if _st:
                        webradio.play_station(_st, S, settings)
                        source_state.commit_source("webradio")
                log.info(f"CLI favorites_play: {_item['name']}")
            else:
                log.warn(f"CLI favorites_play: Favorit nicht gefunden: {_query!r}")
        except Exception as e:
            log.error(f"CLI favorites_play Fehler: {e}")


    elif cmd == "web_next":
        # Nächster Webradio-Sender (zyklisch durch stations.json)
        try:
            import json as _wj
            _cfg = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "config", "stations.json")
            _st_data = _wj.load(open(_cfg))
            _sts = _st_data.get("stations", _st_data) if isinstance(_st_data, dict) else _st_data
            _sts = [s for s in _sts if s.get("enabled", True)]
            _cur = S.get("radio_name", "") or S.get("radio_station", "")
            _idx = next((i for i, s in enumerate(_sts)
                         if s.get("name","") == _cur), -1)
            _next = _sts[(_idx + 1) % len(_sts)] if _sts else None
            if _next:
                webradio.play_station(_next, S, settings)
                source_state.commit_source("webradio")
                log.info(f"web_next → {_next['name']}")
        except Exception as e:
            log.error(f"web_next Fehler: {e}")

    elif cmd == "web_prev":
        # Vorheriger Webradio-Sender (zyklisch)
        try:
            import json as _wj
            _cfg = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "config", "stations.json")
            _st_data = _wj.load(open(_cfg))
            _sts = _st_data.get("stations", _st_data) if isinstance(_st_data, dict) else _st_data
            _sts = [s for s in _sts if s.get("enabled", True)]
            _cur = S.get("radio_name", "") or S.get("radio_station", "")
            _idx = next((i for i, s in enumerate(_sts)
                         if s.get("name","") == _cur), 0)
            _prev = _sts[(_idx - 1) % len(_sts)] if _sts else None
            if _prev:
                webradio.play_station(_prev, S, settings)
                source_state.commit_source("webradio")
                log.info(f"web_prev → {_prev['name']}")
        except Exception as e:
            log.error(f"web_prev Fehler: {e}")

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
