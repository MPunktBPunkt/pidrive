#!/usr/bin/env python3
"""td_nav.py — Navigation und Menü-Aktionen  v0.10.40"""
import os, sys, time as _time_mod, threading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import log, ipc
from settings import save_settings
from modules import source_state
from modules import (
    musik, wifi, bluetooth, audio, system as sys_mod,
    webradio, dab, fm, library, scanner, update, favorites
)


def handle(cmd, menu_state, store, S, settings, bg):
    """Navigation: up/down/left/right/enter/back/cat/enter-action."""
    # ── Navigation ────────────────────────────────────────────────────────
    if   cmd == "up":
        menu_state.key_up()
    elif cmd == "down":
        menu_state.key_down()
    elif cmd == "left":
        menu_state.key_left()
    elif cmd == "back":
        # v0.9.21: BT-Geräteliste verlassen → Scan stoppen
        _leaving_node = menu_state.selected_folder
        menu_state.key_back()
        if _leaving_node and getattr(_leaving_node, "id", "") == "bt_geraete":
            log.info("MENU bt_geraete: Auto-Scan gestoppt (back)")
            bg(lambda: bluetooth.stop_scan())
    elif cmd == "enter":
        node = menu_state.key_enter()
        if node and node.type in ("station", "action", "toggle"):
            _execute_node(node, menu_state, store, S, settings)
        # v0.9.21: BT-Geräteliste betreten → Scan automatisch starten
        if node and node.type == "folder" and node.id == "bt_geraete":
            log.info("MENU bt_geraete: Auto-Scan gestartet")
            def _bt_geraete_enter():
                # v0.9.29: BT einschalten wenn nötig
                if not S.get("bt_on", False) and not S.get("bt", False):
                    log.info("MENU bt_geraete: BT war aus — schalte ein")
                    import subprocess
                    subprocess.run(
                        "rfkill unblock bluetooth; hciconfig hci0 up; bluetoothctl power on",
                        shell=True, capture_output=True, timeout=6
                    )
                    S["bt_on"] = True
                    S["bt_status"] = "getrennt"
                    S["menu_rev"] = S.get("menu_rev", 0) + 1
                    import time; time.sleep(1)
                bluetooth.scan_devices(S, settings)
            bg(_bt_geraete_enter)
    elif cmd == "right":
        node = menu_state.key_right()
        if node and node.type in ("station", "action", "toggle"):
            _execute_node(node, menu_state, store, S, settings)
        if node and node.type == "folder" and node.id == "bt_geraete":
            log.info("MENU bt_geraete: Auto-Scan gestartet (right)")
            def _bt_geraete_right():
                if not S.get("bt_on", False) and not S.get("bt", False):
                    log.info("MENU bt_geraete (right): BT war aus — schalte ein")
                    import subprocess
                    subprocess.run(
                        "rfkill unblock bluetooth; hciconfig hci0 up; bluetoothctl power on",
                        shell=True, capture_output=True, timeout=6
                    )
                    S["bt_on"] = True
                    S["bt_status"] = "getrennt"
                    S["menu_rev"] = S.get("menu_rev", 0) + 1
                    import time; time.sleep(1)
                bluetooth.scan_devices(S, settings)
            bg(_bt_geraete_right)

    # ── Direkt-Kategorie ──────────────────────────────────────────────────
    elif cmd.startswith("cat:"):
        val = cmd[4:]
        menu_state.navigate_to(val)

    else:
        return False
    return True



# ── Source-Switch Guards (gesetzt von main_core._init_dispatcher) ────────────
_source_switch_begin = None
_source_switch_end   = None
_source_switch_info  = None

def _set_nav_guards(begin_fn, end_fn, info_fn):
    global _source_switch_begin, _source_switch_end, _source_switch_info
    _source_switch_begin = begin_fn
    _source_switch_end   = end_fn
    _source_switch_info  = info_fn


# Entpreller-State für _execute_node (lokal in td_nav)
_LAST_NODE_EXEC_TS = 0.0
_LAST_NODE_EXEC_ID = ""


def _execute_node(node, menu_state, store, S, settings):
    global _LAST_NODE_EXEC_TS, _LAST_NODE_EXEC_ID
    import threading

    now = _time_mod.time()
    node_exec_id = f"{node.type}:{node.id}:{node.action}:{node.source}"
    if node_exec_id == _LAST_NODE_EXEC_ID and (now - _LAST_NODE_EXEC_TS) < 0.5:
        log.info(f"MENU_ACTION entprellt id={node.id} type={node.type}")
        return
    _LAST_NODE_EXEC_ID = node_exec_id
    _LAST_NODE_EXEC_TS = now

    def bg(fn):
        threading.Thread(target=fn, daemon=True).start()

    def _stop_all_sources():
        try:
            webradio.stop(S)
        except Exception as e:
            log.warn(f"stop_all_sources: webradio.stop: {e}")
        try:
            dab.stop(S)
        except Exception as e:
            log.warn(f"stop_all_sources: dab.stop: {e}")
        try:
            fm.stop(S)
        except Exception as e:
            log.warn(f"stop_all_sources: fm.stop: {e}")
        try:
            scanner.stop(S)
        except Exception as e:
            log.warn(f"stop_all_sources: scanner.stop: {e}")

        S["radio_playing"] = False
        S["radio_station"] = ""
        S["radio_name"] = ""
        S["radio_type"] = ""
        S["control_context"] = "idle"
        source_state.commit_source("idle")
        _time_mod.sleep(0.10)

    if node.type == "station":
        log.info(f"PLAY_STATION label={node.label!r} source={node.source} meta={node.meta}")

        def _run_station_switch():
            owner = f"station:{node.source}:{node.id}"
            if not _source_switch_begin(owner=owner, blocking=False):
                info = _source_switch_info()
                log.warn(f"PLAY_STATION blocked by active switch owner={info.get('owner','?')}")
                return

            source_state.begin_transition(owner, node.source or "unknown")
            try:
                _stop_all_sources()
                src = node.source
                meta = node.meta

                if src == "fm":
                    _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                                     if "  " in node.label else node.label.lstrip("★ ").strip())
                    _freq = meta.get("freq", "")
                    _ok = fm.play_station({"name": _name, "freq": _freq}, S, settings)
                    if _ok is not False:  # None (alte API) oder True = Erfolg
                        source_state.commit_source("fm")
                    else:
                        log.warn(f"FM play_station scheiterte — kein commit_source fm name={_name!r}")

                elif src == "dab":
                    _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                                     if "  " in node.label else node.label.lstrip("★ ").strip())
                    _sid = meta.get("service_id", "")
                    dab.play_by_name(_name, S, settings=settings, service_id=_sid)
                    source_state.commit_source("dab")

                elif src == "webradio":
                    _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                                     if "  " in node.label else node.label.lstrip("★ ").strip())
                    _url = meta.get("url", "")
                    webradio.play_station({"name": _name, "url": _url}, S, settings)
                    source_state.commit_source("webradio")

            except Exception as e:
                log.error(f"PLAY_STATION switch error: {e}")
            finally:
                _source_switch_end()
                source_state.end_transition()

        bg(_run_station_switch)
        return

    action = node.action
    if not action:
        return

    log.info(f"MENU_ACTION id={node.id} type={node.type} action={action}")

    if node.type == "toggle":
        __import__("trigger_dispatcher").handle_trigger(action, menu_state, store, S, settings)
        return

    __import__("trigger_dispatcher").handle_trigger(action, menu_state, store, S, settings)



def _fm_manual(S, settings):
    freq_str = fm.freq_input_screen()
    if freq_str:
        fm.play_station({"name": f"{freq_str} MHz", "freq": freq_str}, S)



