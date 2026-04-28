"""
main_core.py — PiDrive Hauptprozess (Core)
Aufrufer: systemd pidrive_core.service
Abhängig von: alle modules/*, ipc.py, settings.py, menu_model.py
Schreibt: /tmp/pidrive_cmd (liest), /tmp/pidrive_status.json, /tmp/pidrive_menu.json
"""


import sys, os, time, json, signal
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

signal.signal(signal.SIGHUP, signal.SIG_IGN)

import log, ipc
import status as S_module
try:
    import mpris2 as _mpris2
except Exception:
    _mpris2 = None
from menu_model import MenuNode, MenuState, StationStore, build_tree
from modules import source_state
from modules import (
    musik, wifi, bluetooth, audio, system as sys_mod,
    gpio_buttons as _gpio_buttons,
    webradio, dab, fm, library, scanner, update, favorites
)

logger = log.setup("core")

CONFIG_DIR = os.path.join(BASE_DIR, "config")

from settings import load_settings, save_settings  # noqa: E402


# ── Globaler Scan-Guard ──────────────────────────────────────────────────────

import threading as _scan_threading

_SCAN_LOCK  = _scan_threading.Lock()
_SCAN_STATE = {"active": False, "source": "", "started_ts": 0}


def _scan_begin(source):
    with _SCAN_LOCK:
        if _SCAN_STATE["active"]:
            return False
        _SCAN_STATE.update({
            "active": True,
            "source": source,
            "started_ts": int(time.time())
        })
        return True


def _scan_end():
    with _SCAN_LOCK:
        _SCAN_STATE.update({"active": False, "source": "", "started_ts": 0})


def _scan_info():
    with _SCAN_LOCK:
        return dict(_SCAN_STATE)


# ── Globaler Source-Switch-Lock ──────────────────────────────────────────────

import threading as _src_threading

_SOURCE_SWITCH_LOCK  = _src_threading.Lock()
_SOURCE_SWITCH_STATE = {"active": False, "owner": "", "started_ts": 0.0}


def _source_switch_begin(owner="unknown", blocking=False):
    ok = _SOURCE_SWITCH_LOCK.acquire(blocking=blocking)
    if not ok:
        return False
    _SOURCE_SWITCH_STATE["active"]     = True
    _SOURCE_SWITCH_STATE["owner"]      = owner
    _SOURCE_SWITCH_STATE["started_ts"] = _time_mod.time() if "_time_mod" in dir() else 0.0
    return True


def _source_switch_end():
    try:
        if _SOURCE_SWITCH_LOCK.locked():
            _SOURCE_SWITCH_STATE["active"]     = False
            _SOURCE_SWITCH_STATE["owner"]      = ""
            _SOURCE_SWITCH_STATE["started_ts"] = 0.0
            _SOURCE_SWITCH_LOCK.release()
    except RuntimeError:
        pass


def _source_switch_info():
    return dict(_SOURCE_SWITCH_STATE)


# ── Trigger-Entprellung ──────────────────────────────────────────────────────

import time as _time_mod

_LAST_TRIGGER_TS: dict = {}
_TRIGGER_DEBOUNCE = {
    "enter":    0.35,
    "fm_next":  0.5,
    "fm_prev":  0.5,
    "dab_next": 0.5,
    "dab_prev": 0.5,
}

_LAST_NODE_EXEC_TS  = 0.0
_LAST_NODE_EXEC_ID  = ""


def _debounced(cmd: str) -> bool:
    now   = _time_mod.time()
    limit = _TRIGGER_DEBOUNCE.get(cmd)
    if not limit:
        return False
    last = _LAST_TRIGGER_TS.get(cmd, 0.0)
    if now - last < limit:
        log.info(f"TRIGGER debounce: {cmd}")
        return True
    _LAST_TRIGGER_TS[cmd] = now
    return False


# ── BT-Agent früh starten ────────────────────────────────────────────────────

def _start_bt_agent_early():
    try:
        if bluetooth.start_agent_session():
            log.info("BT agent startup: OK")
        else:
            log.warn("BT agent startup: failed")
        bluetooth.start_agent_health_thread()
    except Exception as e:
        log.warn("BT agent startup: " + str(e))


# ── Trigger-Handling ─────────────────────────────────────────────────────────

def handle_trigger(cmd, menu_state, store, S, settings):
    rebuild = False

    if _debounced(cmd):
        return False

    def bg(fn):
        import threading
        threading.Thread(target=fn, daemon=True).start()

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

    # ── Spotify ───────────────────────────────────────────────────────────
    elif cmd in ("spotify_on", "spotify_off", "spotify_toggle"):
        bg(lambda: musik.spotify_toggle(S))

    # ── Audio ─────────────────────────────────────────────────────────────
    elif cmd == "audio_klinke":
        bg(lambda: audio.set_output("klinke", settings))
    elif cmd == "audio_hdmi":
        bg(lambda: audio.set_output("hdmi", settings))
    elif cmd == "audio_bt":
        bg(lambda: audio.set_output("bt", settings))
    elif cmd == "audio_all":
        bg(lambda: audio.set_output("all", settings))
    elif cmd == "vol_up":
        bg(lambda: audio.volume_up(settings))
    elif cmd == "vol_down":
        bg(lambda: audio.volume_down(settings))

    # ── WiFi / BT ─────────────────────────────────────────────────────────
    elif cmd in ("wifi_on", "wifi_off", "wifi_toggle"):
        bg(lambda: wifi.wifi_toggle(S))
    elif cmd in ("bt_on", "bt_off", "bt_toggle"):
        bg(lambda: bluetooth.bt_toggle(S))
    elif cmd == "wifi_scan":
        bg(lambda: wifi.scan_networks(S, settings))
    elif cmd == "bt_scan":
        def _bt_scan_trigger():
            if not S.get("bt_on", False) and not S.get("bt", False):
                log.info("bt_scan: BT war aus — schalte ein")
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
        bg(_bt_scan_trigger)
    elif cmd.startswith("bt_connect:"):
        mac = cmd.split(":", 1)[1].strip()
        bg(lambda m=mac: bluetooth.connect_device(m, S, settings))

    elif cmd.startswith("bt_forget:"):
        # v0.9.29: Gerät vergessen — aus BlueZ und known_devices entfernen
        mac = cmd.split(":", 1)[1].strip()
        def _bt_forget(m=mac):
            try:
                bluetooth._btctl(f"remove {m}", timeout=10)
                knw = bluetooth._get_known_devices()
                bluetooth._write_known_devices([d for d in knw if d.get("mac") != m])
                log.info(f"BT: Gerät vergessen mac={m}")
                S["menu_rev"] = S.get("menu_rev", 0) + 1
            except Exception as _e:
                log.warn(f"BT forget: {_e}")
        bg(_bt_forget)
    elif cmd == "bt_disconnect":
        bg(lambda: bluetooth.disconnect_current(S, settings))
    elif cmd == "bt_reconnect_last":
        # v0.9.30: TICKET 1 — Watcher aufwecken
        bluetooth.wake_auto_reconnect()
        bg(lambda: bluetooth.reconnect_last(S, settings))
    elif cmd == "bt_backup":
        def _do_bt_backup():
            try:
                from modules import bt_backup as _btb
                ipc.write_progress("BT-Backup", "Sichern...", color="blue")
                res = _btb.backup()
                if res.get("ok"):
                    info = _btb.backup_info()
                    devs = len(info.get("devices", []))
                    ipc.write_progress("BT-Backup", f"OK — {devs} Gerät(e) gesichert ✓", color="green")
                    log.info(f"BT-Backup: {res['count']} Dateien")
                else:
                    ipc.write_progress("BT-Backup", f"Fehler: {res.get('error','?')}", color="red")
                import time as _t
                _t.sleep(3)
                ipc.clear_progress()
            except Exception as e:
                log.error(f"bt_backup Trigger: {e}")
                ipc.clear_progress()
        bg(_do_bt_backup)

    elif cmd == "bt_restore":
        def _do_bt_restore():
            try:
                from modules import bt_backup as _btb
                if not _btb.has_backup():
                    ipc.write_progress("BT-Restore", "Kein Backup vorhanden!", color="orange")
                    import time as _t
                    _t.sleep(3)
                    ipc.clear_progress()
                    return
                ipc.write_progress("BT-Restore", "Wiederherstellung...", color="blue")
                res = _btb.restore()
                if res.get("ok"):
                    ipc.write_progress("BT-Restore", "OK — bluetoothd neugestartet ✓", color="green")
                    log.info(f"BT-Restore: {res['count']} Dateien")
                else:
                    ipc.write_progress("BT-Restore", f"Fehler: {res.get('error','?')}", color="red")
                import time as _t
                _t.sleep(3)
                ipc.clear_progress()
            except Exception as e:
                log.error(f"bt_restore Trigger: {e}")
                ipc.clear_progress()
        bg(_do_bt_restore)

    elif cmd.startswith("bt_repair:"):
        mac = cmd.split(":", 1)[1].strip()
        bg(lambda m=mac: bluetooth.repair_device(m, S, settings))
    elif cmd.startswith("wifi_connect:"):
        ssid = cmd.split(":", 1)[1]
        bg(lambda s=ssid: wifi.connect_network(s, S, settings))

    # ── Gain ──────────────────────────────────────────────────────────────
    elif cmd.startswith("fm_gain:"):
        try:
            val = int(cmd.split(":", 1)[1].strip())
            settings["fm_gain"] = val
            save_settings(settings)
            ipc.write_progress("FM Gain", f"{'Auto (AGC)' if val == -1 else str(val) + ' dB'}", color="green")
            import time as _tg
            _tg.sleep(1)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"fm_gain Trigger: {e}")

    elif cmd.startswith("dab_gain:"):
        try:
            val = int(cmd.split(":", 1)[1].strip())
            settings["dab_gain"] = val
            save_settings(settings)
            ipc.write_progress("DAB Gain", f"{'Auto (AGC)' if val == -1 else str(val) + ' dB'}", color="green")
            import time as _tg2
            _tg2.sleep(1)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"dab_gain Trigger: {e}")

    elif cmd.startswith("ppm:"):
        try:
            val = int(cmd.split(":", 1)[1].strip())
            settings["ppm_correction"] = val
            save_settings(settings)
            label = f"{val:+d} ppm" if val != 0 else "deaktiviert (0)"
            ipc.write_progress("PPM", f"Korrektur: {label}", color="green")
            log.info(f"TRIGGER ppm_correction={val}")
            import time as _tp
            _tp.sleep(1)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"ppm Trigger: {e}")

    elif cmd.startswith("squelch:"):
        try:
            val = int(cmd.split(":", 1)[1].strip())
            val = max(0, min(val, 50))
            settings["scanner_squelch"] = val
            save_settings(settings)
            label = "immer offen" if val == 0 else str(val)
            ipc.write_progress("Squelch", f"Schwelle: {label}", color="green")
            log.info(f"TRIGGER scanner_squelch={val}")
            import time as _tq
            _tq.sleep(1)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"squelch Trigger: {e}")

    elif cmd.startswith("scanner_gain:"):
        try:
            val = int(cmd.split(":", 1)[1].strip())
            val = max(-1, min(val, 49))
            settings["scanner_gain"] = val
            save_settings(settings)
            label = "Auto (AGC)" if val == -1 else f"{val} dB"
            ipc.write_progress("Scanner Gain", label, color="green")
            log.info(f"TRIGGER scanner_gain={val}")
            import time as _tsg
            _tsg.sleep(1)
            ipc.clear_progress()
        except Exception as e:
            log.error(f"scanner_gain Trigger: {e}")

    # ── RTL-SDR Reset ─────────────────────────────────────────────────────
    elif cmd == "rtlsdr_reset":
        def _do_rtlsdr_reset():
            try:
                from modules import rtlsdr as _rtl
                ipc.write_progress("RTL-SDR", "USB-Reset läuft...", color="blue")
                result = _rtl.usb_reset()
                if result.get("ok"):
                    ipc.write_progress("RTL-SDR", "Reset OK — Stick erkannt ✓", color="green")
                    log.info("RTLSDR_RESET: OK — Stick wieder erkannt")
                else:
                    ipc.write_progress("RTL-SDR", "Reset: Stick nicht erkannt — Abziehen/Einstecken nötig", color="orange")
                    log.warn("RTLSDR_RESET: Stick nach Reset nicht erkannt")
                import time as _t
                _t.sleep(3)
                ipc.clear_progress()
            except Exception as e:
                log.error(f"RTLSDR_RESET Fehler: {e}")
                ipc.clear_progress()
        bg(_do_rtlsdr_reset)

    elif cmd == "radio_stop":
        def _radio_stop():
            if source_state.begin_transition("trigger:radio_stop", "idle"):
                try:
                    webradio.stop(S)
                    dab.stop(S)
                    fm.stop(S)
                    scanner.stop(S)
                    S["radio_playing"] = False
                    S["radio_station"] = ""
                    S["radio_name"] = ""
                    S["radio_type"] = ""
                    S["control_context"] = "idle"
                    source_state.commit_source("idle")
                finally:
                    source_state.end_transition()
            else:
                webradio.stop(S)
                dab.stop(S)
                fm.stop(S)
                scanner.stop(S)
                S["radio_playing"] = False
                S["radio_station"] = ""
                S["radio_name"] = ""
                S["radio_type"] = ""
                S["control_context"] = "idle"
                source_state.commit_source("idle")
        bg(_radio_stop)

    elif cmd == "radio_restart_on_bt":
        def _radio_restart():
            import time
            # v0.9.21: 3s warten — PulseAudio braucht ~2s um A2DP-Sink zu registrieren
            # Ohne Wartezeit findet get_bt_sink() den Sink noch nicht → Klinke statt BT
            time.sleep(3)
            _rtype = S.get("radio_type", "")
            _last_web = settings.get("last_web_station")
            _last_dab = settings.get("last_dab_station")
            _last_fm  = settings.get("last_fm_station")
            from modules.audio import is_radio_source
            if not is_radio_source(_rtype):
                log.info("[AUDIO] radio_restart_on_bt: kein Neustart — source=" + (_rtype or "none"))
            elif _rtype == "WEB" and _last_web:
                log.info("[AUDIO] radio_restart_on_bt source=webradio: " + str(_last_web.get("name","")))
                webradio.play_station(_last_web, S, settings)
            elif _rtype == "DAB" and _last_dab:
                log.info("[AUDIO] radio_restart_on_bt source=dab: " + str(_last_dab.get("name","")))
                dab.play_station(_last_dab, S, settings)
            elif _rtype == "FM" and _last_fm:
                log.info("[AUDIO] radio_restart_on_bt source=fm: " + str(_last_fm.get("name","")))
                fm.play_station(_last_fm, S, settings)
            else:
                log.info("[AUDIO] radio_restart_on_bt: keine letzte Station fuer " + _rtype)
        import threading
        threading.Thread(target=_radio_restart, daemon=True).start()

    elif cmd == "library_stop":
        library.stop_playback(S)

    # ── DAB Suchlauf ───────────────────────────────────────────────────────
    elif cmd == "dab_scan":
        def _dab_scan():
            if not _scan_begin("dab"):
                info = _scan_info()
                log.warn("SCAN_BLOCKED source=dab running=" + info.get("source","?"))
                ipc.write_progress("DAB+ Suchlauf",
                    "Schon aktiv: " + info.get("source","?").upper(), color="orange")
                time.sleep(2)
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
                    time.sleep(2)
                    new_root = build_tree(store, S, settings)
                    menu_state.root = new_root
                    menu_state.clamp_cursors()
                    menu_state.rev += 1
                else:
                    log.warn("SCAN_DONE source=dab count=0 — bestehende Liste bleibt")
                    ipc.write_progress("DAB+ Suchlauf", "0 Sender — Liste bleibt erhalten", color="orange")
                    time.sleep(2)
            except Exception as e:
                log.error(f"SCAN_FAIL source=dab error={e}")
                ipc.write_progress("DAB+ Fehler", str(e)[:48], color="red")
                source_state.commit_source("idle")
                time.sleep(3)
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
                    time.sleep(2)
                    ipc.clear_progress()
                    return

                if not source_state.begin_transition(owner, "dab"):
                    ipc.write_progress("DAB+ Suchlauf", "Blockiert", color="orange")
                    time.sleep(2)
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
                    time.sleep(2)
                except Exception as e:
                    log.error(f"SCAN_FAIL dab custom: {e}")
                    source_state.commit_source("idle")
                    time.sleep(3)
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
                time.sleep(2)
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
                time.sleep(2)

                if count > 0:
                    new_root = build_tree(store, S, settings)
                    menu_state.root = new_root
                    menu_state.clamp_cursors()
                    menu_state.rev += 1
            except Exception as e:
                log.error(f"SCAN_FAIL source=fm error={e}")
                ipc.write_progress("FM Fehler", str(e)[:48], color="red")
                time.sleep(3)
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
            time.sleep(2)
            ipc.clear_progress()
        else:
            source = cmd.split(":", 1)[1]
            store.reload_source(source)
            rebuild = True
            log.info(f"STATIONS_RELOAD source={source}")
            ipc.write_progress("Senderliste", f"{source} neu geladen", color="green")
            time.sleep(1)
            ipc.clear_progress()

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

    # ── Scanner ─────────────────────────────────────────────────────────────
    elif cmd.startswith("scan_up:"):
        band = cmd.split(":", 1)[1]
        def _scan_up(b=band):
            source_state.begin_transition(f"scan_up:{b}", "scanner")
            try:
                scanner.channel_up(b, S)
            finally:
                source_state.end_transition()
        bg(_scan_up)

    elif cmd.startswith("scan_down:"):
        band = cmd.split(":", 1)[1]
        def _scan_down(b=band):
            source_state.begin_transition(f"scan_down:{b}", "scanner")
            try:
                scanner.channel_down(b, S)
            finally:
                source_state.end_transition()
        bg(_scan_down)

    elif cmd.startswith("scan_next:"):
        band = cmd.split(":", 1)[1]
        def _scan_next(b=band):
            if source_state.begin_transition(f"scan_next:{b}", "scanner"):
                try:
                    scanner.scan_next(b, S, settings)
                finally:
                    source_state.end_transition()
        bg(_scan_next)

    elif cmd.startswith("scan_prev:"):
        band = cmd.split(":", 1)[1]
        def _scan_prev(b=band):
            if source_state.begin_transition(f"scan_prev:{b}", "scanner"):
                try:
                    scanner.scan_prev(b, S, settings)
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
                bg(lambda b=band, d=delta: scanner.channel_jump(b, d, S))

    elif cmd.startswith("scan_step:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                delta = float(parts[2])
            except Exception:
                delta = 0.0
            if delta:
                bg(lambda b=band, d=delta: scanner.freq_step(b, d, S, settings))

    elif cmd.startswith("scan_setfreq:"):
        parts = cmd.split(":")
        if len(parts) >= 3:
            band = parts[1]
            try:
                freq = float(parts[2])
            except Exception:
                freq = 0.0
            if freq:
                bg(lambda b=band, f=freq: scanner.set_freq(b, f, S, settings))

    elif cmd.startswith("scan_inputfreq:"):
        parts = cmd.split(":")
        if len(parts) >= 2:
            band = parts[1]
            def _input_and_set(b=band):
                freq = scanner.freq_input_screen(b, settings)
                if freq is not None:
                    scanner.set_freq(b, freq, S, settings)
            bg(_input_and_set)

    # ── Bibliothek ─────────────────────────────────────────────────────────
    elif cmd == "lib_browse":
        bg(lambda: library.browse_and_play(S, load_settings()))

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
            rebuild_tree(menu_state, store, S, settings)
        except Exception as _fe:
            log.warn("fav_toggle: " + str(_fe))

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

    log.trigger_received(cmd)
    if cmd.startswith("reload_stations:"):
        log.info(f"STATIONS_RELOAD source={cmd.split(':',1)[1]}")
    return rebuild


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
                    fm.play_station({"name": _name, "freq": _freq}, S, settings)
                    source_state.commit_source("fm")

                elif src == "dab":
                    _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                                     if "  " in node.label else node.label.lstrip("★ ").strip())
                    _sid = meta.get("service_id", "")
                    dab.play_by_name(_name, S, service_id=_sid)
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
        handle_trigger(action, menu_state, store, S, settings)
        return

    handle_trigger(action, menu_state, store, S, settings)


def _fm_manual(S, settings):
    freq_str = fm.freq_input_screen()
    if freq_str:
        fm.play_station({"name": f"{freq_str} MHz", "freq": freq_str}, S)


def check_trigger(menu_state, store, S, settings):
    if not os.path.exists(ipc.CMD_FILE):
        return False

    NAV_CMDS = {"up", "down", "enter", "back", "left", "right"}
    try:
        lst = ipc.read_json(ipc.LIST_FILE, {})
        if lst.get("active"):
            with open(ipc.CMD_FILE) as f:
                peek = f.read().strip()
            if peek in NAV_CMDS:
                return False
    except Exception:
        pass

    try:
        with open(ipc.CMD_FILE) as f:
            cmd = f.read().strip()
        os.remove(ipc.CMD_FILE)
    except Exception:
        return False

    if not cmd:
        return False

    try:
        return handle_trigger(cmd, menu_state, store, S, settings)
    except Exception as e:
        log.error(f"Trigger '{cmd}' Fehler: {e}")
        return False


# ── System-Check ────────────────────────────────────────────────────────────

def system_check():
    import subprocess
    log.info("--- Core System-Check ---")
    VERSION = open(os.path.join(BASE_DIR, "VERSION")).read().strip()
    log.info(f"  PiDrive Core v{VERSION}")

    for path, label in [("/dev/fb1", "SPI Display"), ("/dev/fb0", "HDMI Framebuffer")]:
        if os.path.exists(path):
            log.info(f"  ✓ {label}: {path}")
        else:
            log.warn(f"  ✗ {label}: {path} nicht gefunden")

    log.info("  USB-Geraete:")
    try:
        r = subprocess.run("lsusb 2>/dev/null", shell=True,
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(x in line.lower() for x in ["rtl", "2832", "2838"]):
                log.info(f"    ✓ RTL-SDR: {line}")
            elif any(x in line.lower() for x in ["bluetooth", "broadcom", "cambridge"]):
                log.info(f"    ✓ BT: {line}")
            elif any(x in line.lower() for x in ["hub", "root hub"]):
                pass
            else:
                log.info(f"    · {line}")
        if not r.stdout.strip():
            log.warn("    (keine USB-Geraete gefunden)")
    except Exception as _e:
        log.warn(f"  USB scan: {_e}")

    log.info("  Netzwerk:")
    try:
        r = subprocess.run(["ip", "-4", "addr", "show"],
                           capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            if "inet " in line and "127." not in line:
                parts = line.strip().split()
                ip   = parts[1].split("/")[0]
                iface = ""
                for prev in r.stdout[:r.stdout.find(line)].splitlines():
                    if ":" in prev and not prev.startswith(" "):
                        iface = prev.split(":")[1].strip().split()[0]
                log.info(f"    ✓ {iface}: {ip}")
        ssid = subprocess.run("iwgetid -r 2>/dev/null",
                              shell=True, capture_output=True, text=True, timeout=2).stdout.strip()
        if ssid:
            log.info(f"    ✓ SSID: {ssid}")
    except Exception:
        pass

    try:
        hc = subprocess.run("hciconfig 2>/dev/null",
                            shell=True, capture_output=True, text=True, timeout=3)
        if "UP RUNNING" in hc.stdout:
            log.info("  ✓ Bluetooth: UP RUNNING")
            paired = subprocess.run("bluetoothctl paired-devices 2>/dev/null",
                                    shell=True, capture_output=True, text=True, timeout=3)
            devs = [l for l in paired.stdout.splitlines() if l.startswith("Device")]
            if devs:
                for d in devs:
                    p = d.split(" ", 2)
                    name = p[2] if len(p) > 2 else p[1]
                    log.info(f"    ★ Gepairt: {name} ({p[1]})")
            else:
                log.info("    (keine gepairten Geraete)")
        else:
            log.warn("  ⚠ Bluetooth: nicht aktiv")
    except Exception:
        pass

    try:
        pa = subprocess.run(["systemctl", "is-active", "pulseaudio"],
                            capture_output=True, text=True, timeout=3)
        if pa.stdout.strip() == "active":
            log.info("  ✓ PulseAudio: aktiv (BT A2DP)")
        else:
            log.warn("  ⚠ PulseAudio: nicht aktiv")
    except Exception:
        pass

    try:
        sp = subprocess.run(["systemctl", "is-active", "raspotify"],
                            capture_output=True, text=True, timeout=3)
        if sp.stdout.strip() == "active":
            log.info("  ✓ Raspotify: aktiv")
        else:
            log.warn("  ⚠ Raspotify: nicht aktiv")
    except Exception:
        pass

    try:
        from modules import rtlsdr as _rtlsdr_check
        _rtlsdr_check.log_startup_check(log)
    except Exception as _e:
        log.warn("  ⚠ RTL-SDR Check: " + str(_e))

    log.info("--- System-Check OK ---")


# ── Menü neu bauen nach Scan/Reload ────────────────────────────────────────

def rebuild_tree(menu_state, store, S, settings):
    old_path = menu_state.path[:]
    new_root = build_tree(store, S, settings)
    menu_state.root = new_root

    menu_state._stack   = [new_root]
    menu_state._cursors = [0]
    for label in old_path[1:]:
        found = False
        for i, child in enumerate(menu_state.current.children):
            if child.label == label:
                menu_state._stack.append(child)
                menu_state._cursors.append(0)
                found = True
                break
        if not found:
            break

    menu_state.clamp_cursors()
    menu_state.rev += 1
    log.info(f"MENU_REBUILD path={'/'.join(menu_state.path)} cursor={menu_state.cursor}")


# ── Startup Tasks ───────────────────────────────────────────────────────────

def startup_tasks(S, settings):
    """
    Einmalig beim Start: BT reconnect + letzte Station wiederherstellen.
    v0.9.30: Phasen — restore_bt_prepare → restore_bt_try_once →
                       audio_base_ready → restore_source → steady
    """
    import time, subprocess as _sp_boot

    # ── TICKET 7: Boot-Readiness — warte auf PulseAudio + BT-Adapter ────────
    source_state.set_boot_phase("restore_bt_prepare")
    _ready = False
    for _attempt in range(12):  # max 12s warten
        try:
            _pa_ok = _sp_boot.run(
                "PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null",
                shell=True, capture_output=True, timeout=2
            ).returncode == 0
            _bt_ok = _sp_boot.run(
                "hciconfig hci0 2>/dev/null | grep -q UP",
                shell=True, capture_output=True, timeout=2
            ).returncode == 0
            if _pa_ok and _bt_ok:
                log.info(f"Boot-Readiness: PulseAudio + BT bereit ({_attempt+1}s)")
                _ready = True
                break
        except Exception:
            pass
        time.sleep(1)
    if not _ready:
        log.warn("Boot-Readiness: Timeout — starte trotzdem (PulseAudio oder BT nicht bereit)")

    # ── Phase BT-Reconnect ────────────────────────────────────────────────────
    source_state.set_boot_phase("restore_bt")

    try:
        if bluetooth.reconnect_known_devices(S, settings):
            log.info("BT Boot-Reconnect: verbunden")
        else:
            # v0.9.26: bt_state explizit auf failed setzen statt in "connecting" hängen
            source_state.set_bt_state("failed")
            log.info("BT Boot-Reconnect: kein Gerät verfügbar → bt_state=failed")
    except Exception as _e:
        source_state.set_bt_state("failed")
        log.warn("BT Boot-Reconnect: " + str(_e))

    try:
        _gpio_active = _gpio_buttons.start()
        if _gpio_active:
            log.info("GPIO: Tasten aktiv (Key1=up, Key2=enter, Key3=back)")
        else:
            log.info("GPIO: nicht verfügbar (kein RPi.GPIO oder kein Raspberry Pi)")
    except Exception as _eg:
        log.warn(f"GPIO start: {_eg}")

    # ── TICKET 3: audio_route immer explizit setzen ──────────────────────────
    source_state.set_boot_phase("audio_base_ready")
    try:
        from modules.audio import _set_pi_output_klinke, get_mpv_args
        _audio_out = settings.get("audio_output", "auto")
        if S.get("bt") and S.get("bt_pa_sink"):
            source_state.set_audio_route("bt")
            log.info("Boot: Audio-Basis = bt (A2DP verbunden)")
        elif _audio_out == "hdmi":
            source_state.set_audio_route("hdmi")
            log.info("Boot: Audio-Basis = hdmi")
        else:
            _set_pi_output_klinke()
            source_state.set_audio_route("klinke")
            log.info("Boot: Audio-Basis = klinke (amixer Card 1 aktiviert)")
        # Audio-State-Datei einmal explizit schreiben damit WebUI+Diagnose konsistent sind
        get_mpv_args(settings, source="boot_audio_base")
    except Exception as _ea:
        log.warn("Boot amixer: " + str(_ea))

    try:
        from modules import audio as _aud_vol
        # v0.9.25: Volume in settings.json auf max 100% korrigieren
        try:
            if int(settings.get("volume", 90)) > 100:
                settings["volume"] = 90
                from settings import save_settings
                save_settings(settings)
                log.info("[AUDIO] volume > 100 in settings → auf 90% korrigiert")
        except Exception:
            pass
        _aud_vol.apply_startup_volume(settings)
    except Exception as _ev:
        log.warn("Boot startup_volume: " + str(_ev))

    source_state.set_boot_phase("restore_source")

    try:
        time.sleep(1)
        last_src   = settings.get("last_source", "")
        last_fm    = settings.get("last_fm_station")
        last_dab   = settings.get("last_dab_station")
        last_web   = settings.get("last_web_station")
        # v0.9.29: Resume-State sofort loggen für Diagnose
        _dab_name = (last_dab or {}).get("name", "–") if last_dab else "–"
        _dab_sid  = (last_dab or {}).get("service_id", "–") if last_dab else "–"
        _web_name = (last_web or {}).get("name", "–") if last_web else "–"
        log.info(f"Boot-Resume-State: last_source={last_src!r} dab={_dab_name}({_dab_sid}) web={_web_name}")

        # v0.9.27: last_source ist die autoritäre Quelle — kein Fallback der überschreibt
        if last_src == "fm" and last_fm and last_fm.get("freq"):
            log.info("Boot-Resume: FM → " + str(last_fm.get("name", last_fm.get("freq", ""))))
            fm.play_station(last_fm, S, settings)

        elif last_src == "dab" and last_dab and last_dab.get("name"):
            # DAB-Resume: service_id + channel bevorzugt (stabil, kein Name-Lookup nötig)
            _sid = last_dab.get("service_id", "")
            _ch  = last_dab.get("channel", "")
            _nm  = last_dab.get("name", "")
            log.info(f"Boot-Resume: DAB → {_nm} (ch={_ch} sid={_sid})")
            dab.play_station(last_dab, S, settings)

        elif last_src == "webradio" and last_web and last_web.get("url"):
            log.info("Boot-Resume: Webradio → " + str(last_web.get("name", "")))
            webradio.play_station(last_web, S, settings)

        elif last_src and not last_src:
            pass  # last_source explizit leer → kein Resume
        elif last_fm and last_fm.get("freq") and not last_src:
            # Nur Fallback wenn last_source wirklich leer (Erststart / Migration)
            log.info("Boot-Resume: FM (Erststart-Fallback) → " + str(last_fm.get("name", "")))
            fm.play_station(last_fm, S, settings)
        elif last_dab and last_dab.get("name") and not last_src:
            log.info("Boot-Resume: DAB (Erststart-Fallback) → " + str(last_dab.get("name", "")))
            dab.play_station(last_dab, S, settings)

        else:
            log.info("Boot-Resume: keine letzte Quelle gespeichert")

    except Exception as _e:
        log.warn("Boot-Resume: " + str(_e))
    finally:
        source_state.set_boot_phase("steady")
        # v0.9.30: TICKET 2 — Watcher erst jetzt starten (nach boot_phase=steady)
        try:
            bluetooth.start_auto_reconnect(S, settings)
            log.info("BT auto-reconnect: Watcher gestartet (boot_phase=steady)")
        except Exception as _e_w:
            log.warn(f"BT Watcher Start: {_e_w}")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # VERSION aus Datei lesen — muss vor dem Banner passieren
    global VERSION
    try:
        VERSION = open(os.path.join(BASE_DIR, "VERSION")).read().strip()
    except Exception:
        VERSION = "?"
    log.info("=" * 50)
    # v0.9.28: Klarer Boot-Marker für Log-Auswertung
    import datetime as _dt
    log.info(f"===== BOOT {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} PiDrive v{VERSION} =====")
    log.info(f"PiDrive Core v{VERSION} gestartet")
    log.info(f"  PID={os.getpid()}  UID={os.getuid()}")
    _start_bt_agent_early()
    log.info("  Headless — kein Display benoetigt")
    log.info(f"  Trigger: echo 'cmd' > {ipc.CMD_FILE}")
    log.info("=" * 50)

    system_check()

    _mpris2_player = _mpris2.start_mpris2() if _mpris2 else None

    settings = load_settings()
    try:
        from settings import ensure_settings_file
        ensure_settings_file()
        settings = load_settings()
    except Exception:
        pass

    S_module.start()
    S = S_module.S

    store = StationStore(CONFIG_DIR)
    store.load_all()

    root = build_tree(store, S, settings)
    menu_state = MenuState(root)

    stat_timer  = time.time()
    ipc_timer   = time.time()
    store_timer = time.time()

    log.info("Core-Loop gestartet")
    # v0.9.30: TICKET 2 — Watcher startet erst am Ende von startup_tasks()
    # (nach boot_phase=steady), nicht mehr hier direkt

    _ready_written = False
    import threading as _thr
    _thr.Thread(target=startup_tasks, args=(S_module.S, settings), daemon=True).start()

    while True:
        S = S_module.S

        needs_rebuild = check_trigger(menu_state, store, S, settings)
        if needs_rebuild:
            rebuild_tree(menu_state, store, S, settings)

        cur_s_rev = S.get("menu_rev", 0)
        if cur_s_rev != getattr(main, '_last_s_rev', 0):
            main._last_s_rev = cur_s_rev
            if not needs_rebuild:
                rebuild_tree(menu_state, store, S, settings)

        if needs_rebuild or (os.path.exists(ipc.CMD_FILE) is False and
                             menu_state.rev != getattr(main, '_last_rev', -1)):
            ipc.write_menu(menu_state.export())
            main._last_rev = menu_state.rev

        if time.time() - store_timer > 10:
            if store.reload_if_changed():
                rebuild_tree(menu_state, store, S, settings)
            store_timer = time.time()

        bt_now = S.get("bt", False)
        if getattr(main, '_bt_was_connected', False) and not bt_now:
            if settings.get("audio_output") == "bt":
                log.info("BT getrennt — Audio Fallback auf Klinke")
                settings["audio_output"] = "klinke"
                settings["alsa_device"] = "default"

                def _bt_disconnect_bg():
                    try:
                        import subprocess
                        PA = "PULSE_SERVER=unix:/var/run/pulse/native"
                        sinks = subprocess.run(
                            PA + " pactl list sinks short 2>/dev/null",
                            shell=True, capture_output=True, text=True, timeout=3
                        )
                        import re as _re
                        alsa_sink = ""
                        for line in sinks.stdout.splitlines():
                            parts = line.split()
                            if len(parts) >= 2 and _re.search(r"alsa_output\.1\.", parts[1]):
                                alsa_sink = parts[1]
                                break
                        if not alsa_sink:
                            # Fallback: erstes ALSA das kein HDMI (Card 0) ist
                            for line in sinks.stdout.splitlines():
                                parts = line.split()
                                if (len(parts) >= 2 and "alsa_output" in parts[1]
                                        and not _re.search(r"alsa_output\.0\.", parts[1])):
                                    alsa_sink = parts[1]
                                    break
                        if alsa_sink:
                            subprocess.run(
                                PA + " pactl set-default-sink " + alsa_sink,
                                shell=True, timeout=3
                            )
                            log.info("[AUDIO] bt_disconnected → PA zurück auf " + alsa_sink)

                        _rtype = S.get("radio_type", "")
                        from modules.audio import is_radio_source
                        if S.get("radio_playing") and is_radio_source(_rtype):
                            log.info("[AUDIO] radio_restart_on_disconnect source=" + _rtype)
                            import time as _td
                            _td.sleep(0.5)
                            with open("/tmp/pidrive_cmd", "w") as _cf:
                                _cf.write("radio_restart_on_bt\n")
                        elif _rtype:
                            log.info("[AUDIO] no restart on disconnect — source=" + _rtype)
                    except Exception as _e:
                        log.warn("BT Disconnect BG: " + str(_e))

                import threading
                threading.Thread(target=_bt_disconnect_bg, daemon=True).start()

        main._bt_was_connected = bt_now

        if time.time() - ipc_timer > 0.1:
            ipc.write_status(S, settings)
            exported = menu_state.export()
            ipc.write_menu(exported)

            if _mpris2:
                try:
                    _mpris2.update(S, exported)
                except Exception:
                    pass

            ipc_timer = time.time()
            if not _ready_written:
                try:
                    open(ipc.READY_FILE, "w").write("1")
                    _ready_written = True
                    log.info("IPC ready — /tmp/pidrive_ready geschrieben")
                except Exception:
                    pass

        if time.time() - stat_timer > 60:
            log.status_update(S["wifi"], S["bt"], S["spotify"],
                              settings.get("audio_output", "auto"))
            stat_timer = time.time()

        time.sleep(0.03)


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            bluetooth.stop_agent_session()
        except Exception:
            pass