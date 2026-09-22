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
    wifi, bluetooth, audio, system as sys_mod,
    webradio, update, favorites
)
from modules.radio import dab, fm, scanner


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


def _clear_meta(S):
    """Metadaten vor Quellwechsel löschen — verhindert Stale-Titel."""
    for _k in ("radio_name", "radio_type", "radio_station", "track", "artist",
               "album", "dls_text", "metadata_unavailable", "source_error"):
        if _k in ("radio_name", "radio_type", "radio_station"):
            S[_k] = ""
        else:
            S.pop(_k, None)


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
                    menu_state.rebuild(build_tree(store, S, settings))
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

    elif cmd == "dab_scan_replace":
        def _dab_scan_replace():
            if not _scan_begin("dab"):
                info = _scan_info()
                log.warn("SCAN_BLOCKED source=dab replace running=" + info.get("source", "?"))
                ipc.write_progress("DAB+ Suchlauf",
                    "Schon aktiv: " + info.get("source", "?").upper(), color="orange")
                _time_mod.sleep(2)
                ipc.clear_progress()
                return

            ipc.write_progress("DAB+ Suchlauf", "Ersetze Liste …", color="blue")
            log.info("SCAN_START source=dab mode=replace")

            try:
                results = dab.scan_dab_channels(settings=settings)
                count = len(results)
                store.replace_dab(results)
                log.info(f"SCAN_DONE source=dab mode=replace count={count}")
                if count > 0:
                    ipc.write_progress("DAB+ Suchlauf",
                        f"{count} Sender — Liste ersetzt", color="green")
                else:
                    ipc.write_progress("DAB+ Suchlauf",
                        "0 Sender — Liste geleert", color="orange")
                _time_mod.sleep(2)
                menu_state.rebuild(build_tree(store, S, settings))
            except Exception as e:
                log.error(f"SCAN_FAIL source=dab replace error={e}")
                ipc.write_progress("DAB+ Fehler", str(e)[:48], color="red")
                source_state.commit_source("idle")
                _time_mod.sleep(3)
            finally:
                if not S.get("radio_playing"):
                    S["control_context"] = "idle"
                source_state.end_transition()
                _scan_end()
                ipc.clear_progress()
        bg(_dab_scan_replace)

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
                        menu_state.rebuild(build_tree(store, S, settings))
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
                    menu_state.rebuild(build_tree(store, S, settings))
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
                    if not source_state.begin_transition("webui", "webradio"):
                        ipc.write_progress("Webradio", "Blockiert", color="orange")
                        import time as _t
                        _t.sleep(2)
                        ipc.clear_progress()
                        return
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
        _query = cmd.split(":", 1)[1].strip()
        _gen = source_state.bump_play_gen("play_dab")

        def _run_cli_dab():
            _sid = _query if _query.startswith("0x") else ""
            try:
                if not source_state.is_play_gen(_gen):
                    log.info(f"CLI play_dab: superseded before start {_query!r}")
                    return
                _clear_meta(S)
                try: webradio.stop(S)
                except Exception: pass
                try: fm.stop(S)
                except Exception: pass
                if not source_state.is_play_gen(_gen):
                    return
                # Früher Commit: play_by_name blockiert bis zu dab_wait_lock (90s).
                # Sonst bleibt die WebUI auf der alten Quelle (z.B. FM) stehen.
                if source_state.begin_transition("webui:play_dab", "dab"):
                    try:
                        if not source_state.is_play_gen(_gen):
                            return
                        S["radio_type"] = "DAB+"
                        S["radio_name"] = _query
                        S["radio_station"] = f"DAB: {_query}"
                        S["radio_playing"] = False
                        S["control_context"] = "radio_dab"
                        source_state.commit_source("dab")
                    finally:
                        source_state.end_transition()
                if not source_state.is_play_gen(_gen):
                    log.info(f"CLI play_dab: superseded after commit {_query!r}")
                    return
                _dab_ok = dab.play_by_name(_query, S, settings=settings, service_id=_sid)
                if not source_state.is_play_gen(_gen):
                    log.info(f"CLI play_dab: superseded after play {_query!r}")
                    return
                if _dab_ok is not None:
                    # erneut committen falls play_station Zwischenzustände gesetzt hat
                    source_state.commit_source("dab")
                    if _dab_ok:
                        log.info(f"CLI play_dab: {_query!r} lock ok")
                    else:
                        log.info(
                            f"CLI play_dab: {_query!r} no_lock/partial — "
                            f"welle-cli läuft weiter state={S.get('dab_playback_state','?')}"
                        )
                else:
                    log.warn(f"CLI play_dab: Exception — kein commit {_query!r}")
            except Exception as e:
                import traceback as _tb
                log.error(f"CLI play_dab Fehler: {type(e).__name__}: {e}")
                log.error(f"CLI play_dab Traceback:\n{_tb.format_exc()}")

        bg(_run_cli_dab)

    elif cmd.startswith("play_fm:"):
        _query = cmd.split(":", 1)[1].strip()
        _gen = source_state.bump_play_gen("play_fm")

        def _run_cli_fm():
            try:
                if not source_state.is_play_gen(_gen):
                    log.info(f"CLI play_fm: superseded before start {_query!r}")
                    return
                import json as _fj
                _cfg_dir = os.path.join(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))), "config")
                _fm_path = os.path.join(_cfg_dir, "fm_stations.json")
                _fm_data = _fj.load(open(_fm_path))
                _fm_all  = _fm_data.get("stations", []) if isinstance(_fm_data, dict) else _fm_data
                _match = None
                if _query:
                    # 1) Frequenz exakt (Float-tolerant) — verhindert "90" ∈ "Radio 90.2"-Falschtreffer
                    try:
                        _qf = float(_query.replace(",", "."))
                    except ValueError:
                        _qf = None
                    if _qf is not None:
                        for s in _fm_all:
                            for key in ("freq_mhz", "freq"):
                                try:
                                    if abs(float(s.get(key)) - _qf) < 0.05:
                                        _match = s
                                        break
                                except (TypeError, ValueError):
                                    pass
                            if _match:
                                break
                    # 2) Name exakt, dann Teilstring
                    if not _match:
                        _ql = _query.lower()
                        _match = next((s for s in _fm_all if s.get("name", "").lower() == _ql), None)
                    if not _match and len(_query) >= 3:
                        _ql = _query.lower()
                        _match = next(
                            (s for s in _fm_all if _ql in s.get("name", "").lower()),
                            None,
                        )
                if not _match and _query:
                    _q2 = _query.replace(",", ".")
                    try:
                        _freq_f = float(_q2)
                        if 76.0 <= _freq_f <= 108.0:
                            _match = {"name": f"FM {_freq_f:g}", "freq_mhz": _freq_f}
                    except ValueError:
                        pass
                if not _match:
                    log.warn(f"CLI play_fm: Sender nicht gefunden: {_query!r}")
                    return

                if not source_state.is_play_gen(_gen):
                    return
                _clear_meta(S)
                # DAB zuerst hart stoppen — freigibt Stick auch aus Lock-Wait
                try: webradio.stop(S)
                except Exception: pass
                try: dab.stop(S)
                except Exception: pass

                if not source_state.is_play_gen(_gen):
                    log.info(f"CLI play_fm: superseded after stop {_query!r}")
                    return

                if source_state.begin_transition("webui:play_fm", "fm"):
                    try:
                        if not source_state.is_play_gen(_gen):
                            return
                        S["radio_type"] = "FM"
                        S["radio_name"] = _match.get("name") or _query
                        _fx = str(_match.get("freq") or _match.get("freq_mhz") or _query)
                        S["radio_station"] = f"FM: {S['radio_name']} ({_fx} MHz)"
                        S["radio_playing"] = False
                        S["control_context"] = "radio_fm"
                        source_state.commit_source("fm")
                    finally:
                        source_state.end_transition()

                if not source_state.is_play_gen(_gen):
                    return
                _freq = str(_match.get("freq") or _match.get("freq_mhz", ""))
                _fm_ok = fm.play_station(
                    {"name": _match["name"], "freq": _freq}, S, settings
                )
                if not source_state.is_play_gen(_gen):
                    log.info(f"CLI play_fm: superseded after play {_query!r}")
                    return
                if _fm_ok is not False:
                    source_state.commit_source("fm")
                    try:
                        from mpv_meta import write_source_history as _wsh
                        _wsh(
                            "fm",
                            _match.get("name") or S.get("radio_name") or _freq or "FM",
                            _freq or "",
                        )
                    except Exception:
                        pass
                    log.info(f"CLI play_fm: {_match['name']} ({_freq} MHz)")
                else:
                    log.warn(
                        f"CLI play_fm: Fehler beim Starten — {S.get('source_error', '?')}"
                    )
                    import modules.source_state as _sst_fm
                    _sst_fm.commit_source("idle", auto_end=True)
            except Exception as e:
                log.error(f"CLI play_fm Fehler: {e}")

        bg(_run_cli_fm)

    elif cmd.startswith("play_web:"):
        # Format: play_web:<name_or_id>
        _query = cmd.split(":", 1)[1].strip()
        _gen = source_state.bump_play_gen("play_web")

        def _run_cli_web():
            try:
                if not source_state.is_play_gen(_gen):
                    return
                _stations = webradio.load_stations()
                _match = next((s for s in _stations if
                               _query.lower() in (s.get("name","")).lower()
                               or _query == str(s.get("id","")))
                              , None)
                if not _match:
                    log.warn(f"CLI play_web: Sender nicht gefunden: {_query!r}")
                    return
                try: dab.stop(S)
                except Exception: pass
                try: fm.stop(S)
                except Exception: pass
                if not source_state.is_play_gen(_gen):
                    return
                if source_state.begin_transition("webui:play_web", "webradio"):
                    try:
                        if not source_state.is_play_gen(_gen):
                            return
                        S["radio_type"] = "WEB"
                        S["radio_name"] = _match.get("name") or _query
                        S["radio_station"] = f"WEB: {S['radio_name']}"
                        S["radio_playing"] = False
                        S["control_context"] = "radio_web"
                        source_state.commit_source("webradio")
                    finally:
                        source_state.end_transition()
                if not source_state.is_play_gen(_gen):
                    return
                webradio.play_station(_match, S, settings)
                if not source_state.is_play_gen(_gen):
                    return
                source_state.commit_source("webradio")
                try:
                    from mpv_meta import write_source_history as _wsh2
                    _wsh2("webradio", _match.get("name") or S.get("radio_name") or "", "")
                except Exception: pass
                log.info(f"CLI play_web: {_match['name']}")
            except Exception as e:
                log.error(f"CLI play_web Fehler: {e}")

        bg(_run_cli_web)

    elif cmd.startswith("favorites_play:"):
        # Format: favorites_play:<index_or_name>
        _query = cmd.split(":", 1)[1].strip()
        try:
            from modules import favorites as _fav
            _favs = _fav.get_all()
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

    elif cmd.startswith("local_play:"):
        # Lokale Datei/Ordner/M3U Playlist spielen
        payload = cmd.split(":", 1)[1]
        shuffle = False
        if payload.endswith("|shuffle"):
            shuffle = True
            payload = payload[:-8]
        _clear_meta(S)
        try:
            for _stop_fn in (webradio.stop, dab.stop, fm.stop, scanner.stop):
                try:
                    _stop_fn(S)
                except Exception:
                    pass
            from modules import local_player as _lp
            if not _lp.play(payload, S, settings, shuffle=shuffle):
                log.warn(f"local_play: keine Dateien in {payload!r}")
                return
            source_state.commit_source("local")
            try:
                import os as _oslh
                from mpv_meta import write_source_history as _wsh3
                _wsh3("local", S.get("track") or _oslh.path.basename(payload.rstrip("/")) or "Lokal", payload)
            except Exception:
                pass
            log.info(f"local_play: {payload!r} shuffle={shuffle}")
        except Exception as _e:
            log.error(f"local_play Fehler: {_e}")

    elif cmd == "fm_next":
        bg(lambda: fm.play_next(S, store.fm))
    elif cmd == "fm_prev":
        bg(lambda: fm.play_prev(S, store.fm))
    elif cmd.startswith("fm_step:"):
        try:
            _delta = float(cmd.split(":", 1)[1])
        except Exception:
            log.warn(f"fm_step: ungültig {cmd!r}")
            return True
        bg(lambda d=_delta: fm.step_freq(S, settings, d))

    elif cmd.startswith("fm_hp_step:"):
        try:
            delta = int(cmd.split(":", 1)[1].strip())
            delta = 1 if delta >= 0 else -1
            new = fm.step_fm_hp(delta, settings, S=S)
            dirty = bool((S.get("fm_tune") or {}).get("dirty"))
            mark = " *" if dirty else ""
            ipc.write_progress("FM HP", f"{new} Hz{mark}", color="green")
            fm.retune_fm_if_playing(S, settings)
            try:
                scanner.retune_scanner_fm_if_playing(S, settings)
            except Exception:
                pass
            log.info(f"fm_hp_step → {new} dirty={dirty}")
            import time as _tfh
            _tfh.sleep(0.6)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"fm_hp_step: {e}")

    elif cmd.startswith("fm_lp_step:"):
        try:
            delta = int(cmd.split(":", 1)[1].strip())
            delta = 1 if delta >= 0 else -1
            new = fm.step_fm_lp(delta, settings, S=S)
            dirty = bool((S.get("fm_tune") or {}).get("dirty"))
            mark = " *" if dirty else ""
            ipc.write_progress("FM LP", f"{new} Hz{mark}", color="green")
            fm.retune_fm_if_playing(S, settings)
            try:
                scanner.retune_scanner_fm_if_playing(S, settings)
            except Exception:
                pass
            log.info(f"fm_lp_step → {new} dirty={dirty}")
            import time as _tfl
            _tfl.sleep(0.6)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"fm_lp_step: {e}")

    elif cmd == "fm_tune_save":
        try:
            saved = fm.save_fm_tune_as_defaults(S, settings)
            ipc.write_progress(
                "FM Default",
                f"HP{saved['hp_hz']} LP{saved['lp_hz']}",
                color="green",
            )
            log.info(f"fm_tune_save {saved}")
            import time as _tfs
            _tfs.sleep(1.0)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"fm_tune_save: {e}")

    # ── DAB Next/Prev ───────────────────────────────────────────────────────
    elif cmd == "dab_next":
        bg(lambda: dab.play_next(S, store.dab))
    elif cmd == "dab_prev":
        bg(lambda: dab.play_prev(S, store.dab))

    else:
        return False
    return True
