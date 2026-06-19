#!/usr/bin/env python3
"""td_system.py — Bibliothek und System-Kommandos  v0.10.55"""
import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log, ipc
from settings import save_settings, load_settings
from modules import source_state
from modules import (
    wifi, bluetooth, audio, system as sys_mod,
    webradio, dab, fm, scanner, update, favorites
)


def handle(cmd, menu_state, store, S, settings, bg):
    """System-Trigger: radio_stop, Bibliothek, Reboot, Update, Favoriten."""
    # ── Bibliothek ─────────────────────────────────────────────────────────
    if cmd == "lib_browse":
        # v0.10.55: source_state tracking + begin_transition
        def _lib_browse():
            if source_state.begin_transition("lib_browse", "library"):
                try:
                    library.browse_and_play(S, load_settings())
                    if S.get("library_playing"):
                        source_state.commit_source("library")
                finally:
                    source_state.end_transition()
        bg(_lib_browse)

    elif cmd.startswith("fav_toggle:"):
        payload = cmd[len("fav_toggle:"):]
        try:
            import json as _j2
            parts = payload.split(":", 3)
            _src  = parts[0]
            _id   = parts[1]
            _name = parts[2]
            _meta = _j2.loads(parts[3]) if len(parts) > 3 else {}
            is_now_fav = favorites.toggle({
                "id": _id,
                "name": _name,
                "source": _src,
                "meta": _meta
            })
            if _src == "fm":
                store.set_favorite_fm(_id, is_now_fav)
            elif _src == "dab":
                store.set_favorite_dab(_id, is_now_fav)
            elif _src == "webradio":
                store.set_favorite_web(_id, is_now_fav)
            # Lazy import to avoid circular dependency
            try:
                import main_core as _mc
                _mc.rebuild_tree(menu_state, store, S, settings)
            except Exception as _rte:
                log.warn(f"rebuild_tree: {_rte}")
        except Exception as _fe:
            log.warn("fav_toggle: " + str(_fe))

    # ── Aktuelle Wiedergabe als Favorit merken ───────────────────────────────
    elif cmd == "favorites_add_current":
        try:
            rtype = (S.get("radio_type", "") or "").upper()
            src_map = {"FM": "fm", "DAB": "dab", "WEB": "webradio",
                       "SPOTIFY": "spotify", "SCANNER": "scanner"}
            src  = src_map.get(rtype, "")
            name = S.get("radio_name") or S.get("radio_station") or ""
            if not src or not name:
                ipc.write_progress("Favorit", "Nichts Aktives zum Merken", color="orange")
                time.sleep(1); ipc.clear_progress()
            else:
                if src == "fm":
                    meta = settings.get("last_fm_station") or {"name": name}
                elif src == "dab":
                    meta = settings.get("last_dab_station") or {"name": name}
                elif src == "webradio":
                    meta = settings.get("last_web_station") or {"name": name}
                else:
                    meta = {"name": name}
                if not isinstance(meta, dict):
                    meta = {"name": name}
                _fid = f"{src}_{str(name).lower().replace(' ', '_')[:24]}"
                favorites.add({"id": _fid, "name": name, "source": src, "meta": meta})
                try:
                    import main_core as _mc
                    _mc.rebuild_tree(menu_state, store, S, settings)
                except Exception as _rte:
                    log.warn(f"rebuild_tree: {_rte}")
        except Exception as _fe:
            log.warn("favorites_add_current: " + str(_fe))

    # ── System ──────────────────────────────────────────────────────────────
    elif cmd == "reboot":
        ipc.write_progress("Neustart", "In 3 Sekunden ...", color="orange")
        time.sleep(3)
        os.system("reboot")
    elif cmd == "shutdown":
        ipc.write_progress("Ausschalten", "In 3 Sekunden ...", color="orange")
        time.sleep(3)
        os.system("poweroff")
    elif cmd == "sys_info":
        bg(lambda: sys_mod.show_info(S, settings))
    elif cmd == "sys_version":
        bg(lambda: sys_mod.show_version(S))
    elif cmd == "update":
        bg(lambda: update.run_update(S))
    elif cmd == "audio_select":
        menu_state.navigate_to("audio_out")

    else:
        return False   # Trigger nicht von td_system behandelt
    return True
