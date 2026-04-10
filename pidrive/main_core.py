"""
main_core.py - PiDrive Core v0.7.0

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
from menu_model import MenuNode, MenuState, StationStore, build_tree
from modules import (musik, wifi, bluetooth, audio, system as sys_mod,
                     webradio, dab, fm, library, scanner, update)

logger = log.setup("core")

CONFIG_DIR = os.path.join(BASE_DIR, "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")


# ── Settings ──────────────────────────────────────────────────────────────────

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"music_path": os.path.expanduser("~/Musik"),
                "audio_output": "auto",
                "fm_freq": "98.5"}

def save_settings(settings):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        log.error(f"Settings speichern: {e}")


# ── Trigger-Handling ───────────────────────────────────────────────────────────

def handle_trigger(cmd, menu_state, store, S, settings):
    """Alle Trigger verarbeiten. Gibt True zurück wenn Menü neu gebaut werden soll."""
    rebuild = False

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

    # ── Radio Stop ───────────────────────────────────────────────────────────
    elif cmd == "radio_stop":
        webradio.stop(S); dab.stop(S); fm.stop(S)
    elif cmd == "library_stop":
        library.stop_playback(S)

    # ── DAB Suchlauf ─────────────────────────────────────────────────────────
    elif cmd == "dab_scan":
        def _dab_scan():
            ipc.write_progress("DAB+ Suchlauf", "Scanne Band III ...", color="blue")
            log.info("SCAN_START source=dab")
            try:
                results = dab.scan_dab_channels()
                store.save_dab(results)
                count = len(results)
                log.info(f"SCAN_DONE source=dab count={count}")
                ipc.write_progress("DAB+ Suchlauf", f"{count} Sender gefunden", color="green")
                time.sleep(2)
                # Menü sofort mit neuen Sendern neu bauen
                new_root = build_tree(store, S, settings)
                menu_state.root = new_root
                menu_state.clamp_cursors()
                menu_state.rev += 1
            except Exception as e:
                log.error(f"SCAN_FAIL source=dab error={e}")
                ipc.write_progress("DAB+ Fehler", str(e)[:48], color="red")
                time.sleep(3)
            finally:
                ipc.clear_progress()
        bg(_dab_scan)

    # ── FM Suchlauf ──────────────────────────────────────────────────────────
    elif cmd == "fm_scan":
        def _fm_scan():
            ipc.write_progress("FM Suchlauf", "Scanne UKW 87.5–108.0 MHz ...", color="blue")
            log.info("SCAN_START source=fm")
            try:
                results = fm.scan_stations(S)
                store.save_fm(results)
                count = len(results)
                log.info(f"SCAN_DONE source=fm count={count}")
                if count == 0:
                    ipc.write_progress("FM Suchlauf", "Kein Sender gefunden", color="orange")
                else:
                    ipc.write_progress("FM Suchlauf", f"{count} Sender gefunden ✓", color="green")
                time.sleep(2)
                new_root = build_tree(store, S, settings)
                menu_state.root = new_root
                menu_state.clamp_cursors()
                menu_state.rev += 1
            except Exception as e:
                log.error(f"SCAN_FAIL source=fm error={e}")
                ipc.write_progress("FM Fehler", str(e)[:48], color="red")
                time.sleep(3)
            finally:
                ipc.clear_progress()
        bg(_fm_scan)

    # ── Reload Stationen ─────────────────────────────────────────────────────
    elif cmd.startswith("reload_stations:"):
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

    # ── Bibliothek ───────────────────────────────────────────────────────────
    elif cmd == "lib_browse":
        bg(lambda: library.browse_and_play(S, load_settings()))

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
    import threading

    def bg(fn): threading.Thread(target=fn, daemon=True).start()

    action = node.action
    if not action:
        return

    log.info(f"MENU_ACTION id={node.id} type={node.type} action={action or 'play'}")

    # Stationen abspielen
    if node.type == "station":
        log.info(f"PLAY_STATION label={node.label!r} source={node.source} meta={node.meta}")
        src = node.source
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
    log.info("--- Core System-Check ---")
    VERSION = open(os.path.join(BASE_DIR, "VERSION")).read().strip()
    log.info(f"  PiDrive Core v{VERSION}")

    checks = [
        ("/dev/fb1", "SPI Display"),
        ("/dev/fb0", "HDMI Framebuffer"),
    ]
    for path, label in checks:
        if os.path.exists(path):
            log.info(f"  ✓ {label}: {path}")
        else:
            log.warn(f"  ✗ {label}: {path} nicht gefunden")

    # RTL-SDR
    import subprocess
    r = subprocess.run("lsusb 2>/dev/null | grep -i rtl", shell=True,
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        log.info("  ✓ RTL-SDR gefunden")
    else:
        log.warn("  ⚠ RTL-SDR nicht gefunden (DAB+/FM benötigt USB-Stick)")

    try:
        import subprocess
        r = subprocess.run(["ip","-4","addr","show"], capture_output=True, text=True)
        ip = [l.split()[1].split("/")[0] for l in r.stdout.splitlines() if "inet " in l and "127." not in l]
        if ip:
            log.info(f"  ✓ WLAN: {ip[0]}")
    except Exception:
        pass
    log.info("--- Core System-Check OK ---")


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

def main():
    log.info("=" * 50)
    log.info("PiDrive Core v0.7.4 gestartet")
    log.info(f"  PID={os.getpid()}  UID={os.getuid()}")
    log.info("  Headless — kein Display benoetigt")
    log.info(f"  Trigger: echo 'cmd' > {ipc.CMD_FILE}")
    log.info("=" * 50)

    system_check()

    settings = load_settings()
    S_module.refresh(force=True)
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

    while True:
        S_module.refresh()
        S = S_module.S

        # Trigger prüfen
        needs_rebuild = check_trigger(menu_state, store, S, settings)
        if needs_rebuild:
            rebuild_tree(menu_state, store, S, settings)

        # StationStore Hot-Reload (alle 10s prüfen)
        if time.time() - store_timer > 10:
            if store.reload_if_changed():
                rebuild_tree(menu_state, store, S, settings)
            store_timer = time.time()

        # IPC schreiben (jede Sekunde)
        if time.time() - ipc_timer > 1.0:
            ipc.write_status(S, settings)
            ipc.write_menu(menu_state.export())
            ipc_timer = time.time()
            if not _ready_written:
                try:
                    open(ipc.READY_FILE, "w").write("1")
                    _ready_written = True
                    log.info("IPC ready — /tmp/pidrive_ready geschrieben")
                except Exception:
                    pass

        # Status-Log (alle 30s)
        if time.time() - stat_timer > 30:
            log.status_update(S["wifi"], S["bt"], S["spotify"],
                              settings.get("audio_output", "auto"))
            stat_timer = time.time()

        time.sleep(0.05)


if __name__ == "__main__":
    main()
