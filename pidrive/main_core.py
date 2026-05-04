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

# ── Trigger-Dispatcher (ausgelagert v0.10.16) ─────────────────────────────────
from trigger_dispatcher import (
    handle_trigger, _execute_node, _fm_manual,
    _set_guards, _debounced,
)

# Guards registrieren (nach allen lokalen Definitionen)
def _init_dispatcher():
    _set_guards(
        begin_fn = _source_switch_begin,
        end_fn   = _source_switch_end,
        info_fn  = _source_switch_info,
        sc_begin = _scan_begin,
        sc_end   = _scan_end,
        sc_info  = _scan_info,
    )
    # Guards auch in td_nav setzen — _execute_node lebt dort und braucht sie
    import td_nav as _td_nav
    _td_nav._set_nav_guards(
        begin_fn = _source_switch_begin,
        end_fn   = _source_switch_end,
        info_fn  = _source_switch_info,
    )


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
    # v0.10.16: Trigger-Dispatcher Guards registrieren
    _init_dispatcher()
    
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