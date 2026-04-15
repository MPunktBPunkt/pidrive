"""
main_core.py - PiDrive Core v0.8.6

Headless Core — kein pygame, kein Display.
Baumbasiertes Menümodell (menu_model.py).
Stationslisten aus JSON (StationStore, Hot-Reload).
Suchlauf → JSON speichern → Menü sofort aktualisieren.

Triggerbasierte Steuerung: echo 'cmd' > /tmp/pidrive_cmd
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
from modules import (musik, wifi, bluetooth, audio, system as sys_mod,
                     webradio, dab, fm, library, scanner, update, favorites)

logger = log.setup("core")

CONFIG_DIR = os.path.join(BASE_DIR, "config")

# ── Settings ──────────────────────────────────────────────────────────────────

# load_settings / save_settings aus settings.py importieren
# (thread-safe: settings.py importiert KEIN main_core)
from settings import load_settings, save_settings  # noqa: E402


# ── Globaler Scan-Guard (verhindert parallele DAB/FM Scans) ─────────────────
import threading as _scan_threading

_SCAN_LOCK  = _scan_threading.Lock()
_SCAN_STATE = {"active": False, "source": "", "started_ts": 0}

def _scan_begin(source):
    """Exklusiven Scan-Slot reservieren. True = erfolgreich."""
    with _SCAN_LOCK:
        if _SCAN_STATE["active"]:
            return False
        _SCAN_STATE.update({"active": True, "source": source,
                             "started_ts": int(__import__("time").time())})
        return True

def _scan_end():
    """Scan-Slot freigeben."""
    with _SCAN_LOCK:
        _SCAN_STATE.update({"active": False, "source": "", "started_ts": 0})

def _scan_info():
    with _SCAN_LOCK:
        return dict(_SCAN_STATE)


# ── Trigger-Entprellung (v0.8.7) ───────────────────────────────────────────────
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
    """True = Befehl innerhalb Entprellzeit wiederholt → ignorieren."""
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


# ── Trigger-Handling ───────────────────────────────────────────────────────────

def handle_trigger(cmd, menu_state, store, S, settings):
    """Alle Trigger verarbeiten. Gibt True zurück wenn Menü neu gebaut werden soll."""
    rebuild = False

    # Entprellung für schnelle Doppeldrücker
    if _debounced(cmd):
        return False

    def bg(fn):
        import threading
        threading.Thread(target=fn, daemon=True).start()

    # ── Navigation ──────────────────────────────────────────────────────────
    if   cmd == "up":    menu_state.key_up()
    elif cmd == "down":  menu_state.key_down()
    elif cmd == "left":  menu_state.key_left()
    elif cmd == "back":  menu_state.key_back()
    elif cmd == "enter":
        node = menu_state.key_enter()
        if node and node.type in ("station", "action", "toggle"):
            _execute_node(node, menu_state, store, S, settings)
    elif cmd == "right":
        node = menu_state.key_right()
        if node and node.type in ("station", "action", "toggle"):
            _execute_node(node, menu_state, store, S, settings)

    # ── Direkt-Kategorie ────────────────────────────────────────────────────
    elif cmd.startswith("cat:"):
        val = cmd[4:]
        menu_state.navigate_to(val)

    # ── Spotify ─────────────────────────────────────────────────────────────
    elif cmd in ("spotify_on", "spotify_off", "spotify_toggle"):
        bg(lambda: musik.spotify_toggle(S))

    # ── Audio ────────────────────────────────────────────────────────────────
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

    # ── WiFi / BT ────────────────────────────────────────────────────────────
    elif cmd in ("wifi_on", "wifi_off", "wifi_toggle"):
        bg(lambda: wifi.wifi_toggle(S))
    elif cmd in ("bt_on", "bt_off", "bt_toggle"):
        bg(lambda: bluetooth.bt_toggle(S))
    elif cmd == "wifi_scan":
        bg(lambda: wifi.scan_networks(S, settings))
    elif cmd == "bt_scan":
        bg(lambda: bluetooth.scan_devices(S, settings))
    elif cmd.startswith("bt_connect:"):
        mac = cmd.split(":", 1)[1].strip()
        bg(lambda m=mac: bluetooth.connect_device(m, S, settings))
    elif cmd == "bt_disconnect":
        bg(lambda: bluetooth.disconnect_current(S, settings))
    elif cmd == "bt_reconnect_last":
        bg(lambda: bluetooth.reconnect_last(S, settings))
    elif cmd.startswith("bt_repair:"):
        mac = cmd.split(":", 1)[1].strip()
        bg(lambda m=mac: bluetooth.repair_device(m, S, settings))
    elif cmd.startswith("wifi_connect:"):
        ssid = cmd.split(":", 1)[1]
        bg(lambda s=ssid: wifi.connect_network(s, S, settings))

    # ── Radio Stop ───────────────────────────────────────────────────────────
    elif cmd == "radio_stop":
        webradio.stop(S); dab.stop(S); fm.stop(S)

    elif cmd == "radio_restart_on_bt":
        # Letzte Quelle mit neuem BT-Audio neu starten
        def _radio_restart():
            import time
            time.sleep(1)  # kurz warten bis BT-Sink stabil
            # Nur Radioquellen neu starten (nicht MP3/Spotify)
            _rtype    = S.get("radio_type", "")
            _last_web = settings.get("last_web_station")
            _last_dab = settings.get("last_dab_station")
            _last_fm  = settings.get("last_fm_station")
            # Nur bekannte Radio-Quellen neu starten
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

    # ── DAB Suchlauf ─────────────────────────────────────────────────────────
    elif cmd == "dab_scan":
        def _dab_scan():
            if not _scan_begin("dab"):
                info = _scan_info()
                log.warn("SCAN_BLOCKED source=dab running=" + info.get("source","?"))
                ipc.write_progress("DAB+ Suchlauf",
                    "Schon aktiv: " + info.get("source","?").upper(), color="orange")
                time.sleep(2); ipc.clear_progress(); return
            ipc.write_progress("DAB+ Suchlauf", "Scanne Band III ...", color="blue")
            log.info("SCAN_START source=dab")
            try:
                results = dab.scan_dab_channels()
                count = len(results)
                if count > 0:
                    store.save_dab(results)
                    log.info(f"SCAN_DONE source=dab count={count}")
                    ipc.write_progress("DAB+ Suchlauf",
                        f"{count} Sender gefunden", color="green")
                    time.sleep(2)
                    new_root = build_tree(store, S, settings)
                    menu_state.root = new_root
                    menu_state.clamp_cursors()
                    menu_state.rev += 1
                else:
                    log.warn("SCAN_DONE source=dab count=0 — bestehende Liste bleibt")
                    ipc.write_progress("DAB+ Suchlauf",
                        "0 Sender — Liste bleibt erhalten", color="orange")
                    time.sleep(2)
            except Exception as e:
                log.error(f"SCAN_FAIL source=dab error={e}")
                ipc.write_progress("DAB+ Fehler", str(e)[:48], color="red")
                time.sleep(3)
            finally:
                _scan_end()
                ipc.clear_progress()
        bg(_dab_scan)

    # ── FM Suchlauf ──────────────────────────────────────────────────────────
    elif cmd == "fm_scan":
        def _fm_scan():
            if not _scan_begin("fm"):
                info = _scan_info()
                log.warn("SCAN_BLOCKED source=fm running=" + info.get("source","?"))
                ipc.write_progress("FM Suchlauf",
                    "Schon aktiv: " + info.get("source","?").upper(), color="orange")
                time.sleep(2); ipc.clear_progress(); return
            ipc.write_progress("FM Suchlauf", "Scanne UKW 87.5–108.0 MHz ...", color="blue")
            log.info("SCAN_START source=fm")
            try:
                results = fm.scan_stations(S, quick_only=True)
                count = len(results)
                if count > 0:
                    store.save_fm(results)
                    log.info(f"SCAN_DONE source=fm count={count}")
                    ipc.write_progress("FM Suchlauf",
                        f"{count} Sender gefunden ✓", color="green")
                else:
                    log.warn("SCAN_DONE source=fm count=0 — bestehende Liste bleibt")
                    ipc.write_progress("FM Suchlauf",
                        "Kein Sender — Liste bleibt erhalten", color="orange")
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

    # ── Reload Stationen ─────────────────────────────────────────────────────
    elif cmd.startswith("reload_stations:"):
        _si = _scan_info()
        if _si.get("active"):
            log.warn("STATIONS_RELOAD_BLOCKED scan_running=" + _si.get("source","?"))
            ipc.write_progress("Senderliste",
                "Blockiert: Scan läuft (" + _si.get("source","?").upper() + ")",
                color="orange")
            time.sleep(2); ipc.clear_progress()
        else:
            source = cmd.split(":", 1)[1]
            store.reload_source(source)
            rebuild = True
            log.info(f"STATIONS_RELOAD source={source}")
            ipc.write_progress("Senderliste", f"{source} neu geladen", color="green")
            time.sleep(1); ipc.clear_progress()

    # ── FM Next/Prev ─────────────────────────────────────────────────────────
    elif cmd == "fm_next":
        bg(lambda: fm.play_next(S, store.fm))
    elif cmd == "fm_prev":
        bg(lambda: fm.play_prev(S, store.fm))
    elif cmd == "fm_manual":
        bg(lambda: _fm_manual(S, settings))

    # ── DAB Next/Prev ────────────────────────────────────────────────────────
    elif cmd == "dab_next":
        bg(lambda: dab.play_next(S, store.dab))
    elif cmd == "dab_prev":
        bg(lambda: dab.play_prev(S, store.dab))

    # ── Scanner Bänder ───────────────────────────────────────────────────────
    elif cmd.startswith("scan_up:"):
        band = cmd.split(":",1)[1]
        bg(lambda b=band: scanner.channel_up(b, S))
    elif cmd.startswith("scan_down:"):
        band = cmd.split(":",1)[1]
        bg(lambda b=band: scanner.channel_down(b, S))
    elif cmd.startswith("scan_next:"):
        band = cmd.split(":",1)[1]
        bg(lambda b=band: scanner.scan_next(b, S))
    elif cmd.startswith("scan_prev:"):
        band = cmd.split(":",1)[1]
        bg(lambda b=band: scanner.scan_prev(b, S))

    elif cmd.startswith("scan_jump:"):
        # scan_jump:<band>:<delta>  — Kanal-Sprung
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
        # scan_step:<band>:<delta_mhz>  — Frequenzschritt VHF/UHF
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
        # scan_setfreq:<band>:<freq_mhz>  — direkte Frequenz setzen
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
        # scan_inputfreq:<band>  — manuelle Frequenzeingabe
        parts = cmd.split(":")
        if len(parts) >= 2:
            band = parts[1]
            def _input_and_set(b=band):
                freq = scanner.freq_input_screen(b, settings)
                if freq is not None:
                    scanner.set_freq(b, freq, S, settings)
            bg(_input_and_set)

    # ── Bibliothek ───────────────────────────────────────────────────────────
    elif cmd == "lib_browse":
        bg(lambda: library.browse_and_play(S, load_settings()))

    elif cmd.startswith("fav_toggle:"):
        payload = cmd[len("fav_toggle:"):]
        # payload = source:id:name:meta_json
        try:
            import json as _j2
            parts = payload.split(":", 3)
            _src  = parts[0]
            _id   = parts[1]
            _name = parts[2]
            _meta = _j2.loads(parts[3]) if len(parts) > 3 else {}
            is_now_fav = favorites.toggle({"id": _id, "name": _name,
                                           "source": _src, "meta": _meta})
            # Auch im Senderlisten-JSON das favorite-Flag aktualisieren
            if _src == "fm":
                store.set_favorite_fm(_id, is_now_fav)
            elif _src == "dab":
                store.set_favorite_dab(_id, is_now_fav)
            elif _src == "webradio":
                store.set_favorite_web(_id, is_now_fav)
            rebuild_tree(menu_state, store, S, settings)
        except Exception as _fe:
            log.warn("fav_toggle: " + str(_fe))

    # ── System ───────────────────────────────────────────────────────────────
    elif cmd == "reboot":
        ipc.write_progress("Neustart", "In 3 Sekunden ...", color="orange")
        time.sleep(3); os.system("reboot")
    elif cmd == "shutdown":
        ipc.write_progress("Ausschalten", "In 3 Sekunden ...", color="orange")
        time.sleep(3); os.system("poweroff")
    elif cmd == "sys_info":
        bg(lambda: sys_mod.show_info(S, settings))
    elif cmd == "sys_version":
        bg(lambda: sys_mod.show_version(S))
    elif cmd == "update":
        bg(lambda: update.run_update(S))
    elif cmd == "audio_select":
        bg(lambda: audio.select_output_interactive(S, settings))

    log.trigger_received(cmd)
    if cmd in ("dab_scan","fm_scan"):
        log.info(f"SCAN_START source={cmd.split('_')[0]}")
    elif cmd.startswith("reload_stations:"):
        log.info(f"STATIONS_RELOAD source={cmd.split(':',1)[1]}")
    return rebuild


def _execute_node(node, menu_state, store, S, settings):
    """Knoten ausführen (station/action/toggle)."""
    global _LAST_NODE_EXEC_TS, _LAST_NODE_EXEC_ID
    import threading

    # Doppelte Ausführung desselben Knotens innerhalb 0.5s verhindern
    now = _time_mod.time()
    node_exec_id = f"{node.type}:{node.id}:{node.action}:{node.source}"
    if node_exec_id == _LAST_NODE_EXEC_ID and (now - _LAST_NODE_EXEC_TS) < 0.5:
        log.info(f"MENU_ACTION entprellt id={node.id} type={node.type}")
        return
    _LAST_NODE_EXEC_ID = node_exec_id
    _LAST_NODE_EXEC_TS = now

    def bg(fn): threading.Thread(target=fn, daemon=True).start()

    # Stationen zuerst prüfen — haben action=None, brauchen src/meta
    if node.type == "station":
        log.info(f"PLAY_STATION label={node.label!r} source={node.source} meta={node.meta}")
        src  = node.source
        meta = node.meta
        if src == "fm":
            # meta["name"] für reinen Sendernamen (ohne Frequenz-Suffix)
            _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                              if "  " in node.label else node.label.lstrip("★ ").strip())
            _freq = meta.get("freq","")
            bg(lambda n=_name, f=_freq: fm.play_station({"name": n, "freq": f}, S))
        elif src == "dab":
            _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                              if "  " in node.label else node.label.lstrip("★ ").strip())
            bg(lambda n=_name: dab.play_by_name(n, S))
        elif src == "webradio":
            # meta["name"] und meta["url"] korrekt weitergeben
            _name = meta.get("name", node.label.split("  ")[0].lstrip("★ ").strip()
                              if "  " in node.label else node.label.lstrip("★ ").strip())
            _url  = meta.get("url","")
            bg(lambda n=_name, u=_url: webradio.play_station({"name": n, "url": u}, S))
        return

    # action-String muss vorhanden sein (toggle/action/info)
    action = node.action
    if not action:
        return   # info-Nodes: kein action → nichts tun

    log.info(f"MENU_ACTION id={node.id} type={node.type} action={action}")

    # Toggle-Knoten
    if node.type == "toggle":
        handle_trigger(action, menu_state, store, S, settings)
        return

    # Action-Knoten
    handle_trigger(action, menu_state, store, S, settings)


def _fm_manual(S, settings):
    freq_str = fm.freq_input_screen()
    if freq_str:
        fm.play_station({"name": f"{freq_str} MHz", "freq": freq_str}, S)


def check_trigger(menu_state, store, S, settings):
    """Trigger-Datei auslesen und verarbeiten."""
    if not os.path.exists(ipc.CMD_FILE):
        return False

    # Race condition fix: wenn headless_pick läuft (list aktiv),
    # Navigation-Trigger NICHT konsumieren — headless_pick liest sie selbst
    NAV_CMDS = {"up","down","enter","back","left","right"}
    try:
        lst = ipc.read_json(ipc.LIST_FILE, {})
        if lst.get("active"):
            # Nur cmd lesen ohne zu löschen, dann prüfen ob es Navigation ist
            with open(ipc.CMD_FILE) as f:
                peek = f.read().strip()
            if peek in NAV_CMDS:
                return False  # headless_pick soll es lesen
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


# ── System-Check ──────────────────────────────────────────────────────────────

def system_check():
    import subprocess
    log.info("--- Core System-Check ---")
    VERSION = open(os.path.join(BASE_DIR, "VERSION")).read().strip()
    log.info(f"  PiDrive Core v{VERSION}")

    # Framebuffer
    for path, label in [("/dev/fb1","SPI Display"), ("/dev/fb0","HDMI Framebuffer")]:
        if os.path.exists(path):
            log.info(f"  ✓ {label}: {path}")
        else:
            log.warn(f"  ✗ {label}: {path} nicht gefunden")

    # USB-Geräte vollständig auflisten
    log.info("  USB-Geraete:")
    try:
        r = subprocess.run("lsusb 2>/dev/null", shell=True,
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Bekannte relevante Geräte hervorheben
            if any(x in line.lower() for x in ["rtl","2832","2838"]):
                log.info(f"    ✓ RTL-SDR: {line}")
            elif any(x in line.lower() for x in ["bluetooth","broadcom","cambridge"]):
                log.info(f"    ✓ BT: {line}")
            elif any(x in line.lower() for x in ["hub","root hub"]):
                pass  # Hubs nicht loggen
            else:
                log.info(f"    · {line}")
        if not r.stdout.strip():
            log.warn("    (keine USB-Geraete gefunden)")
    except Exception as _e:
        log.warn(f"  USB scan: {_e}")

    # Netzwerkstatus
    log.info("  Netzwerk:")
    try:
        r = subprocess.run(["ip","-4","addr","show"],
                           capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            if "inet " in line and "127." not in line:
                parts = line.strip().split()
                ip   = parts[1].split("/")[0]
                iface = ""
                # Find interface name
                for prev in r.stdout[:r.stdout.find(line)].splitlines():
                    if ":" in prev and not prev.startswith(" "):
                        iface = prev.split(":")[1].strip().split()[0]
                log.info(f"    ✓ {iface}: {ip}")
        ssid = subprocess.run("iwgetid -r 2>/dev/null",
                              shell=True, capture_output=True,
                              text=True, timeout=2).stdout.strip()
        if ssid:
            log.info(f"    ✓ SSID: {ssid}")
    except Exception:
        pass

    # Bluetooth
    try:
        hc = subprocess.run("hciconfig 2>/dev/null",
                            shell=True, capture_output=True,
                            text=True, timeout=3)
        if "UP RUNNING" in hc.stdout:
            log.info("  ✓ Bluetooth: UP RUNNING")
            # Gepairte Geräte
            paired = subprocess.run("bluetoothctl paired-devices 2>/dev/null",
                                    shell=True, capture_output=True,
                                    text=True, timeout=3)
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

    # PulseAudio
    try:
        pa = subprocess.run(["systemctl","is-active","pulseaudio"],
                            capture_output=True, text=True, timeout=3)
        if pa.stdout.strip() == "active":
            log.info("  ✓ PulseAudio: aktiv (BT A2DP)")
        else:
            log.warn("  ⚠ PulseAudio: nicht aktiv")
    except Exception:
        pass

    # Raspotify
    try:
        sp = subprocess.run(["systemctl","is-active","raspotify"],
                            capture_output=True, text=True, timeout=3)
        if sp.stdout.strip() == "active":
            log.info("  ✓ Raspotify: aktiv")
        else:
            log.warn("  ⚠ Raspotify: nicht aktiv")
    except Exception:
        pass

    # RTL-SDR: passiver Startup-Check via rtlsdr-Modul (öffnet Device NICHT)
    try:
        from modules import rtlsdr as _rtlsdr_check
        _rtlsdr_check.log_startup_check(log)
    except Exception as _e:
        log.warn("  ⚠ RTL-SDR Check: " + str(_e))

    log.info("--- System-Check OK ---")


# ── Menü neu bauen nach Scan/Reload ──────────────────────────────────────────

def rebuild_tree(menu_state, store, S, settings):
    """Menübaum neu aufbauen, aktuelle Position behalten."""
    old_path = menu_state.path[:]
    new_root = build_tree(store, S, settings)
    menu_state.root = new_root

    # Versuche alte Position wiederherzustellen
    menu_state._stack   = [new_root]
    menu_state._cursors = [0]
    for label in old_path[1:]:  # root überspringen
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


# ── Hauptschleife ──────────────────────────────────────────────────────────────


def startup_tasks(S, settings):
    """Einmalig beim Start: BT reconnect + letzte Station wiederherstellen."""
    import subprocess, time

    # BT Auto-reconnect: letztes Geraet zuerst, dann alle gepairten
    try:
        # Letztes bekanntes Geraet hat Prioritaet
        last_mac = settings.get("bt_last_mac", "")
        r = subprocess.run("bluetoothctl paired-devices 2>/dev/null",
                           shell=True, capture_output=True, text=True, timeout=5)
        paired = []
        for line in r.stdout.splitlines():
            p = line.strip().split(" ", 2)
            if len(p) >= 2 and p[0] == "Device":
                paired.append((p[1], p[2] if len(p)>2 else p[1]))
        # Letztes Geraet an den Anfang
        if last_mac:
            paired = sorted(paired, key=lambda x: 0 if x[0]==last_mac else 1)
        for mac, name in paired:
            subprocess.run("bluetoothctl trust " + mac + " 2>/dev/null",
                           shell=True, capture_output=True, timeout=3)
            connected = False
            # 3 Versuche: BT im Auto ist oft noch nicht ready beim Pi-Start
            for attempt, wait in enumerate([0, 5, 12]):
                if wait > 0:
                    time.sleep(wait)
                rc = subprocess.run("bluetoothctl connect " + mac + " 2>/dev/null",
                                    shell=True, capture_output=True,
                                    text=True, timeout=8)
                if "successful" in rc.stdout.lower() or "connected" in rc.stdout.lower():
                    connected = True
                    break
                log.info("BT Reconnect Versuch " + str(attempt+1) + " fehlgeschlagen: " + mac)
            if connected:
                log.info("BT Auto-reconnect OK: " + mac + " (" + name + ")")
                settings["bt_last_mac"]  = mac
                settings["bt_last_name"] = name
                from modules import bluetooth as _bt
                _bt.connect_device(mac, S, settings)
                break
    except Exception as _e:
        log.warn("BT Auto-reconnect: " + str(_e))

    # Letzte FM/DAB Station wiederherstellen
    try:
        time.sleep(1)
        last_fm  = settings.get("last_fm_station")
        last_dab = settings.get("last_dab_station")
        if last_fm and last_fm.get("freq"):
            log.info("FM: starte letzte Station: " + str(last_fm.get("name","")))
            from modules import fm as _fm
            _fm.play_station(last_fm, S, settings)
        elif last_dab and last_dab.get("name"):
            log.info("DAB: starte letzte Station: " + str(last_dab.get("name","")))
            from modules import dab as _dab
            _dab.play_station(last_dab, S, settings)
    except Exception as _e:
        log.warn("Letzte Station: " + str(_e))


def main():
    log.info("=" * 50)
    log.info("PiDrive Core v0.8.6 gestartet")
    log.info(f"  PID={os.getpid()}  UID={os.getuid()}")
    log.info("  Headless — kein Display benoetigt")
    log.info(f"  Trigger: echo 'cmd' > {ipc.CMD_FILE}")
    log.info("=" * 50)

    system_check()

    # MPRIS2: BMW-Display Metadaten
    _mpris2_player = _mpris2.start_mpris2() if _mpris2 else None

    settings = load_settings()
    S_module.start()   # Status-Thread starten (non-blocking)
    S = S_module.S

    # StationStore initialisieren
    store = StationStore(CONFIG_DIR)
    store.load_all()

    # Menübaum aufbauen
    root       = build_tree(store, S, settings)
    menu_state = MenuState(root)

    save_timer = time.time()
    stat_timer = time.time()
    ipc_timer  = time.time()
    store_timer= time.time()

    log.info("Core-Loop gestartet")
    _ready_written = False
    import threading as _thr
    _thr.Thread(target=startup_tasks, args=(S_module.S, settings),
                daemon=True).start()


    while True:
        S = S_module.S   # Direkt lesen — Thread aktualisiert im Hintergrund

        # Trigger prüfen
        needs_rebuild = check_trigger(menu_state, store, S, settings)
        if needs_rebuild:
            rebuild_tree(menu_state, store, S, settings)

        # Scan-triggered rebuild: bt_scan/wifi_scan setzen S['menu_rev']
        cur_s_rev = S.get("menu_rev", 0)
        if cur_s_rev != getattr(main, '_last_s_rev', 0):
            main._last_s_rev = cur_s_rev
            if not needs_rebuild:
                rebuild_tree(menu_state, store, S, settings)

        # Nach Trigger: IPC sofort schreiben (schnelle Reaktion im Web/Display)
        if needs_rebuild or (os.path.exists(ipc.CMD_FILE) is False and
                             menu_state.rev != getattr(main, '_last_rev', -1)):
            ipc.write_menu(menu_state.export())
            main._last_rev = menu_state.rev

        # StationStore Hot-Reload (alle 10s prüfen)
        if time.time() - store_timer > 10:
            if store.reload_if_changed():
                rebuild_tree(menu_state, store, S, settings)
            store_timer = time.time()

        # BT Disconnect: Einmalig wenn BT getrennt wird
        bt_now = S.get("bt", False)
        if getattr(main, '_bt_was_connected', False) and not bt_now:
            if settings.get("audio_output") == "bt":
                log.info("BT getrennt — Audio Fallback auf Klinke")
                settings["audio_output"] = "klinke"
                settings["alsa_device"]  = "default"
                # In Background ausführen, blockiert nicht den Loop
                def _bt_disconnect_bg():
                    try:
                        import subprocess
                        PA = "PULSE_SERVER=unix:/var/run/pulse/native"
                        sinks = subprocess.run(
                            PA + " pactl list sinks short 2>/dev/null",
                            shell=True, capture_output=True, text=True, timeout=3)
                        for line in sinks.stdout.splitlines():
                            if "alsa_output" in line:
                                alsa_sink = line.split()[1]
                                subprocess.run(
                                    PA + " pactl set-default-sink " + alsa_sink,
                                    shell=True, timeout=3)
                                log.info("[AUDIO] bt_disconnected → PA zurück auf " + alsa_sink)
                                break
                        # Radioquelle auf Klinke neu starten
                        _rtype = S.get("radio_type", "")
                        from modules.audio import is_radio_source
                        if S.get("radio_playing") and is_radio_source(_rtype):
                            log.info("[AUDIO] radio_restart_on_disconnect source=" + _rtype)
                            import time as _td
                            _td.sleep(0.5)
                            with open("/tmp/pidrive_cmd","w") as _cf:
                                _cf.write("radio_restart_on_bt\n")
                        elif _rtype:
                            log.info("[AUDIO] no restart on disconnect — source=" + _rtype)
                    except Exception as _e:
                        log.warn("BT Disconnect BG: " + str(_e))
                import threading
                threading.Thread(target=_bt_disconnect_bg, daemon=True).start()
        main._bt_was_connected = bt_now

        # IPC schreiben (alle 0.1s — Status-Thread ist non-blocking)
        if time.time() - ipc_timer > 0.1:
            ipc.write_status(S, settings)
            exported = menu_state.export()
            ipc.write_menu(exported)
            # BMW-Display aktualisieren
            if _mpris2:
                try: _mpris2.update(S, exported)
                except Exception: pass
            ipc_timer = time.time()
            if not _ready_written:
                try:
                    open(ipc.READY_FILE, "w").write("1")
                    _ready_written = True
                    log.info("IPC ready — /tmp/pidrive_ready geschrieben")
                except Exception:
                    pass

        # Status-Log (alle 60s)
        if time.time() - stat_timer > 60:
            log.status_update(S["wifi"], S["bt"], S["spotify"],
                              settings.get("audio_output", "auto"))
            stat_timer = time.time()

        time.sleep(0.03)


if __name__ == "__main__":
    main()
