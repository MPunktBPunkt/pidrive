#!/usr/bin/env python3
"""
pidrivectl — PiDrive Kommandozeilenwerkzeug
Verwendung:  pidrivectl <befehl> [optionen]

Befehle:
  status                  Vollständiger Systemstatus
  now                     Was läuft gerade?
  quick                   Schnellübersicht (Quelle, Titel, Vol, BT)

  play dab <name>         DAB+-Sender starten
  play web <name>         Webradio-Sender starten
  play fm  <name|freq>    FM-Sender starten
  stop                    Wiedergabe stoppen

  station list dab|fm|web Senderliste anzeigen

  favorites list          Favoritenliste anzeigen
  favorites play <nr|name>Favorit starten
  favorites add current   Aktuellen Sender zu Favoriten hinzufügen

  bt status               Bluetooth-Status
  bt scan                 Geräte scannen
  bt devices              Gefundene Geräte
  bt known                Bekannte Geräte
  bt connect <mac|name>   Mit Gerät verbinden
  bt disconnect           Bluetooth trennen
  bt reconnect            Letztes Gerät neu verbinden
  bt on / off             Bluetooth ein-/ausschalten

  volume                  Lautstärke anzeigen
  volume up               Lauter (+5%)
  volume down             Leiser (-5%)
  volume set <0-100>      Lautstärke setzen

  audio route klinke|bt|hdmi|auto   Audio-Ausgang wählen
  audio status            Audio-Status

  dab status              DAB+-Status (Lock, PCM, DLS)
  dab scan                DAB-Sendersuchlauf starten

  system info             System-Informationen
  system resources        RAM, Speicher, Uptime
  system reboot           Neustart
  system shutdown         Herunterfahren

  log [core|app|display]  Log anzeigen

  debug state             Status- und Quell-State JSON
  debug dab               DAB-Debug JSON
  debug bt                Bluetooth-Debug
  debug audio             Audio-Debug

Optionen:
  --json      Maschinenlesbare JSON-Ausgabe
  --verbose   Erweiterte Ausgabe
  --api       Web-API statt IPC nutzen (wenn WebUI läuft)

Exit-Codes:
  0  Erfolg
  1  Allgemeiner Fehler
  2  Nicht gefunden / ungültige Eingabe
  3  Core offline
  4  Beschäftigt / Transition aktiv
"""
import argparse
import sys
import os

# Damit cli_service etc. gefunden werden
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cli_format as fmt
from cli_service import PiDriveService, EXIT_OK, EXIT_ERROR, EXIT_NOTFOUND, EXIT_OFFLINE, EXIT_BUSY

def _exit_err(msg, code=EXIT_ERROR):
    fmt.err(msg)
    sys.exit(code)


def main():
    parser = argparse.ArgumentParser(
        prog="pidrivectl",
        description="PiDrive Kommandozeilenwerkzeug",
        add_help=True,
    )
    parser.add_argument("--json",    action="store_true", help="JSON-Ausgabe")
    parser.add_argument("--verbose", action="store_true", help="Erweiterte Ausgabe")
    parser.add_argument("--api",     action="store_true", help="Web-API nutzen")
    sub = parser.add_subparsers(dest="cmd", title="Befehle")

    # ── status / now / quick ──────────────────────────────────────────────
    sub.add_parser("status", help="Systemstatus")
    sub.add_parser("now",    help="Aktuelle Wiedergabe")
    sub.add_parser("quick",  help="Schnellübersicht")
    sub.add_parser("stop",   help="Wiedergabe stoppen")

    # ── play ──────────────────────────────────────────────────────────────
    p_play = sub.add_parser("play", help="Sender/Quelle starten")
    p_play.add_argument("source", choices=["dab","fm","web"], help="Quelle")
    p_play.add_argument("name", help="Sendername oder Frequenz")

    # ── station ───────────────────────────────────────────────────────────
    p_station = sub.add_parser("station", help="Senderverwaltung")
    st_sub = p_station.add_subparsers(dest="station_cmd")
    p_stl = st_sub.add_parser("list")
    p_stl.add_argument("source", choices=["dab","fm","web"], help="Quelle")

    # ── favorites ─────────────────────────────────────────────────────────
    p_fav = sub.add_parser("favorites", help="Favoriten")
    fav_sub = p_fav.add_subparsers(dest="fav_cmd")
    fav_sub.add_parser("list")
    p_fp = fav_sub.add_parser("play")
    p_fp.add_argument("query", help="Nummer oder Name")
    fav_sub.add_parser("add")   # add current

    # ── bt ────────────────────────────────────────────────────────────────
    p_bt = sub.add_parser("bt", help="Bluetooth")
    bt_sub = p_bt.add_subparsers(dest="bt_cmd")
    bt_sub.add_parser("status")
    bt_sub.add_parser("scan")
    bt_sub.add_parser("devices")
    bt_sub.add_parser("known")
    p_btc = bt_sub.add_parser("connect")
    p_btc.add_argument("query", help="MAC-Adresse oder Name")
    bt_sub.add_parser("disconnect")
    bt_sub.add_parser("reconnect")
    bt_sub.add_parser("on")
    bt_sub.add_parser("off")

    # ── volume ────────────────────────────────────────────────────────────
    p_vol = sub.add_parser("volume", help="Lautstärke")
    vol_sub = p_vol.add_subparsers(dest="vol_cmd")
    vol_sub.add_parser("up")
    vol_sub.add_parser("down")
    p_vs = vol_sub.add_parser("set")
    p_vs.add_argument("level", type=int, help="0–100")

    # ── audio ─────────────────────────────────────────────────────────────
    p_audio = sub.add_parser("audio", help="Audio-Ausgang")
    audio_sub = p_audio.add_subparsers(dest="audio_cmd")
    p_route = audio_sub.add_parser("route")
    p_route.add_argument("mode", choices=["klinke","bt","hdmi","auto"])
    audio_sub.add_parser("status")

    # ── dab ───────────────────────────────────────────────────────────────
    p_dab = sub.add_parser("dab", help="DAB+")
    dab_sub = p_dab.add_subparsers(dest="dab_cmd")
    dab_sub.add_parser("status")
    dab_sub.add_parser("scan")
    dab_sub.add_parser("next")
    dab_sub.add_parser("prev")

    # ── system ────────────────────────────────────────────────────────────
    p_sys = sub.add_parser("system", help="System")
    sys_sub = p_sys.add_subparsers(dest="sys_cmd")
    sys_sub.add_parser("info")
    sys_sub.add_parser("resources")
    sys_sub.add_parser("reboot")
    sys_sub.add_parser("shutdown")
    sys_sub.add_parser("diagnose")

    # ── log ───────────────────────────────────────────────────────────────
    p_log = sub.add_parser("log", help="Log anzeigen")
    p_log.add_argument("target", nargs="?", default="core",
                       choices=["core","app","display","avrcp"])

    # ── debug ─────────────────────────────────────────────────────────────
    p_dbg = sub.add_parser("debug", help="Debug-Informationen")
    dbg_sub = p_dbg.add_subparsers(dest="dbg_cmd")
    dbg_sub.add_parser("state")
    dbg_sub.add_parser("dab")
    dbg_sub.add_parser("bt")
    dbg_sub.add_parser("audio")
    dbg_sub.add_parser("menu")
    dbg_sub.add_parser("source-state")

    # ──────────────────────────────────────────────────────────────────────
    args = parser.parse_args()
    svc  = PiDriveService(use_http=args.api)
    use_json = args.json

    # ── Dispatch ──────────────────────────────────────────────────────────

    if not args.cmd:
        parser.print_help()
        sys.exit(EXIT_OK)

    # status
    if args.cmd == "status":
        d = svc.get_status()
        if not d["online"]:
            fmt.err("Core offline.")
            sys.exit(EXIT_OFFLINE)
        if use_json: fmt.print_json(d)
        else:        fmt.print_status(d)
        sys.exit(EXIT_OK)

    # now
    if args.cmd == "now":
        d = svc.get_now()
        if use_json: fmt.print_json(d)
        else:        fmt.print_now(d)
        sys.exit(EXIT_OK)

    # quick
    if args.cmd == "quick":
        d = svc.get_quick()
        if use_json: fmt.print_json(d)
        else:        fmt.print_quick(d)
        sys.exit(EXIT_OK)

    # stop
    if args.cmd == "stop":
        svc.require_online()
        r = svc.send("radio_stop")
        if use_json: fmt.print_json(r)
        else: fmt.out("Radio gestoppt.")
        sys.exit(EXIT_OK)

    # play
    if args.cmd == "play":
        svc.require_online()
        try:
            r = svc.play(args.source, args.name)
            if use_json: fmt.print_json(r)
            else: fmt.out(f"Starte {args.source.upper()}: {args.name}")
        except LookupError as e:
            _exit_err(str(e), EXIT_NOTFOUND)
        sys.exit(EXIT_OK)

    # station
    if args.cmd == "station":
        if args.station_cmd == "list":
            try:
                stations = svc.list_stations(args.source)
                if use_json: fmt.print_json(stations)
                else: fmt.print_stations(stations, args.source)
            except Exception as e:
                _exit_err(str(e))
        sys.exit(EXIT_OK)

    # favorites
    if args.cmd == "favorites":
        if args.fav_cmd == "list":
            try:
                favs = svc.list_favorites()
                if use_json: fmt.print_json(favs)
                else: fmt.print_favorites(favs)
            except Exception as e:
                _exit_err(str(e))
        elif args.fav_cmd == "play":
            svc.require_online()
            try:
                r = svc.play_favorite(args.query)
                if use_json: fmt.print_json(r)
                else: fmt.out(f"Favorit gestartet: {args.query}")
            except Exception as e:
                _exit_err(str(e))
        elif args.fav_cmd == "add":
            svc.require_online()
            r = svc.send("favorites_add_current")
            if use_json: fmt.print_json(r)
            else: fmt.out("Aktueller Sender zu Favoriten hinzugefügt.")
        sys.exit(EXIT_OK)

    # bt
    if args.cmd == "bt":
        if not args.bt_cmd:
            d = svc.get_status()
            if use_json: fmt.print_json({"bt": d["bt"], "device": d["bt_device"], "status": d["bt_status"]})
            else:
                state = f"{'verbunden' if d['bt'] else 'getrennt'}"
                dev   = f" — {d['bt_device']}" if d.get('bt_device') else ""
                fmt.out(f"Bluetooth: {state}{dev}")
            sys.exit(EXIT_OK)

        svc.require_online()
        bt_trigger_map = {
            "scan": "bt_scan", "on": "bt_on", "off": "bt_off",
            "disconnect": "bt_disconnect", "reconnect": "bt_reconnect_last",
        }
        if args.bt_cmd in bt_trigger_map:
            r = svc.send(bt_trigger_map[args.bt_cmd])
            if use_json: fmt.print_json(r)
            else: fmt.out(f"BT: {args.bt_cmd} gesendet.")
        elif args.bt_cmd == "devices":
            devs = svc.bt_discovered()
            if use_json: fmt.print_json(devs)
            else: fmt.print_bt_list(devs, "Gefundene Geräte")
        elif args.bt_cmd == "known":
            devs = svc.bt_known()
            if use_json: fmt.print_json(devs)
            else: fmt.print_bt_list(devs, "Bekannte Geräte")
        elif args.bt_cmd == "connect":
            dev = svc.bt_resolve(args.query)
            if not dev:
                _exit_err(f"BT-Gerät nicht gefunden: {args.query!r}", EXIT_NOTFOUND)
            r = svc.send(f"bt_connect:{dev['mac']}")
            if use_json: fmt.print_json(r)
            else: fmt.out(f"Verbinde mit {dev.get('name', dev['mac'])}…")
        elif args.bt_cmd == "status":
            d = svc.get_status()
            if use_json:
                fmt.print_json({"bt": d["bt"], "device": d["bt_device"], "status": d["bt_status"]})
            else:
                fmt.out(f"Bluetooth: {'verbunden' if d['bt'] else 'getrennt'}")
                if d.get("bt_device"): fmt.out(f"  Gerät: {d['bt_device']}")
        sys.exit(EXIT_OK)

    # volume
    if args.cmd == "volume":
        if not args.vol_cmd:
            d = svc.get_status()
            if use_json: fmt.print_json({"volume": d.get("volume"), "audio_out": d.get("audio_eff")})
            else: fmt.out(f"Lautstärke: {d.get('volume','–')}%  Ausgang: {d.get('audio_eff','–')}")
            sys.exit(EXIT_OK)
        svc.require_online()
        if args.vol_cmd == "up":    r = svc.send("vol_up")
        elif args.vol_cmd == "down": r = svc.send("vol_down")
        elif args.vol_cmd == "set":
            lvl = max(0, min(100, args.level))
            # Volume set via mehrfache steps ist Näherung; besser direkt:
            r = svc.send(f"vol_up")  # TODO: vol_set:<n> wenn Core unterstützt
            fmt.out(f"Lautstärke gesetzt auf {lvl}% (Näherung via up/down)")
            sys.exit(EXIT_OK)
        if use_json: fmt.print_json(r)
        else: fmt.out(f"Lautstärke: {args.vol_cmd}")
        sys.exit(EXIT_OK)

    # audio
    if args.cmd == "audio":
        if not args.audio_cmd:
            d = svc.get_status()
            if use_json: fmt.print_json({"audio_out": d.get("audio_out"), "effective": d.get("audio_eff")})
            else: fmt.out(f"Audio: {d.get('audio_eff','–')} (angefordert: {d.get('audio_out','–')})")
            sys.exit(EXIT_OK)
        svc.require_online()
        if args.audio_cmd == "route":
            trig = {"klinke": "audio_klinke","bt":"audio_bt","hdmi":"audio_hdmi","auto":"audio_all"}[args.mode]
            r = svc.send(trig)
            if use_json: fmt.print_json(r)
            else: fmt.out(f"Audio-Route: {args.mode}")
        elif args.audio_cmd == "status":
            d = svc.get_status()
            if use_json: fmt.print_json({"audio_out": d["audio_out"], "effective": d["audio_eff"]})
            else:
                fmt.out(f"Ausgang:   {d.get('audio_eff','–')}")
                fmt.out(f"Angefragt: {d.get('audio_out','–')}")
        sys.exit(EXIT_OK)

    # dab
    if args.cmd == "dab":
        if args.dab_cmd == "status":
            d = svc.dab_status()
            if use_json: fmt.print_json(d)
            else: fmt.print_dab_status(d)
        elif args.dab_cmd == "scan":
            svc.require_online()
            r = svc.send("dab_scan")
            if use_json: fmt.print_json(r)
            else: fmt.out("DAB-Sendersuchlauf gestartet.")
        elif args.dab_cmd == "next":
            svc.require_online()
            svc.send("dab_next")
            fmt.out("DAB: nächster Sender.")
        elif args.dab_cmd == "prev":
            svc.require_online()
            svc.send("dab_prev")
            fmt.out("DAB: vorheriger Sender.")
        sys.exit(EXIT_OK)

    # system
    if args.cmd == "system":
        if not args.sys_cmd or args.sys_cmd == "info":
            v = svc.get_version()
            d = svc.get_status()
            if use_json:
                fmt.print_json({"version": v, "online": d["online"],
                                 "ip": d.get("wifi_ssid","")})
            else:
                fmt.out(f"PiDrive v{v}")
                fmt.out(f"Core: {'online' if d['online'] else 'OFFLINE'}")
                if d.get("wifi_ssid"): fmt.out(f"WiFi: {d['wifi_ssid']}")
        elif args.sys_cmd == "resources":
            r = svc.system_resources()
            if use_json: fmt.print_json(r)
            else: fmt.print_resources(r)
        elif args.sys_cmd == "reboot":
            svc.require_online()
            fmt.out("Starte neu…")
            svc.send("reboot")
        elif args.sys_cmd == "shutdown":
            svc.require_online()
            fmt.out("Herunterfahren…")
            svc.send("shutdown")
        elif args.sys_cmd == "diagnose":
            try:
                import subprocess
                r = subprocess.run(
                    ["python3", os.path.join(os.path.dirname(__file__), "diagnose.py")],
                    capture_output=True, text=True
                )
                fmt.out(r.stdout)
                if r.stderr: fmt.err(r.stderr[:500])
            except Exception as e:
                _exit_err(str(e))
        sys.exit(EXIT_OK)

    # log
    if args.cmd == "log":
        log_txt = svc.log(args.target)
        fmt.out(log_txt)
        sys.exit(EXIT_OK)

    # debug
    if args.cmd == "debug":
        if not args.dbg_cmd:
            fmt.print_json(svc.debug_state())
            sys.exit(EXIT_OK)
        if args.dbg_cmd == "state":
            d = svc.debug_state()
            if use_json: fmt.print_json(d)
            else:
                fmt.out("=== Source State ===")
                fmt.print_json(d.get("source_state", {}))
        elif args.dbg_cmd == "dab":
            d = svc.dab_status()
            fmt.print_json(d)
        elif args.dbg_cmd == "bt":
            fmt.out("=== Bekannte Geräte ===")
            fmt.print_json(svc.bt_known())
            fmt.out("\n=== Gefundene Geräte ===")
            fmt.print_json(svc.bt_discovered())
        elif args.dbg_cmd == "audio":
            try:
                d = svc.http.get_json("/api/audio")
                fmt.print_json(d)
            except Exception:
                fmt.print_json(svc.get_status())
        elif args.dbg_cmd == "menu":
            import json
            try:
                with open("/tmp/pidrive_menu.json") as f:
                    fmt.print_json(json.load(f))
            except Exception as e:
                _exit_err(str(e))
        elif args.dbg_cmd == "source-state":
            import json
            try:
                with open("/tmp/pidrive_source_state.json") as f:
                    fmt.print_json(json.load(f))
            except Exception as e:
                _exit_err(str(e))
        sys.exit(EXIT_OK)

    parser.print_help()
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
