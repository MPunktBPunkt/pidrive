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
# cli/ ist ein Unterpaket von pidrive/ — kein sys.path-Hack nötig
# sys.path.insert wird nur noch für Root-Fallback benutzt
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from cli import format as fmt
from cli.service import PiDriveService, EXIT_OK, EXIT_ERROR, EXIT_NOTFOUND, EXIT_OFFLINE, EXIT_BUSY

def _exit_err(msg, code=EXIT_ERROR):
    fmt.err(msg)
    sys.exit(code)


def _run_debug_mpris(args, fmt, use_json):
    """MPRIS2 D-Bus Diagnose und Test-Metadaten-Push."""
    import subprocess as _sp, json as _j, os as _os

    action = getattr(args, 'mpris_action', 'status')

    fmt.out("\n=== MPRIS2 D-Bus Status ===")
    r = _sp.run(["dbus-send","--system","--print-reply",
                  "--dest=org.freedesktop.DBus","/",
                  "org.freedesktop.DBus.ListNames"],
                 capture_output=True, text=True)
    registered = "org.mpris.MediaPlayer2.pidrive" in r.stdout
    fmt.out("  " + ("✓ REGISTRIERT" if registered else "✗ NICHT REGISTRIERT") +
            "  org.mpris.MediaPlayer2.pidrive")

    pw = _sp.run(["pgrep","-a","pipewire-pulse"], capture_output=True, text=True)
    if pw.stdout.strip():
        fmt.out("  ⚠ pipewire-pulse läuft — D-Bus Konflikt möglich!")
    else:
        fmt.out("  ✓ Kein pipewire-pulse")

    fmt.out("\n=== BlueZ AVRCP Player ===")
    r2 = _sp.run(["bluetoothctl","show"], capture_output=True, text=True)
    r3 = _sp.run(["dbus-send","--system","--print-reply",
                   "--dest=org.bluez","/",
                   "org.freedesktop.DBus.ObjectManager.GetManagedObjects"],
                  capture_output=True, text=True)
    if "MediaPlayer1" in r3.stdout:
        fmt.out("  ✓ BlueZ MediaPlayer1 vorhanden")
    else:
        fmt.out("  ✗ Kein BlueZ MediaPlayer1 (BT verbunden?)")

    fmt.out("\n=== Pi IP-Adresse ===")
    try:
        import subprocess as _sp3
        r_ip = _sp3.run(["ip", "-4", "addr", "show", "wlan0"],
                        capture_output=True, text=True, timeout=2)
        for _ln in r_ip.stdout.splitlines():
            if _ln.strip().startswith("inet "):
                _ip = _ln.strip().split()[1].split("/")[0]
                fmt.out(f"  wlan0: {_ip}")
                fmt.out(f"  SSH:   ssh pidrive@{_ip}")
                fmt.out(f"  WebUI: http://{_ip}:8080")
                break
        else:
            fmt.out("  wlan0: nicht verbunden")
    except Exception:
        fmt.out("  IP nicht ermittelbar")

    fmt.out("\n=== Core-Status Metadaten ===")
    try:
        s = _j.loads(open("/tmp/pidrive_status.json").read())
        fmt.out(f"  Quelle:  {s.get('source','?')}")
        fmt.out(f"  Titel:   {s.get('track') or s.get('radio_name','–')}")
        fmt.out(f"  Artist:  {s.get('artist','–')}")
    except Exception as e:
        fmt.out(f"  Status nicht lesbar: {e}")

    if action == "push":
        title  = getattr(args, 'title', 'Testradio')
        artist = getattr(args, 'artist', 'PiDrive Test')
        album  = getattr(args, 'album', 'Debug')
        fmt.out(f"\n=== Test-Push: '{title}' / '{artist}' ===")
        try:
            with open("/tmp/pidrive_cmd", "a") as _f2:
                _f2.write(f"mpris_push:{title}|{artist}|{album}\n")
            fmt.out("  ✓ Trigger gesendet (mpris_push:...)")
            fmt.out("  → dbus-send --system --print-reply \\")
            fmt.out("      --dest=org.mpris.MediaPlayer2.pidrive \\")
            fmt.out("      /org/mpris/MediaPlayer2 \\")
            fmt.out("      org.freedesktop.DBus.Properties.GetAll \\")
            fmt.out("      string:org.mpris.MediaPlayer2.Player 2>&1 | grep -A2 Title")
        except Exception as e:
            fmt.out(f"  ✗ Fehler: {e}")


def main():
    parser = argparse.ArgumentParser(
        prog="pidrivectl",
        description="PiDrive Kommandozeilenwerkzeug",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Beispiele:
  pidrivectl status              Systemstatus (Quelle, Titel, Vol, BT, WiFi)
  pidrivectl now                 Was laeuft gerade?
  pidrivectl quick               Kompakte Einzeilen-Uebersicht

  pidrivectl play dab "ROCK FM"  DAB+-Sender starten (Name oder Nummer)
  pidrivectl play dab 27         DAB+-Sender #27 aus der Liste
  pidrivectl play web "Bayern 1" Webradio starten
  pidrivectl play spotify        Spotify Connect aktivieren
  pidrivectl stop                Wiedergabe stoppen

  pidrivectl station list dab    DAB-Senderliste (★ = Favorit)
  pidrivectl station list fm     FM-Senderliste
  pidrivectl station list web    Webradio-Liste
  pidrivectl favorites list      Favoritenliste (alle Quellen)
  pidrivectl favorites add       Aktuellen Sender zu Favoriten

  pidrivectl bt scan             Bluetooth-Scan (live, 22s)
  pidrivectl bt pair <mac>       Gerät pairen (vorher in Pairing-Modus!)
  pidrivectl bt connect <mac>    Mit gepaairtem Gerät verbinden
  pidrivectl bt known            Bekannte Geräte (gepairt/gesehen)

  pidrivectl volume up           Lauter (zeigt neue %)
  pidrivectl volume down         Leiser
  pidrivectl volume 70           Direkt auf 70%% setzen
  pidrivectl volume set 70       Lautstaerke direkt setzen

  pidrivectl audio route klinke  Audio-Ausgang: klinke | bt | hdmi
  pidrivectl audio status        Aktuellen Ausgang anzeigen

  pidrivectl dab status          DAB+ Empfangsstatus (Lock, PCM, Fehler)
  pidrivectl dab scan            DAB+ Sendersuchlauf starten

  pidrivectl ppm                 Aktuellen PPM-Offset anzeigen
  pidrivectl ppm set 49          PPM-Offset setzen (RTL-SDR Kalibrierung)
  pidrivectl ppm calibrate       Automatische PPM-Kalibrierung

  pidrivectl system              System-Info + Spotify-Status
  pidrivectl system resources    RAM, Speicher, Uptime, Throttling
  pidrivectl system diagnose     Vollstaendige Systemdiagnose

  pidrivectl log                 Core-Log (letzte 40 Eintraege)
  pidrivectl log display         Display-Log
  pidrivectl log avrcp           AVRCP/BMW-Log

  pidrivectl version             Version anzeigen
  pidrivectl debug               Status/Source/Menu als JSON

  pidrivectl avrcp               Live-Monitor BMW iDrive AVRCP Tasten
  pidrivectl avrcp status        Letztes AVRCP-Event
  pidrivectl avrcp events        AVRCP Ringbuffer (letzte 20)
  pidrivectl avrcp inject next   Trigger simulieren (Testen ohne BMW)

Flags (vor dem Befehl angeben):
  --json     Maschinenlesbare Ausgabe fuer Scripting
  --api      Web-API statt IPC nutzen (wenn WebUI laeuft)
""",
        add_help=True,
    )
    parser.add_argument("--json",    action="store_true", help="JSON-Ausgabe")
    parser.add_argument("--verbose", action="store_true", help="Erweiterte Ausgabe")
    parser.add_argument("--api",     action="store_true", help="Web-API nutzen")
    sub = parser.add_subparsers(dest="cmd", title="Befehle")

    # ── status / now / quick ──────────────────────────────────────────────
    sub.add_parser("status", help="Quelle, Titel, Vol, BT, WiFi")
    sub.add_parser("now",    help="Was laeuft gerade? (Titel + DLS)")
    sub.add_parser("quick",  help="Kompakte Einzeile: Quelle, Titel, Vol, BT")
    sub.add_parser("version", help="Version anzeigen")
    sub.add_parser("stop",   help="Radio + Spotify stoppen")

    # ── play ──────────────────────────────────────────────────────────────
    p_play = sub.add_parser("play", help="Sender/Quelle starten")
    p_play.add_argument("source", choices=["dab","fm","web","spotify","local"], help="Quelle")
    p_play.add_argument("name", nargs="?", default=None,
                        help="Sendername, Frequenz oder Pfad (local)")
    p_play.add_argument("--shuffle", action="store_true")
    p_play.add_argument("path", nargs="*", default=[])

    # ── station ───────────────────────────────────────────────────────────
    p_station = sub.add_parser("station", help="Senderverwaltung")
    st_sub = p_station.add_subparsers(dest="station_cmd")
    p_stl = st_sub.add_parser("list")
    p_stl.add_argument("source", choices=["dab","fm","web","local"], help="Quelle")

    # ── favorites ─────────────────────────────────────────────────────────
    p_fav = sub.add_parser("favorites", help="Favoriten")
    fav_sub = p_fav.add_subparsers(dest="fav_cmd")
    fav_sub.add_parser("list")
    p_fp = fav_sub.add_parser("play")
    p_fp.add_argument("query", help="Nummer oder Name")
    p_fa = fav_sub.add_parser("add", help="Sender zu Favoriten hinzufuegen")
    p_fr = fav_sub.add_parser("remove", help="Favorit entfernen")
    p_fr.add_argument("name", help="Name oder Nummer")
    p_fa.add_argument("name", nargs="?", default=None,
                      help="Sendername (leer = aktueller Sender)")

    # ── bt ────────────────────────────────────────────────────────────────
    p_bt = sub.add_parser("bt", help="Bluetooth")
    bt_sub = p_bt.add_subparsers(dest="bt_cmd")
    bt_sub.add_parser("status")
    bt_sub.add_parser("scan")
    bt_sub.add_parser("devices")
    bt_sub.add_parser("known")
    p_btc = bt_sub.add_parser("connect")
    p_btc.add_argument("query", help="MAC-Adresse oder Name")
    p_btp = bt_sub.add_parser("pair", help="Pairen + verbinden (Gerät muss im Pairing-Modus sein)")
    p_btp.add_argument("query", help="MAC-Adresse oder Name")
    bt_sub.add_parser("disconnect")
    bt_sub.add_parser("reconnect")
    bt_sub.add_parser("on")
    bt_sub.add_parser("off")

    # ── volume ────────────────────────────────────────────────────────────
    p_vol = sub.add_parser("volume", help="Lautstärke")
    # vol_arg wird per sys.argv pre-processing gehandhabt (Konflikt mit subparsers)
    vol_sub = p_vol.add_subparsers(dest="vol_cmd")
    vol_sub.add_parser("up")
    vol_sub.add_parser("down")
    p_vs = vol_sub.add_parser("set")
    p_vs.add_argument("level", type=int, help="0-100")

    # ── ppm ───────────────────────────────────────────────────────────────
    p_ppm = sub.add_parser("ppm", help="PPM-Offset fuer RTL-SDR (DAB/FM Kalibrierung)")
    ppm_sub = p_ppm.add_subparsers(dest="ppm_cmd")
    ppm_sub.add_parser("status", help="Aktuellen PPM-Wert anzeigen")
    p_ppm_set = ppm_sub.add_parser("set", help="PPM-Offset setzen")
    p_ppm_set.add_argument("value", type=int, help="PPM-Wert (typ. 40-55)")
    ppm_sub.add_parser("calibrate", help="Automatische Kalibrierung starten")

    # ── audio ─────────────────────────────────────────────────────────────
    p_audio = sub.add_parser("audio", help="Audio-Ausgang")
    audio_sub = p_audio.add_subparsers(dest="audio_cmd")
    p_route = audio_sub.add_parser("route")
    p_route.add_argument("mode", choices=["klinke","bt","hdmi","auto"])
    audio_sub.add_parser("status")
    audio_sub.add_parser("test", help="Testton abspielen (3s)")

    # ── dab ───────────────────────────────────────────────────────────────
    p_dab = sub.add_parser("dab", help="DAB+")
    dab_sub = p_dab.add_subparsers(dest="dab_cmd")
    dab_sub.add_parser("status")
    dab_sub.add_parser("scan")
    dab_sub.add_parser("next")
    dab_sub.add_parser("prev")
    dab_sub.add_parser("stop")   # Alias fuer radio_stop

    p_dab_live = dab_sub.add_parser("live", help="Live-Monitor")
    p_dab_live.add_argument("--once", action="store_true")
    p_dab_live.add_argument("--changes", action="store_true")
    p_dab_live.add_argument("--interval", type=float, default=1.0)

    # ── scanner ──────────────────────────────────────────────────────────
    p_scanner = sub.add_parser("scanner", help="RTL-SDR Funk-Scanner")
    sc_sub = p_scanner.add_subparsers(dest="sc_cmd")
    # scanner ohne Subcommand → Status
    p_sc_band = sc_sub.add_parser("band", help="Band-Kommando (intern)")
    # scanner BAND scan|ch|freq|next|prev
    for _scb in ["pmr446","freenet","lpd433","vhf","uhf","cb","fm"]:
        _p = sc_sub.add_parser(_scb)
        _sc_sub2 = _p.add_subparsers(dest="sc_action")
        _sc_sub2.add_parser("scan")
        _sc_sub2.add_parser("stop")
        _sc_sub2.add_parser("next")
        _sc_sub2.add_parser("prev")
        _p_ch  = _sc_sub2.add_parser("ch");   _p_ch.add_argument("n",  type=int)
        _p_fr  = _sc_sub2.add_parser("freq"); _p_fr.add_argument("f",  type=float)
    _p_sq = sc_sub.add_parser("squelch"); _p_sq.add_argument("level", type=int)
    _p_pp = sc_sub.add_parser("ppm");     _p_pp.add_argument("value", type=int)
    _p_st = sc_sub.add_parser("stop")

    # ── system ────────────────────────────────────────────────────────────
    p_sys = sub.add_parser("system", help="System")
    sys_sub = p_sys.add_subparsers(dest="sys_cmd")
    sys_sub.add_parser("info")
    sys_sub.add_parser("resources")
    sys_sub.add_parser("reboot")
    sys_sub.add_parser("shutdown")
    sys_sub.add_parser("diagnose")

    # ── log ───────────────────────────────────────────────────────────────
    p_playlist = sub.add_parser("playlist", help="Wiedergabe-History")
    p_playlist.add_argument("date", nargs="?", default="today")
    p_log = sub.add_parser("log", help="Log anzeigen")
    p_log.add_argument("target", nargs="?", default="core",
                       choices=["core","app","display","avrcp"])

    # ── debug ─────────────────────────────────────────────────────────────
    # ── test ──────────────────────────────────────────────────────────────────
    p_test = sub.add_parser("test", help="System-Test (alle Quellen + Audio + BT)")
    p_test.add_argument("test_cmd", nargs="?", default="all",
                        choices=["all", "system", "audio", "bt", "mpris",
                                 "webradio", "fm", "scanner", "dab", "dabscan",
                                 "spotify", "avrcp", "log"],
                        help="all=kompletter Test, oder einzelner Block")

    p_dbg = sub.add_parser("debug", help="Debug-Informationen + Trigger-Inject")

    # ── avrcp ───────────────────────────────────────────────────────────────
    p_avrcp = sub.add_parser("avrcp", help="AVRCP-Monitor (BMW iDrive Tasten)")
    p_avrcp.add_argument("avrcp_cmd", nargs="?", default="monitor",
                         choices=["monitor","status","events","inject"],
                         help="monitor|status|events|inject")
    p_avrcp.add_argument("avrcp_arg", nargs="?", default=None,
                         help="Trigger fuer inject (z.B. next, prev, play)")

    dbg_sub = p_dbg.add_subparsers(dest="dbg_cmd")
    dbg_sub.add_parser("state")
    dbg_sub.add_parser("dab")
    dbg_sub.add_parser("avrcp", help="Letzte AVRCP-Events (Ringbuffer)")
    p_mpris = dbg_sub.add_parser("mpris", help="MPRIS2 D-Bus Diagnose + Test-Push")
    p_mpris.add_argument("mpris_action", nargs="?", default="status",
                         choices=["status","push"],
                         help="status=D-Bus-Check, push=Test-Metadaten senden")
    p_mpris.add_argument("--title", default="Testradio")
    p_mpris.add_argument("--artist", default="PiDrive Test")
    p_mpris.add_argument("--album", default="Debug")
    p_inject = dbg_sub.add_parser("inject", help="Trigger direkt injizieren")
    p_inject.add_argument("trigger", help="z.B. nav_down, enter, back, vol_up")
    dbg_sub.add_parser("bt")
    dbg_sub.add_parser("audio")
    dbg_sub.add_parser("menu")
    dbg_sub.add_parser("source-state")

    # ──────────────────────────────────────────────────────────────────────
    # Normalize: "volume 50" → "volume set 50", "volume set 50" unverändert
    if len(sys.argv) >= 3 and sys.argv[1] == "volume":
        # "volume set N" → vol_arg würde "set" schlucken → fix: remove vol_arg ambiguity
        if sys.argv[2] == "set" and len(sys.argv) >= 4 and sys.argv[3].isdigit():
            pass  # OK: subparser bekommt "set", level="95" korrekt wenn vol_arg entfernt
        elif sys.argv[2].isdigit():
            sys.argv.insert(2, "set")  # "volume 50" → "volume set 50"
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
    if args.cmd == "version":
        import os as _ov
        _vv = "?"
        # cli/ liegt EINE EBENE tiefer als VERSION → parent dir
        _real = _ov.path.realpath(__file__)       # /…/pidrive/cli/cli.py
        _cli_dir = _ov.path.dirname(_real)        # /…/pidrive/cli/
        _pidrive_dir = _ov.path.dirname(_cli_dir) # /…/pidrive/
        for _vf in [
            _ov.path.join(_pidrive_dir, "VERSION"),
            _ov.path.join(_cli_dir, "VERSION"),
            "/home/pidrive/pidrive/pidrive/VERSION",
            "/opt/pidrive/pidrive/VERSION",
        ]:
            try:
                _vv = open(_vf).read().strip()
                if _vv: break
            except Exception: pass
        fmt.out(f"PiDrive v{_vv}")
        sys.exit(EXIT_OK)

    if args.cmd == "quick":
        d = svc.get_quick()
        if use_json: fmt.print_json(d)
        else:        fmt.print_quick(d)
        sys.exit(EXIT_OK)

    # stop
    if args.cmd == "stop":
        svc.require_online()
        svc.send("radio_stop")
        svc.send("spotify_off")
        if use_json: fmt.print_json({"ok": True})
        else: fmt.out("Gestoppt.")
        sys.exit(EXIT_OK)

    # play
    if args.cmd == "play":
        svc.require_online()

        # Spotify: kein Name noetig, einfach toggle/on
        if args.source == "spotify":
            r = svc.send("spotify_on")
            if use_json: fmt.print_json(r)
            else: fmt.out("Spotify Connect aktiviert — Sender aus Spotify-App waehlen")
            sys.exit(EXIT_OK)

        # Lokale Datei / Ordner / M3U Playlist
        if args.source == "local":
            _parts = ([args.name] if args.name else []) + list(getattr(args, "path", []))
            if not _parts:
                # Kein Pfad → music_dir aus settings verwenden
                import os as _osP, sys as _sysP
                _pd = _osP.path.dirname(_osP.path.dirname(_osP.path.realpath(__file__)))
                if _pd not in _sysP.path: _sysP.path.insert(0, _pd)
                try:
                    from settings import load_settings as _llsp
                    _path = _llsp().get("music_dir") or "/home/pidrive/Musik"
                except Exception:
                    _path = "/home/pidrive/Musik"
                fmt.out(f"  Musikordner: {_path}")
            else:
                _path = " ".join(_parts)
            _shuf = "|shuffle" if getattr(args, "shuffle", False) else ""
            svc.require_online()
            svc.send(f"local_play:{_path}{_shuf}")
            import time as _lt; _lt.sleep(0.8)
            _d = svc.get_status()
            fmt.out(f"  \u2713 Lokal: {_path}" if _d.get("radio_type")=="LOCAL"
                    else f"  Gestartet: {_path}")
            sys.exit(EXIT_OK)

        name = args.name
        if not name:
            _exit_err(f"Name/Sender fuer {args.source} erforderlich", EXIT_ERROR)

        # Nummer aus Senderliste akzeptieren (z.B. pidrivectl play dab 27)
        if name.isdigit():
            try:
                stations = svc.list_stations(args.source)
                idx = int(name) - 1
                if 0 <= idx < len(stations):
                    name = stations[idx].get("name", name)
                    if not use_json:
                        fmt.out(f"  #{args.name} → {name}")
                else:
                    _exit_err(f"Nummer {name} ungültig (1-{len(stations)})", EXIT_NOTFOUND)
            except Exception as e:
                _exit_err(str(e))

        # DAB: live Feedback während Lock-Phase
        if args.source == "dab" and not use_json:
            fmt.out(f"Starte DAB: {name}")
            fmt.out(f"{fmt.DIM}  (warte auf Lock — bis 30s){fmt.RESET}")
            STATE_ICONS = {
                "starting":     "⏳", "partial_sync": "📡",
                "locked":       "🔒", "pcm_only":     "🔊",
                "no_lock":      "⚠ ", "timeout":      "✗ "
            }
            log_lines = []
            def _on_status(d):
                icon = STATE_ICONS.get(d["state"], "")
                line = f"  {icon} [{d['elapsed']:2d}s] {d['state']}"
                if d.get("sync_ok"): line += " • sync ✓"
                if d.get("pcm"):     line += " • PCM ✓"
                if d.get("last_error"): line += f" • {d['last_error'][:40]}"
                fmt.out(line)
            def _on_log(line):
                # Nur relevante welle-cli Zeilen
                low = line.lower()
                if any(k in low for k in ["sync", "pcm", "dls", "lock", "error", "superframe"]):
                    if len(log_lines) < 8:  # max 8 Logzeilen
                        log_lines.append(line)
                        fmt.out("  " + fmt.DIM + "  " + line[:80] + fmt.RESET)
            result = svc.watch_dab_play(name, timeout=30,
                                         on_status=_on_status, on_log_line=_on_log)
            icon = STATE_ICONS.get(result, "?")
            if result == "locked":
                fmt.out("")
                fmt.out(icon + " Lock — DAB laeuft stabil")
            elif result == "partial_sync":
                fmt.out("")
                fmt.out(icon + " Partieller Lock — laeuft (schwacher Empfang, Audio aktiv)")
                fmt.out("  Tipp: Im Auto mit Antenne deutlich besser")
            elif result == "no_lock":
                fmt.out("")
                fmt.out(icon + " Kein Lock — Signal zu schwach")
                fmt.out("  Tipp: pidrivectl dab status fuer aktuellen Empfangszustand")
            elif result == "timeout":
                d = svc.get_status()
                last = d.get("dab_play_state", d.get("dab_playback_state", "?"))
                fmt.out("")
                fmt.out("Timeout — letzter Zustand: " + last)
            else:
                d = svc.get_status()
                fmt.out(icon + " Status: " + d.get("dab_playback_state", "?"))
        else:
            try:
                r = svc.play(args.source, name)
                if use_json: fmt.print_json(r)
                else: fmt.out(f"Starte {args.source.upper()}: {name}")
            except LookupError as e:
                _exit_err(str(e), EXIT_NOTFOUND)
        sys.exit(EXIT_OK)

    # station
    if args.cmd == "station":
        if args.station_cmd == "list":
            if (args.source or "").lower() == "local":
                import glob as _gl, os as _osL, sys as _sys3
                _pidrive_dir = _osL.path.dirname(_osL.path.dirname(_osL.path.realpath(__file__)))
                if _pidrive_dir not in _sys3.path: _sys3.path.insert(0, _pidrive_dir)
                # Kanonischer Musikpfad aus settings
                _mdir = "/home/pidrive/Musik"
                try:
                    from settings import load_settings as _lls
                    _mdir = _lls().get("music_dir") or _mdir
                except Exception: pass
                _ext = {".mp3",".flac",".ogg",".m4a",".aac",".wav",".opus"}

                def _count_audio_files(d):
                    return sorted([f for f in _gl.glob(_osL.path.join(d,"**","*.*"),recursive=True)
                                   if _osL.path.splitext(f)[1].lower() in _ext])

                # Musikordner anzeigen
                _fs = _count_audio_files(_mdir)
                fmt.out(f"\n  Musikordner: {_mdir}  ({len(_fs)} Dateien)")
                for _n,_f in enumerate(_fs[:30],1): fmt.out(f"    {_n:3}. {_osL.path.basename(_f)}")
                if len(_fs)>30: fmt.out(f"    ... +{len(_fs)-30} weitere")

                # USB-Sticks suchen
                try:
                    from modules.usb_music import find_usb_sticks as _fus
                    _usbs = _fus()
                except Exception: _usbs = []

                if _usbs:
                    fmt.out(f"\n  USB-Sticks: {len(_usbs)} gefunden")
                    for _u in _usbs:
                        fmt.out(f"\n  USB: {_u['name']}  →  {_u['path']}  ({_u['files']} Dateien)")
                        _ufs = _count_audio_files(_u['path'])
                        for _n,_f in enumerate(_ufs[:20],1): fmt.out(f"    {_n:3}. {_osL.path.basename(_f)}")
                        if len(_ufs)>20: fmt.out(f"    ... +{len(_ufs)-20} weitere")
                else:
                    fmt.out("\n  USB-Sticks: keiner gefunden")
                    fmt.out("    (USB-Stick einstecken → erscheint automatisch)")
                sys.exit(EXIT_OK)
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
            if hasattr(args, "name") and args.name:
                r = svc.send("favorites_add:" + args.name)
                if use_json: fmt.print_json(r)
                else: fmt.out("Favorit hinzugefuegt: " + args.name)
            else:
                r = svc.send("favorites_add_current")
                if use_json: fmt.print_json(r)
                else: fmt.out("Aktueller Sender zu Favoriten hinzugefuegt.")
        elif args.fav_cmd == "remove":
            import json as _jf, os as _of
            _cfg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "favorites.json")
            try:
                with open(_cfg) as _ff: _fd = _jf.load(_ff)
            except Exception: _fd = {"version":1,"favorites":[]}
            _fl = _fd.get("favorites", [])
            _n = args.name
            if _n.isdigit():
                _i = int(_n) - 1
                if 0 <= _i < len(_fl): _rm = _fl.pop(_i)
                else: _exit_err("Nummer " + _n + " nicht gefunden", EXIT_NOTFOUND)
            else:
                _new = [x for x in _fl if x.get("name","").lower() != _n.lower()]
                if len(_new) == len(_fl): _exit_err("Nicht gefunden: " + _n, EXIT_NOTFOUND)
                _rm = {"name": _n}; _fl = _new
            _fd["favorites"] = _fl
            try:
                with open(_cfg,"w") as _ff: _jf.dump(_fd, _ff, indent=2)
            except Exception as _e: _exit_err(str(_e), EXIT_ERROR)
            if use_json: fmt.print_json({"ok":True,"removed":_rm.get("name","?")})
            else: fmt.out("Favorit entfernt: " + _rm.get("name","?"))
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
            "on": "bt_on", "off": "bt_off",
            "disconnect": "bt_disconnect", "reconnect": "bt_reconnect_last",
        }
        if args.bt_cmd == "scan":
            # LXC-Hinweis wenn BT-Socket gesperrt
            try:
                from modules.platform import CAPS as _C, bt_socket_restricted as _bsr
                if _bsr():
                    fmt.out(fmt.YELLOW + "  ⚠  BT-Adapter sichtbar aber AF_BLUETOOTH Socket gesperrt (LXC)" + fmt.RESET)
                    fmt.out("     Proxmox LXC fuer BT freischalten:")
                    fmt.out("     lxc.cgroup2.devices.allow: c 166:0 rwm")
                    fmt.out("     lxc.mount.entry: /dev/bluetooth dev/bluetooth none bind,create=dir")
            except Exception: pass
            if use_json:
                r = svc.send("bt_scan")
                fmt.print_json(r)
            else:
                fmt.out("BT-Scan gestartet (22s)…")
                found = []
                seen = set()
                def _new_dev(d):
                    mac  = d.get("mac","?")
                    name = d.get("name","") or mac
                    ble  = " (BLE)" if d.get("ble_random_mac") else ""
                    fmt.out(f"  + {name:<26} {fmt.DIM}{mac}{ble}{fmt.RESET}")
                def _tick(elapsed, total):
                    bar = "█" * (elapsed * 20 // total) + "░" * (20 - elapsed * 20 // total)
                    print(f"  [{bar}] {elapsed}/{total}s", end="\r", flush=True)
                found = svc.watch_bt_scan(scan_seconds=22,
                                           on_device=_new_dev, on_tick=_tick)
                print()  # Zeilenumbruch nach Fortschrittsbalken
                if found:
                    fmt.out(f"\n✓ {len(found)} Gerät(e) gefunden.")
                else:
                    fmt.out("\n  Keine Geräte gefunden.")
        elif args.bt_cmd in bt_trigger_map:
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
                _exit_err("BT-Geraet nicht gefunden: " + repr(args.query), EXIT_NOTFOUND)
            mac  = dev["mac"]
            name = dev.get("name") or mac
            if not dev.get("paired"):
                fmt.out(fmt.YELLOW + "  Hinweis: Nicht gepairt — zuerst 'pidrivectl bt pair " + mac + "'" + fmt.RESET)
                sys.exit(EXIT_ERROR)
            if use_json:
                r = svc.send("bt_connect:" + mac)
                fmt.print_json(r)
            else:
                fmt.out("Verbinde mit " + name + " (" + mac + ")…")
                STATE = {"connected": "✓ Verbunden", "failed": "✗ Fehlgeschlagen", "timeout": "✗ Timeout"}
                def _on_bt(d):
                    fmt.out("  [" + str(d["elapsed"]).rjust(2) + "s] " + d["state"])
                result = svc.watch_bt_connect(mac, name, timeout=20, on_status=_on_bt)
                fmt.out("")
                if result == "connected":
                    fmt.out(fmt.GREEN + "✓ " + name + " verbunden" + fmt.RESET)
                elif result == "failed":
                    fmt.out(fmt.RED + "✗ Verbindung fehlgeschlagen — Geraet erreichbar?" + fmt.RESET)
                else:
                    fmt.out("✗ Timeout — kein Verbindungsaufbau nach 20s")
        elif args.bt_cmd == "pair":
            dev = svc.bt_resolve(args.query)
            mac  = dev["mac"] if dev else args.query.strip()
            name = dev.get("name","") if dev else mac
            if use_json:
                svc.send("bt_repair:" + mac)
                fmt.print_json({"ok": True, "mac": mac, "action": "bt_repair"})
            else:
                fmt.out("Pairing mit " + (name + " (" + mac + ")" if name and name != mac else mac))
                fmt.out("  → Geraet jetzt in Pairing-Modus bringen!")
                fmt.out("  → Warte auf Pairing-Abschluss (bis 30s)…")
                import time as _t_pair
                svc.send("bt_repair:" + mac)
                _t_pair.sleep(2)
                # Prüfe nach 5, 15, 25 Sekunden ob Gerät gepairt wurde
                for _wait in [5, 10, 8]:
                    _t_pair.sleep(_wait)
                    _d = svc.get_status()
                    # Prüfe BlueZ-Datenbank via bt_known
                    _devs = svc.ipc.read_json("/tmp/pidrive_bt_known_devices.json", {}).get("devices", [])
                    _paired = [x for x in _devs if x.get("mac","").upper() == mac.upper() and x.get("paired")]
                    if _paired:
                        fmt.out(fmt.GREEN + "✓ Gepairt: " + (_paired[0].get("name") or mac) + fmt.RESET)
                        fmt.out("  Jetzt verbinden: pidrivectl bt connect " + mac)
                        break
                else:
                    fmt.out("  Pairing-Status unbekannt — pruefe: pidrivectl bt known")
                    fmt.out("  Tipp: Geraet wirklich in Pairing-Modus?")
        elif args.bt_cmd == "status":
            d = svc.get_status()
            # Fallback: wenn IPC "getrennt" sagt, direkt BlueZ prüfen
            if not d.get("bt") and not use_json:
                try:
                    import subprocess as _sp
                    _r = _sp.run("bluetoothctl info 2>/dev/null | grep -E 'Connected|Name|Paired'",
                                 shell=True, capture_output=True, text=True, timeout=3)
                    if "Connected: yes" in _r.stdout:
                        _name = next((l.split("Name:")[1].strip() for l in _r.stdout.splitlines()
                                      if "Name:" in l), "")
                        fmt.out(fmt.GREEN + "Bluetooth: verbunden (BlueZ)" + fmt.RESET)
                        if _name:
                            fmt.out(f"  Gerät: {_name}")
                        fmt.out("  (PiDrive-Sync erfolgt bei nächster Statusaktualisierung)")
                        sys.exit(EXIT_OK)
                except Exception: pass
            if use_json:
                fmt.print_json({"bt": d["bt"], "device": d["bt_device"], "status": d["bt_status"]})
            else:
                connected = d.get("bt", False)
                device    = d.get("bt_device", "") or "–"
                state_str = d.get("bt_status", "getrennt")
                if connected:
                    fmt.out(fmt.GREEN + "✓ Verbunden: " + device + fmt.RESET)
                else:
                    fmt.out("Bluetooth: " + state_str)
                    agent = svc.ipc.read_json("/tmp/pidrive_bt_agent.json", {})
                    if agent.get("ready"):
                        fmt.out("  Agent: bereit (kann Geraete pairen)")
                if d.get("bt_device"): fmt.out(f"  Gerät: {d['bt_device']}")
        sys.exit(EXIT_OK)

    # volume
    if args.cmd == "volume":
        # Direkte Zahl: pidrivectl volume 50
        # vol_arg wurde via sys.argv zu "set N" umgewandelt
        pass  # vol_cmd kommt direkt vom subparser
        if not args.vol_cmd:
            d = svc.get_status()
            if use_json: fmt.print_json({"volume": d.get("volume"), "audio_out": d.get("audio_eff")})
            else: fmt.out(f"Lautstärke: {d.get('volume','–')}%  Ausgang: {d.get('audio_eff','–')}")
            sys.exit(EXIT_OK)
        svc.require_online()
        import time as _time_vol
        if args.vol_cmd == "up":
            svc.send("vol_up"); _time_vol.sleep(0.4)
            vol = svc.get_volume()
            if use_json: fmt.print_json({"ok": True, "volume": vol})
            else: fmt.out("Lautstaerke: " + (str(vol) + "%" if vol is not None else "gesendet"))
            sys.exit(EXIT_OK)
        elif args.vol_cmd == "down":
            svc.send("vol_down"); _time_vol.sleep(0.4)
            vol = svc.get_volume()
            if use_json: fmt.print_json({"ok": True, "volume": vol})
            else: fmt.out("Lautstaerke: " + (str(vol) + "%" if vol is not None else "gesendet"))
            sys.exit(EXIT_OK)
        elif args.vol_cmd == "set":
            lvl = max(0, min(100, args.level))
            import time as _tv
            # vol_set:N → Core aktualisiert PA + amixer + settings["volume"]
            svc.send(f"vol_set:{lvl}")
            _tv.sleep(0.6)  # Core braucht kurz zum Verarbeiten
            d = svc.get_status()
            actual = d.get("volume", lvl)
            if use_json: fmt.print_json({"ok": True, "volume": actual})
            else: fmt.out(f"Lautstaerke: {actual}%")
            sys.exit(EXIT_OK)
        if use_json: fmt.print_json(r)
        else: fmt.out(f"Lautstärke: {args.vol_cmd}")
        sys.exit(EXIT_OK)

    # ppm
    if args.cmd == "ppm":
        if not args.ppm_cmd or args.ppm_cmd == "status":
            # PPM aus settings.json lesen
            import json as _jsppm
            try:
                _sp = __file__.replace("cli/cli.py","config/settings.json").replace("cli\\cli.py","config\\settings.json")
                import os as _osp
                _sp = _osp.path.join(_osp.path.dirname(_osp.path.dirname(_osp.path.abspath(__file__))), "config", "settings.json")
                _s = _jsppm.load(open(_sp))
                ppm_val = _s.get("ppm") or _s.get("ppm_correction", 0)
                if use_json: fmt.print_json({"ppm": ppm_val})
                else: fmt.out("PPM-Offset: " + str(ppm_val) + "  (RTL-SDR DAB/FM)")
            except Exception as e:
                fmt.out("PPM: " + str(e))
        elif args.ppm_cmd == "set":
            svc.require_online()
            r = svc.send("ppm:" + str(args.value))
            if use_json: fmt.print_json(r)
            else: fmt.out("PPM gesetzt auf " + str(args.value))
        elif args.ppm_cmd == "calibrate":
            svc.require_online()
            r = svc.send("ppm_calibrate")
            if use_json: fmt.print_json(r)
            else:
                fmt.out("PPM-Kalibrierung gestartet — rtl_test -p")
                fmt.out("⏱  Mindestlaufzeit: 3 Minuten für stabile Messung")
                fmt.out("   Alternativ direkt: rtl_test -p  (mind. 3 min laufen lassen)")
                fmt.out("   Abbruch nach <60s liefert ungenaue Werte (Ausreißer ±50 ppm)")
                fmt.out("   Ergebnis nach 3 min: pidrivectl ppm")
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
            else:
                import time as _t_ar; _t_ar.sleep(0.3)
                d2 = svc.get_status()
                new_out = d2.get("audio_effective", args.mode)
                fmt.out("Audio-Ausgang: " + fmt.GREEN + new_out + " ✓" + fmt.RESET)
        elif args.audio_cmd == "test":
            # Vollständige Audio-Diagnose
            import subprocess as _sp, os as _os
            G = fmt.GREEN; R = fmt.RED if hasattr(fmt,'RED') else "\033[31m"
            Y = "\033[33m"; RESET = fmt.RESET
            OK  = G + "  ✔" + RESET
            NOK = R + "  ✖" + RESET
            WRN = Y + "  ⚠" + RESET

            def _run(cmd, timeout=4):
                try:
                    r = _sp.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
                    return (r.stdout + r.stderr).strip(), r.returncode == 0
                except Exception as _e:
                    return str(_e), False

            fmt.out("\n" + "─"*48)
            fmt.out("  PiDrive Audio-Diagnose")
            fmt.out("─"*48)

            # ── A) ALSA ──────────────────────────────────────────────────────
            fmt.out("\n=== A) ALSA ===")
            aplay_out, aplay_ok = _run("aplay -l 2>/dev/null")
            if aplay_ok and aplay_out:
                cards = [l for l in aplay_out.splitlines() if "card" in l.lower()]
                fmt.out(OK + f" {len(cards)} ALSA-Gerät(e) gefunden")
                for c in cards:
                    fmt.out(f"     {c.strip()}")
            else:
                fmt.out(NOK + " Keine ALSA-Geräte (aplay -l leer)")

            # ── B) PulseAudio ────────────────────────────────────────────────
            fmt.out("\n=== B) Audio (PipeWire / PulseAudio) ===")
            PA_CMD = "PULSE_SERVER=unix:/var/run/pulse/native"
            pa_info, pa_ok = _run(f"{PA_CMD} pactl info 2>/dev/null")
            if pa_ok:
                fmt.out(OK + " Audio-Server läuft")
                for line in pa_info.splitlines():
                    if "Default Sink:" in line or "Server Version:" in line:
                        fmt.out(f"     {line.strip()}")
            else:
                fmt.out(NOK + " Audio-Server nicht erreichbar")
                fmt.out(WRN + " Tipp: systemctl status pipewire pipewire-pulse wireplumber")

            sinks_out, _ = _run(f"{PA_CMD} pactl list sinks short 2>/dev/null")
            sinks = [l for l in sinks_out.splitlines() if l.strip()]
            if sinks:
                fmt.out(OK + f" {len(sinks)} PA-Sink(s) vorhanden")
                for s in sinks:
                    parts = s.split()
                    name = parts[1] if len(parts) > 1 else s
                    state = parts[4] if len(parts) > 4 else ""
                    if "null" in name.lower():
                        fmt.out(WRN + f" {name}  [{state}]  (virtuell)")
                    elif "bluez" in name.lower():
                        fmt.out(OK + f" {name}  [{state}]  ← BT")
                    else:
                        fmt.out(f"     {name}  [{state}]")
            else:
                fmt.out(NOK + " Keine PA-Sinks vorhanden")
                fmt.out(WRN + " → systemctl restart pipewire pipewire-pulse wireplumber")
                fmt.out(WRN + " → BT: WirePlumber lädt A2DP automatisch nach BT-Connect")

            # BT-Module: Mit PipeWire übernimmt WirePlumber — kein load-module nötig
            pa_info, _ = _run(f"{PA_CMD} pactl info 2>/dev/null")
            if "PipeWire" in pa_info:
                fmt.out(OK + " PipeWire/WirePlumber: BT A2DP automatisch (kein load-module)")
            else:
                mods_out, _ = _run(f"{PA_CMD} pactl list modules short 2>/dev/null")
                for mod in ("module-bluetooth-discover", "module-bluetooth-policy"):
                    if mod in mods_out:
                        fmt.out(OK + f" {mod} geladen")
                    else:
                        fmt.out(NOK + f" {mod} NICHT geladen")
                        fmt.out(f"     → {PA_CMD} pactl load-module {mod}")

            # ── C) Bluetooth ─────────────────────────────────────────────────
            fmt.out("\n=== C) Bluetooth ===")
            hci, _ = _run("hciconfig 2>/dev/null")
            if "UP RUNNING" in hci:
                fmt.out(OK + " hci0 aktiv (UP RUNNING)")
            else:
                fmt.out(NOK + " kein HCI-Adapter aktiv")

            conn_out, _ = _run("bluetoothctl devices Connected 2>/dev/null")
            if conn_out.strip():
                for line in conn_out.strip().splitlines():
                    parts = line.split()
                    mac  = parts[1] if len(parts) > 1 else "?"
                    name = " ".join(parts[2:]) if len(parts) > 2 else mac
                    fmt.out(OK + f" Verbunden: {name}  [{mac}]")
                    # BT-Profil prüfen
                    cards_out, _ = _run(f"{PA_CMD} pactl list cards 2>/dev/null")
                    bt_card = "bluez_card." + mac.replace(":", "_")
                    if bt_card in cards_out:
                        # Aktives Profil extrahieren
                        in_card = False
                        for cl in cards_out.splitlines():
                            if bt_card in cl: in_card = True
                            if in_card and "Active Profile:" in cl:
                                prof = cl.split(":", 1)[1].strip()
                                if "a2dp" in prof.lower():
                                    fmt.out(OK + f"   A2DP-Profil aktiv: {prof}")
                                else:
                                    fmt.out(NOK + f"   Profil: {prof}  (kein A2DP!)")
                                    fmt.out(f"     → {PA_CMD} pactl set-card-profile {bt_card} a2dp-sink")
                                break
                    # A2DP-Sink suchen
                    expected_sink = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
                    if expected_sink in sinks_out:
                        fmt.out(OK + f"   A2DP-Sink: {expected_sink}")
                    else:
                        fmt.out(NOK + f"   Kein A2DP-Sink in PA")
                        fmt.out(f"     → Erwartet: {expected_sink}")
            else:
                bt_paired, _ = _run("bluetoothctl devices Paired 2>/dev/null")
                if bt_paired.strip():
                    fmt.out(WRN + " BT-Geräte gepairt, aber keins verbunden")
                    fmt.out("     → bluetoothctl connect <MAC>")
                else:
                    fmt.out(WRN + " Keine BT-Geräte verbunden oder gepairt")

            # ── D) Wiedergabe-Test ───────────────────────────────────────────
            fmt.out("\n=== D) Wiedergabe ===")
            pacat_ok = _sp.run("which pacat 2>/dev/null", shell=True,
                                capture_output=True).returncode == 0

            if sinks and any("null" not in s.split()[1].lower() for s in sinks if s.split()):
                if pacat_ok:
                    fmt.out("  Teste PA-Ausgabe (440 Hz, 2s) …")
                    _tone = ("python3 -c \"import struct,math,subprocess;"
                             "s=b''.join(struct.pack(chr(60)+chr(104),int(32767*math.sin(6.2832*440*i/44100)))"
                             " for i in range(44100*2));"
                             "p=subprocess.Popen(['pacat','--server=unix:/var/run/pulse/native',"
                             "'--format=s16le','--rate=44100','--channels=1'],stdin=subprocess.PIPE);"
                             "p.stdin.write(s);p.stdin.close();p.wait()\"")
                    _, tone_ok = _run(_tone, timeout=6)
                    if tone_ok:
                        fmt.out(OK + " PA-Ton abgespielt")
                    else:
                        fmt.out(NOK + " PA-Ton fehlgeschlagen (kein Sink oder BT nicht A2DP)")
                else:
                    fmt.out(WRN + " pacat nicht verfügbar — apt install pulseaudio-utils (oder pipewire-pulse)")
            else:
                fmt.out(WRN + " Kein realer PA-Sink — Wiedergabe übersprungen")
                fmt.out("     → systemctl restart pipewire pipewire-pulse wireplumber")

            # ── E) mpv Audio-Routing ─────────────────────────────────────────
            fmt.out("\n=== E) mpv ===")
            mpv_devs, mpv_ok = _run("mpv --audio-device=help 2>&1 | head -20")
            if mpv_ok:
                fmt.out(OK + " mpv vorhanden")
                if "pulse" in mpv_devs.lower() or "pipewire" in mpv_devs.lower():
                    fmt.out(OK + " mpv hat PulseAudio/PipeWire-Backend")
                else:
                    fmt.out(WRN + " mpv hat kein PA-Backend erkannt")
            else:
                fmt.out(NOK + " mpv nicht gefunden")

            # ── Zusammenfassung ──────────────────────────────────────────────
            fmt.out("\n=== Empfehlungen ===")
            recs = []
            if not pa_ok:
                recs.append("systemctl restart pipewire pipewire-pulse wireplumber")
            if not sinks:
                recs.append("systemctl restart pipewire pipewire-pulse wireplumber  (keine Sinks)")
            # PipeWire/WirePlumber: kein load-module nötig
            if not conn_out.strip() and aplay_ok:
                recs.append("BT verbinden: pidrivectl bt connect <MAC>")
            if recs:
                for r in recs:
                    fmt.out(WRN + f" {r}")
            else:
                fmt.out(OK + " Keine Probleme erkannt")
            fmt.out("─"*48 + "\n")
            sys.exit(EXIT_OK)


        elif args.audio_cmd == "status":
            try:
                import sys as _s2, os as _o2
                _b2 = _o2.path.dirname(_o2.path.abspath(__file__))
                if _b2 not in _s2.path: _s2.path.insert(0, _b2)
                from modules.audio import read_last_decision_file as _rld
                _ad = _rld()
            except Exception: _ad = {}
            _bt = svc.get_status().get("bt_status", "–")
            if use_json:
                fmt.print_json({"requested": _ad.get("requested","–"), "effective": _ad.get("effective","–"),
                                "sink": _ad.get("sink","–"), "reason": _ad.get("reason","–"), "bt": _bt})
            else:
                _eff = _ad.get("effective") or "none"
                _req = _ad.get("requested") or "–"
                _rsn = _ad.get("reason") or ""
                _snk = _ad.get("sink") or ""
                fmt.out(f"Ausgang:   {_eff}" + (" ✓" if _eff not in ("none","–","") else ""))
                fmt.out(f"Angefragt: {_req}")
                if _rsn: fmt.out(f"Grund:     {_rsn}")
                if _snk: fmt.out(f"Sink:      {_snk[:55]}")
                fmt.out(f"Bluetooth: {_bt}")
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
            if use_json:
                fmt.print_json(r); sys.exit(EXIT_OK)
            fmt.out("DAB-Sendersuchlauf gestartet (ca. 2-3 Minuten)…")
            fmt.out("  Ctrl+C: Monitor beenden (Scan laeuft weiter im Hintergrund)")
            import time as _ts, json as _js
            _prev_found = 0; _prev_chs = set(); _start_ts = _ts.time()
            try:
                while True:
                    _ts.sleep(2)
                    _elapsed = int(_ts.time() - _start_ts)
                    # Aktuellem Kanal aus Progress
                    try:
                        _pg = _js.load(open("/tmp/pidrive_progress.json"))
                        if _pg.get("active") and _pg.get("message"):
                            print(f"\r  [{_elapsed:>3}s] " + _pg.get("message","")[:45], end="", flush=True)
                    except Exception: pass
                    # Scan-Debug für Zwischenergebnisse
                    try:
                        _dg = _js.load(open("/tmp/pidrive_dab_scan_debug.json"))
                        _fd = _dg.get("found", 0)
                        if _fd != _prev_found:
                            print("")
                            fmt.out(f"  → {_fd} Sender bisher gefunden")
                            for _ch, _cd in _dg.get("channels", {}).items():
                                if _ch not in _prev_chs:
                                    _sts = _cd.get("stations", [])
                                    for _st in _sts[:4]:
                                        fmt.out(f"    {_ch}: " + _st.get("name","?"))
                                    if len(_sts) > 4: fmt.out(f"    ... +{len(_sts)-4} weitere")
                                    _prev_chs.add(_ch)
                            _prev_found = _fd
                    except Exception: pass
                    # Scan fertig?
                    try:
                        _p2 = _js.load(open("/tmp/pidrive_progress.json"))
                        if not _p2.get("active", True) and _elapsed > 10:
                            print(""); fmt.out(f"\n✓ Scan fertig ({_elapsed}s)")
                            try:
                                _cfgp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "dab_stations.json")
                                _cfg = _js.load(open(_cfgp))
                                _all = _cfg.get("stations", _cfg) if isinstance(_cfg, dict) else _cfg
                                fmt.out(f"  {len(_all)} Sender in Datenbank gespeichert")
                            except Exception: pass
                            break
                    except Exception: pass
                    if _elapsed > 300: print(""); fmt.out("  Timeout"); break
            except KeyboardInterrupt:
                print(""); fmt.out("  Monitor beendet (Scan laeuft weiter)")
        elif args.dab_cmd == "next":
            svc.require_online()
            svc.send("dab_next")
            fmt.out("DAB: nächster Sender.")
        elif args.dab_cmd == "prev":
            svc.require_online()
            svc.send("dab_prev")
            fmt.out("DAB: vorheriger Sender.")
        elif args.dab_cmd == "stop":
            svc.require_online()
            svc.send("radio_stop")
            fmt.out("DAB gestoppt.")
        elif args.dab_cmd == "live":
            if not svc.ipc.core_online():
                fmt.err("Core offline"); sys.exit(EXIT_OFFLINE)
            once = getattr(args,"once",False); changes = getattr(args,"changes",False)
            interval = getattr(args,"interval",1.0)
            import os as _os
            try:
                if once:
                    snap = svc.get_dab_live_snapshot()
                    if use_json: fmt.print_json(snap)
                    else: fmt.out(fmt.format_dab_live_block(snap))
                elif changes:
                    fmt.out("DAB Live --changes | Ctrl+C zum Beenden")
                    for snap, diff in svc.iter_dab_live(interval=interval, changes=True):
                        if diff: fmt.out(fmt.format_dab_change_line(snap, diff))
                else:
                    for snap, _ in svc.iter_dab_live(interval=interval, changes=False):
                        if _os.isatty(1): print("\033[2J\033[H", end="", flush=True)
                        fmt.out(fmt.format_dab_live_block(snap))
                        if not _os.isatty(1): break
            except KeyboardInterrupt:
                fmt.out("\nMonitor beendet.")
        sys.exit(EXIT_OK)

    # scanner
    if args.cmd == "scanner":
        sc_cmd = getattr(args, "sc_cmd", None)
        sc_action = getattr(args, "sc_action", None)

        BANDS = ["pmr446","freenet","lpd433","vhf","uhf","cb","fm"]

        if sc_cmd is None:
            # scanner ohne Argument → Status
            r = svc.get_status()
            sc = r.get("scanner", {})
            if sc.get("active"):
                fmt.out(f"Scanner aktiv: Band={sc.get('band','?')}  Freq={sc.get('freq','?')} MHz  Kanal={sc.get('ch','?')}")
                fmt.out(f"  Squelch={r.get('scanner_squelch', r.get('squelch','?'))}  PPM={r.get('ppm_correction','?')}")
            else:
                fmt.out("Scanner: inaktiv")
                fmt.out(f"  Verfügbare Bänder: {', '.join(BANDS)}")
            sys.exit(EXIT_OK)

        if sc_cmd == "squelch":
            svc.send(f"set_scanner_squelch:{args.level}")
            fmt.out(f"  Squelch: {args.level}")
            sys.exit(EXIT_OK)

        if sc_cmd == "ppm":
            svc.send(f"set_ppm:{args.value}")
            fmt.out(f"  PPM: {args.value}")
            sys.exit(EXIT_OK)

        if sc_cmd == "stop":
            svc.send("scanner_stop")
            fmt.out("  Scanner gestoppt")
            sys.exit(EXIT_OK)

        # Band-Kommandos: sc_cmd ist das Band
        band = sc_cmd
        if band in BANDS:
            if sc_action == "scan":
                svc.send(f"scan_next:{band}")
                fmt.out(f"  Scanner {band}: Scan gestartet")
            elif sc_action == "stop":
                svc.send("scanner_stop")
                fmt.out("  Scanner gestoppt")
            elif sc_action == "next":
                svc.send(f"scan_up:{band}")
                fmt.out(f"  {band}: nächster Kanal")
            elif sc_action == "prev":
                svc.send(f"scan_down:{band}")
                fmt.out(f"  {band}: vorheriger Kanal")
            elif sc_action == "ch":
                svc.send(f"scan_setch:{band}:{args.n}")
                fmt.out(f"  ✓ {band} Kanal {args.n}")
            elif sc_action == "freq":
                svc.send(f"scan_setfreq:{band}:{args.f}")
                fmt.out(f"  ✓ {band} Freq {args.f} MHz")
            else:
                fmt.err(f"Unbekannte Aktion. Nutze: scan | ch N | freq F | next | prev | stop")
            sys.exit(EXIT_OK)
        sys.exit(EXIT_OK)

    # system
    if args.cmd == "system":
        if not args.sys_cmd or args.sys_cmd == "info":
            v = svc.get_version()
            d = svc.get_status()
            sp = svc.raspotify_status()
            if use_json:
                fmt.print_json({"version": v, "online": d["online"],
                                 "ip": d.get("wifi_ssid",""),
                                 "spotify": sp})
            else:
                fmt.out(f"PiDrive v{v}")
                fmt.out(f"Core: {'online' if d['online'] else 'OFFLINE'}")
                if d.get("wifi_ssid"): fmt.out(f"WiFi: {d['wifi_ssid']}")
                # librespot oder raspotify
                import subprocess as _ssp2, os as _oss
                _sp_svc = "librespot" if _oss.path.exists("/usr/local/bin/librespot") else "raspotify"
                _sp_r = _ssp2.run(["systemctl","is-active",_sp_svc],capture_output=True,text=True,timeout=3)
                _sp_active = _sp_r.stdout.strip() == "active"
                _cred = _oss.path.exists("/var/cache/librespot/credentials.json")
                sp_state = "aktiv ✓" if _sp_active else ("gestoppt (Token vorhanden)" if _cred else "nicht eingerichtet")
                fmt.out(f"Spotify: {sp_state}  [{_sp_svc}]")
                if not _sp_active:
                    import cli.format as _f
                    if not _cred:
                        fmt.out(f"{_f.DIM}  → OAuth einmalig: pidrivectl system spotify-oauth{_f.RESET}")
                    fmt.out(f"{_f.DIM}  → systemctl start {_sp_svc}{_f.RESET}")
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
            result = svc.run_diagnose()
            fmt.out(result)
        elif args.sys_cmd == "spotify-oauth":
            import subprocess as _sosp, os as _soos
            _lb = "/usr/local/bin/librespot"
            if not _soos.path.exists(_lb):
                _exit_err("librespot nicht gefunden. Bitte zuerst installieren.")
            fmt.out("Spotify OAuth — Browser-URL erscheint gleich.")
            fmt.out("Im Browser öffnen, einloggen, dann Strg+C.")
            _env = {**__import__("os").environ,
                    "PULSE_SERVER": "unix:/var/run/pulse/native"}
            _sosp.run([_lb, "--name", "PiDrive", "--device-type", "automobile",
                       "--enable-oauth", "--system-cache", "/var/cache/librespot"],
                      env=_env)
            if _soos.path.exists("/var/cache/librespot/credentials.json"):
                fmt.out("\n✓ Token gespeichert.")
                _sosp.run(["systemctl", "restart", "librespot"], capture_output=True)
                fmt.out("✓ librespot.service neugestartet.")
            else:
                fmt.err("Kein Token — OAuth nicht abgeschlossen?")
        sys.exit(EXIT_OK)

    # playlist
    if args.cmd == "playlist":
        import json as _plj, os as _plo, datetime as _dt
        _hist = _plo.path.join(_plo.path.dirname(_plo.path.dirname(_plo.path.abspath(__file__))),
                               "config", "play_history.json")
        try:
            with open(_hist, encoding="utf-8") as _plf: _entries = _plj.load(_plf)
        except Exception: _entries = []
        _date = getattr(args, "date", "today")
        _today = _dt.date.today().isoformat()
        if _date == "today":   _fil = [e for e in _entries if e.get("date","").startswith(_today)]; _label = f"Heute ({_today})"
        elif _date == "all":   _fil = _entries; _label = "Alle Einträge"
        elif _date == "last":  _fil = _entries[-20:]; _label = "Letzte 20"
        else:                  _fil = [e for e in _entries if e.get("date","").startswith(_date)]; _label = _date
        if use_json:
            fmt.print_json({"label": _label, "count": len(_fil), "entries": _fil})
        else:
            fmt.out(f"\n  {_label} — {len(_fil)} Titel"); fmt.out("  " + "─"*36)
            for _e in _fil:
                # "ts_human" hat "YYYY-MM-DD HH:MM:SS" → [-8:-3] = "HH:MM"
                _time_str = str(_e.get("ts_human","") or _e.get("time","") or "")
                _t = _time_str[-8:-3] if len(_time_str) >= 8 else ""
                _sta = _e.get('station') or _e.get('name') or ''
                _trk = _e.get('track') or ''
                _art = _e.get('artist') or ''
                _song = f"{_art} — {_trk}" if _art and _trk else (_trk or _art or '')
                _display = f"{_sta}  {_song}" if _sta and _song else (_sta or _song or '?')
                fmt.out(f"  {_t:5}  {_e.get('source',''):8}  {_display}")
            if not _fil: fmt.out("  (keine Einträge)")
        sys.exit(EXIT_OK)

    # log
    if args.cmd == "log":
        log_txt = svc.log(args.target)
        fmt.out(log_txt)
        sys.exit(EXIT_OK)

    # debug
    if args.cmd == "test":
        import test_suite as _ts
        cmd = getattr(args, "test_cmd", "all") or "all"
        if cmd == "all":
            ok = _ts.run_all()
            sys.exit(EXIT_OK if ok else EXIT_ERROR)
        elif cmd == "system":   _ts.test_system()
        elif cmd == "audio":    _ts.test_audio()
        elif cmd == "bt":       _ts.test_bluetooth()
        elif cmd == "mpris":    _ts.test_mpris2_push()
        elif cmd == "webradio": _ts.test_webradio()
        elif cmd == "fm":       _ts.test_fm()
        elif cmd == "scanner":  _ts.test_scanner_fm()
        elif cmd == "dab":      _ts.test_dab()
        elif cmd == "dabscan":  _ts.test_dab_scan()
        elif cmd == "spotify":  _ts.test_spotify()
        elif cmd == "avrcp":    _ts.test_avrcp_inject()
        elif cmd == "log":      _ts.test_log_summary()
        sys.exit(EXIT_OK)

    if args.cmd == "debug":
        pass  # debug-Handler folgt unten
    # ── avrcp ─────────────────────────────────────────────────────────────────
    if args.cmd == "avrcp":
        import json as _aj, time as _at
        AVRCP_EVENTS = "/tmp/pidrive_avrcp_events.json"
        AVRCP_STATUS = "/tmp/pidrive_avrcp_status.json"

        def _load_events():
            try: return _aj.load(open(AVRCP_EVENTS))
            except Exception: return {"events": [], "total": 0}

        def _fmt_ev(ev):
            ts  = ev.get("ts_human") or _at.strftime("%H:%M:%S", _at.localtime(ev.get("ts",0)))
            evn = ev.get("event","?")
            trg = ev.get("trigger","")
            ctx = ev.get("context","")
            arrow = f" → {trg}" if trg else ""
            return f"  [{ts}] {evn:<16}{arrow:<20}  ctx={ctx}"

        cmd = args.avrcp_cmd or "monitor"

        if cmd == "monitor":
            svc.require_online()
            fmt.out("AVRCP-Monitor — BMW iDrive Tasten  (Ctrl+C beendet)")
            fmt.out("=" * 52)
            data = _load_events()
            recent = data.get("events", [])[-5:]
            if recent:
                fmt.out("Zuletzt:")
                for ev in recent: fmt.out(_fmt_ev(ev))
                fmt.out("")
            last_id = recent[-1].get("id",-1) if recent else -1
            fmt.out("Warte auf Events…")
            try:
                while True:
                    _at.sleep(0.3)
                    evs = _load_events().get("events",[])
                    for ev in [e for e in evs if e.get("id",-1) > last_id]:
                        line = _fmt_ev(ev)
                        col  = fmt.GREEN if ev.get("trigger") else ""
                        fmt.out((col+line+fmt.RESET) if col else line)
                        last_id = ev.get("id", last_id)
            except KeyboardInterrupt:
                fmt.out("\nMonitor beendet.")
            sys.exit(EXIT_OK)

        elif cmd == "status":
            try:
                st = _aj.load(open(AVRCP_STATUS))
                fmt.out(f"AVRCP [{st.get('ts_human','?')}]")
                fmt.out(f"  Event:    {st.get('last_event','–')}")
                fmt.out(f"  Trigger:  {st.get('trigger','–')}")
                fmt.out(f"  Kontext:  {st.get('context','–')}")
            except Exception:
                fmt.out("Kein AVRCP-Status (noch kein Event eingegangen)")
            sys.exit(EXIT_OK)

        elif cmd == "events":
            data = _load_events()
            events = data.get("events",[])
            if use_json: fmt.print_json(data); sys.exit(EXIT_OK)
            fmt.out(f"AVRCP Ringbuffer — {len(events)} Events (gesamt: {data.get('total',0)})")
            for ev in events[-20:]: fmt.out(_fmt_ev(ev))
            if not events: fmt.out("  (keine Events)")
            sys.exit(EXIT_OK)

        elif cmd == "inject":
            arg = args.avrcp_arg or "next"
            VALID = ["next","prev","play","stop","up","down","enter","back",
                     "vol_up","vol_down","nav_up","nav_down","dab_next","dab_prev"]
            if arg not in VALID:
                fmt.out(f"Unbekannt: {arg!r}  Gültig: {chr(44).join(VALID)}")
                sys.exit(1)
            svc.require_online()
            svc.send(arg)
            fmt.out(f"✓ Injiziert: {arg}")
            sys.exit(EXIT_OK)

    parser.print_help()
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
