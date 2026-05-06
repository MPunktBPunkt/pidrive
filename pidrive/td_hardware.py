#!/usr/bin/env python3
"""td_hardware.py — Audio, WiFi/BT, Gain, PPM, RTL-SDR  v0.10.38"""
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
    """Hardware-Trigger: Audio, WiFi, BT, Gain, PPM, Squelch, RTL-SDR."""
    # ── Spotify ───────────────────────────────────────────────────────────
    if cmd in ("spotify_on", "spotify_off", "spotify_toggle"):
        def _spotify_toggle():
            was_active = bool(S.get("spotify"))
            musik.spotify_toggle(S)
            if was_active:
                source_state.commit_source("idle")
                log.info("SOURCE spotify → idle (stop)")
            else:
                # v0.10.38: status.py forcieren statt blind 1.5s warten
                import time as _t
                for _attempt in range(6):      # max 3s in 0.5s-Schritten
                    _t.sleep(0.5)
                    S_module.refresh(force=True)
                    if S.get("spotify"):
                        source_state.commit_source("spotify")
                        log.info(f"SOURCE commit: spotify (attempt={_attempt+1})")
                        break
                else:
                    log.warn("SOURCE spotify: nicht aktiv nach 3s — kein commit")
        bg(_spotify_toggle)

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

    else:
        return False
    return True
