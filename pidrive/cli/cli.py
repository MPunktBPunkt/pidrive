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

  audio route klinke|bt|hdmi|usb_gadget|auto   Audio-Ausgang wählen
  audio status            Audio-Status

  usb status              ESP / USB-Gadget Presence (PUMP)
  usb probe               Einmal SoftAP+Serial prüfen

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
from cli.adapters import SOURCE_STATE_FILE

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

  pidrivectl spectrum scan                 UKW 87.5–108, Top-10 Peaks
  pidrivectl spectrum scan 87.5-108 -n 5   Bereich + Anzahl Peaks
  pidrivectl spectrum peek 106.9           Einzelkanal (Offset, DC-sicher)
  pidrivectl spectrum last                 Letztes Scan-Ergebnis

  pidrivectl scanner pmr446 scan           PMR446 Einmal-Scan
  pidrivectl scanner monitor status        PMR446 Dauer-Detektor Status
  pidrivectl scanner monitor start         Detektor starten (optional Autotune)
  pidrivectl scanner monitor start --no-tune  nur loggen, nicht umschalten
  pidrivectl scanner airband freq 121.500  Airband AM manuell
  pidrivectl scanner airband ch 1          Airband-Preset (config)
  pidrivectl scanner airband next          Airband nächstes Preset
  pidrivectl scanner airband prev          Airband vorheriges Preset
  pidrivectl scanner airband scan          Airband Presets nach Signal durchsuchen
  pidrivectl scanner airband list          Airband-Presets anzeigen
  pidrivectl scanner airband monitor start Airband Dauer-Überwachung (AM)
  pidrivectl scanner airband monitor stop
  pidrivectl scanner airband monitor status
  pidrivectl scanner monitor start --trigger-on 18  Lab: niedrigere Hit-Schwelle
  pidrivectl scanner monitor stop
  pidrivectl scanner monitor log -n 40     letzte Activity-Events

  pidrivectl system              System-Info + Spotify-Status
  pidrivectl system resources    RAM, Speicher, Uptime, Throttling
  pidrivectl system diagnose     Vollstaendige Systemdiagnose
  pidrivectl update              Update von GitHub prüfen (mit Bestätigung)
  pidrivectl update --check      Nur prüfen, nichts einspielen
  pidrivectl update --yes        Einspielen ohne Nachfrage

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
    p_btp = bt_sub.add_parser("pair", help="Pairen (ohne Adresse: auf BMW warten)")
    p_btp.add_argument("query", nargs="?", default=None,
                       help="MAC/Name optional — fehlt: BMW-initiiert")
    bt_sub.add_parser("agent", help="D-Bus-Agent-Zustand + letzte Anfragen (BF-C)")
    p_btw = bt_sub.add_parser("pair-window", help="Pairing-Fenster öffnen (Regel window)")
    p_btw.add_argument("seconds", nargs="?", default="300",
                       help="Dauer in Sekunden (Vorgabe 300)")
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

    # ── spectrum ──────────────────────────────────────────────────────────
    p_spec = sub.add_parser("spectrum", help="RTL-SDR Spektrum / UKW-Peak-Scan")
    spec_sub = p_spec.add_subparsers(dest="spectrum_cmd")
    p_sscan = spec_sub.add_parser(
        "scan", help="Bereich scannen, Kanalenergie-Cluster als Peaks")
    p_sscan.add_argument(
        "range", nargs="?", default=None,
        help="Start-Stop MHz, z.B. 87.5-108 oder 102.5:103.5")
    p_sscan.add_argument("-n", "--peaks", type=int, default=None,
                         help="Anzahl Top-Peaks (Default 10)")
    p_sscan.add_argument("--start", type=float, default=None)
    p_sscan.add_argument("--stop", type=float, default=None)
    p_sscan.add_argument("--gain", type=int, default=None,
                         help="Gain dB oder -1=Auto")
    p_sscan.add_argument("--ppm", type=int, default=None)
    p_sscan.add_argument("--avg", type=int, default=None)
    p_speek = spec_sub.add_parser("peek", help="Einzelne Frequenz prüfen")
    p_speek.add_argument("freq", type=float, help="Frequenz MHz, z.B. 106.9")
    p_speek.add_argument("--gain", type=int, default=None)
    p_speek.add_argument("--ppm", type=int, default=None)
    p_speek.add_argument("--avg", type=int, default=None)
    spec_sub.add_parser("last", help="Letztes Spektrum-/Scan-Ergebnis")

    # ── audio ─────────────────────────────────────────────────────────────
    p_audio = sub.add_parser("audio", help="Audio-Ausgang")
    audio_sub = p_audio.add_subparsers(dest="audio_cmd")
    p_route = audio_sub.add_parser("route")
    p_route.add_argument("mode", choices=["klinke", "bt", "hdmi", "auto", "usb_gadget", "usb"])
    audio_sub.add_parser("status")
    audio_sub.add_parser("test", help="Testton abspielen (3s)")

    # ── usb / ESP ─────────────────────────────────────────────────────────
    p_usb = sub.add_parser("usb", help="ESP32 USB-MSC / PUMP")
    usb_sub = p_usb.add_subparsers(dest="usb_cmd")
    usb_sub.add_parser("status", help="Presence aus Status-IPC")
    usb_sub.add_parser("probe", help="Sofort SoftAP+Serial pollen")

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
    for _scb in ["pmr446","freenet","lpd433","vhf","uhf","cb","fm","airband"]:
        _p = sc_sub.add_parser(_scb)
        _sc_sub2 = _p.add_subparsers(dest="sc_action")
        _p_scan = _sc_sub2.add_parser(
            "scan",
            help=("Presets/Kanäle nach Signal durchsuchen "
                  "(Airband: AM-Detect)") if _scb == "airband"
            else "Kanäle/Band nach Signal durchsuchen",
        )
        _p_scan.add_argument("--verbose", "-v", action="store_true",
                             help="pro Kanal Frequenz/Entscheidung ausgeben")
        _sc_sub2.add_parser("stop")
        _sc_sub2.add_parser("next", help="nächstes Preset/Kanal (ohne Suche)")
        _sc_sub2.add_parser("prev", help="vorheriges Preset/Kanal (ohne Suche)")
        if _scb == "airband":
            _sc_sub2.add_parser("list", help="Airband-Presets aus config/airband_stations.json")
            _p_amon = _sc_sub2.add_parser(
                "monitor", help="Airband Dauer-Überwachung (Preset-AM)"
            )
            _amon_sub = _p_amon.add_subparsers(dest="air_mon_action")
            _p_amon_start = _amon_sub.add_parser("start", help="Überwachung starten")
            _p_amon_start.add_argument(
                "--no-tune", action="store_true",
                help="Nur erkennen, nicht umschalten",
            )
            _p_amon_start.add_argument(
                "--hold", type=float, default=None,
                help="Hörzeit Sekunden nach Treffer (Default 20)",
            )
            _amon_sub.add_parser("stop", help="Überwachung stoppen")
            _amon_sub.add_parser("status", help="Monitor-Status")
        _p_ch  = _sc_sub2.add_parser("ch");   _p_ch.add_argument("n",  type=int)
        _p_fr  = _sc_sub2.add_parser("freq"); _p_fr.add_argument("f",  type=float)
    sc_sub.add_parser("status", help="Aktives Band, Frequenz, Squelch")
    _p_sq = sc_sub.add_parser("squelch"); _p_sq.add_argument("level", type=int)
    _p_pp = sc_sub.add_parser("ppm");     _p_pp.add_argument("value", type=int)
    _p_st = sc_sub.add_parser("stop")
    # PMR Dauer-Überwachung (Backend-Log + optional Autotune)
    _p_mon = sc_sub.add_parser("monitor", help="PMR446 Dauer-Überwachung")
    _mon_sub = _p_mon.add_subparsers(dest="mon_action")
    _p_mon_start = _mon_sub.add_parser("start", help="Überwachung starten")
    _p_mon_start.add_argument("--no-tune", action="store_true",
                              help="Nur loggen, nicht umschalten")
    _p_mon_start.add_argument("--hold", type=float, default=None,
                              help="Hörzeit in Sekunden (Default 15)")
    _p_mon_start.add_argument("--trigger-on", type=float, default=None,
                              dest="trigger_on",
                              help="Hit-Schwelle relativ Noise in dB (Default 25; Lab oft 16–20)")
    _p_mon_start.add_argument("--trigger-off", type=float, default=None,
                              dest="trigger_off",
                              help="Hysterese unter Trigger in dB (Default 14)")
    _p_mon_start.add_argument("--watch", type=float, default=None,
                              help="Watch-Fenster Sekunden (0.5–2.5, Default 1.0)")
    _mon_sub.add_parser("stop", help="Überwachung stoppen")
    _mon_sub.add_parser("status", help="Monitor-Status")
    _p_mon_log = _mon_sub.add_parser("log", help="Aktivitäts-Log anzeigen")
    _p_mon_log.add_argument("-n", type=int, default=40, help="letzte N Zeilen")

    # ── system ────────────────────────────────────────────────────────────
    p_sys = sub.add_parser("system", help="System")
    sys_sub = p_sys.add_subparsers(dest="sys_cmd")
    sys_sub.add_parser("info")
    sys_sub.add_parser("resources")
    sys_sub.add_parser("reboot")
    sys_sub.add_parser("shutdown")
    sys_sub.add_parser("diagnose")
    sys_sub.add_parser("spotify-oauth", help="Spotify OAuth einmalig einrichten")

    # ── update (GitHub OTA mit Bestätigung) ─────────────────────────────────
    p_upd = sub.add_parser("update", help="Update von GitHub prüfen / einspielen")
    p_upd.add_argument("--check", action="store_true",
                       help="Nur prüfen, nichts einspielen")
    p_upd.add_argument("--yes", "-y", action="store_true",
                       help="Ohne Nachfrage einspielen")

    # ── log ───────────────────────────────────────────────────────────────
    p_playlist = sub.add_parser("playlist", help="Wiedergabe-History")
    p_playlist.add_argument("date", nargs="?", default="today")
    p_log = sub.add_parser("log", help="Log anzeigen")
    p_log.add_argument("target", nargs="?", default="core",
                       choices=["core","app","display","avrcp"])

    # ── menu (M0: Golden Master, Lint, Verify) ───────────────────────────────
    p_menu = sub.add_parser("menu", help="Menübaum (Snapshot, Verify, Lint)")
    menu_sub = p_menu.add_subparsers(dest="menu_cmd")
    p_snap = menu_sub.add_parser("snapshot", help="Golden Master schreiben")
    p_snap.add_argument("--accept", action="store_true",
                        help="Bestehenden Snapshot ersetzen (CHANGES.md)")
    menu_sub.add_parser("verify", help="Baum gegen Golden Master prüfen")
    menu_sub.add_parser("lint", help="Statische Baum-Prüfungen")
    menu_sub.add_parser("walk", help="Alle Ordner+Blätter auf Erreichbarkeit prüfen")
    p_cost = menu_sub.add_parser("cost", help="Tastendrücke bis Ziel (Skip-Only)")
    p_cost.add_argument("path_id", help="z.B. sources/dab/dab_stations/dab_0xd411")
    p_report = menu_sub.add_parser("report", help="Ergonomie-Kennzahlen aller Blätter")
    p_report.add_argument("--write-doc", action="store_true",
                          help="Baseline nach docs/menue/MENU-ERGONOMIE.md schreiben")
    p_tree = menu_sub.add_parser("tree", help="Vollständigen Menübaum anzeigen")
    p_tree.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_tree.add_argument("--depth", type=int, default=0, help="Max. Tiefe (0=alle)")
    p_goto = menu_sub.add_parser("goto", help="Zu path_id navigieren")
    p_goto.add_argument("path_id", help="z.B. sources/dab/dab_stations")
    p_act = menu_sub.add_parser("activate", help="Knoten per UID auslösen")
    p_act.add_argument("uid", type=lambda x: int(x, 0), help="64-bit UID (dezimal oder 0x…)")
    menu_sub.add_parser("path", help="Aktueller Pfad (Offline-Referenzbaum)")
    menu_sub.add_parser("rebuild", help="Offline-Rebuild-Test (Pfad/Cursor retten)")

    # ── webui (W0/W1 + Live-Smoke) ───────────────────────────────────────────
    p_webui = sub.add_parser("webui", help="WebUI-Check und Selftest")
    webui_sub = p_webui.add_subparsers(dest="webui_cmd")
    webui_sub.add_parser("check", help="Statisch: sendCmd/fetch/Statusfelder")
    webui_sub.add_parser("selftest", help="Import + Aufruf web.shared.*")
    webui_sub.add_parser("routes", help="Alle Flask-Routen listen")
    p_smoke = webui_sub.add_parser("smoke", help="Live-Smoke (Buttons/APIs/State-Machine)")
    p_smoke.add_argument("--mode", choices=["quick", "flows", "full"], default="flows",
                         help="quick|flows|full (default flows)")
    p_smoke.add_argument("--base", default="http://127.0.0.1:8080",
                         help="WebUI-Base-URL")

    # ── source (W7: Zustandsmaschine sichtbar) ───────────────────────────────
    p_source = sub.add_parser("source", help="Quellen-/Transition-Zustand")
    src_sub = p_source.add_subparsers(dest="source_cmd")
    src_sub.add_parser("state", help="source_current, transition, owner, Datei vs Speicher")
    src_sub.add_parser("history", help="Letzte 20 Übergänge")

    # ── idrive (M6: AVRCP-Event-Ebene) ───────────────────────────────────────
    p_idrive = sub.add_parser("idrive", help="BMW iDrive Events simulieren (Event-Ebene)")
    p_idrive.add_argument("idrive_cmd", nargs="?", default=None,
                          help="Event (next|play|…) oder script|event")
    p_idrive.add_argument("idrive_arg", nargs="?", default=None,
                          help="Skript-Datei oder Event-Name")
    p_idrive.add_argument("--offline", action="store_true",
                          help="Ohne Core: lokales MenuState + Menü-Kontext")
    p_idrive.add_argument("--settle", type=float, default=0.35,
                          help="Pause nach Live-Event (Skript)")

    # ── debug ─────────────────────────────────────────────────────────────
    # ── test ──────────────────────────────────────────────────────────────────
    p_test = sub.add_parser("test", help="System-Test (alle Quellen + Audio + BT)")
    p_test.add_argument("test_cmd", nargs="?", default="all",
                        choices=["all", "system", "audio", "bt", "mpris",
                                 "webradio", "fm", "scanner", "dab", "dabscan",
                                 "spotify", "avrcp", "log", "menu", "webui"],
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
    # CLI-Aliase: stations web → station list web, web stop → stop, …
    if len(sys.argv) >= 2:
        if sys.argv[1] == "stations":
            sys.argv[1] = "station"
            if len(sys.argv) >= 3 and sys.argv[2] not in ("list",):
                sys.argv.insert(2, "list")
        elif sys.argv[1] == "web" and len(sys.argv) >= 3 and sys.argv[2] == "stop":
            sys.argv = [sys.argv[0], "stop"] + sys.argv[3:]
        elif sys.argv[1] == "station" and len(sys.argv) >= 3:
            if sys.argv[2] in ("web", "dab", "fm", "local"):
                sys.argv.insert(2, "list")
            elif sys.argv[2] == "list" and len(sys.argv) == 3:
                sys.argv.append("web")

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
            try:
                from settings import load_settings as _lds
                _lock_s = int(_lds().get("dab_wait_lock", 90))
            except Exception:
                _lock_s = 90
            fmt.out(f"{fmt.DIM}  (warte auf Lock — bis {_lock_s}s){fmt.RESET}")
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
            result = svc.watch_dab_play(name, timeout=_lock_s + 15,
                                         on_status=_on_status, on_log_line=_on_log)
            icon = STATE_ICONS.get(result, "?")
            if result == "locked":
                fmt.out("")
                fmt.out(icon + " Lock + PCM — DAB spielt")
            elif result == "partial_sync":
                fmt.out("")
                fmt.out(icon + " Sync OK — warte auf Audio (Empfang instabil)")
                fmt.out("  Tipp: Antenne/Fenster — bei Lock ohne Ton: pidrivectl dab live")
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
            query = getattr(args, "query", None)
            # BF-C: ohne Adresse auf Fahrzeug warten (BMW-initiiert)
            if not query:
                fmt.out("Pairing (BMW-initiiert) — warte auf Anfragen …")
                agent = svc.ipc.read_json("/tmp/pidrive_bt_agent.json", {})
                mode = agent.get("mode", "?")
                kind = agent.get("kind", "bluetoothctl?")
                fmt.out(f"Agent: {kind}, Regel={mode}, sichtbar=dauerhaft")
                try:
                    from modules.bluetooth.bt_agent_dbus import open_pair_window
                    open_pair_window(300)
                    fmt.out("Pairing-Fenster 300s geöffnet")
                except Exception:
                    pass
                # BF-G: Ausgangsmenge merken — nur NEUES Paired-Ereignis zählt
                def _paired_set():
                    try:
                        import subprocess as _sp
                        r = _sp.run("bluetoothctl devices Paired 2>/dev/null",
                                    shell=True, capture_output=True, text=True, timeout=3)
                        out = set()
                        for line in (r.stdout or "").splitlines():
                            parts = line.split()
                            if len(parts) >= 2 and parts[0] == "Device":
                                out.add(parts[1].upper())
                        return out
                    except Exception:
                        return set()

                before = _paired_set()
                last_id = 0
                try:
                    ev0 = svc.ipc.read_json("/tmp/pidrive_bt_agent_events.json", {})
                    evs = ev0.get("events") or []
                    if evs:
                        last_id = int(evs[-1].get("id", 0))
                except Exception:
                    pass
                t0 = __import__("time").time()
                paired = False
                paired_dev = ""
                while __import__("time").time() - t0 < 120:
                    __import__("time").sleep(0.4)
                    ev = svc.ipc.read_json("/tmp/pidrive_bt_agent_events.json", {})
                    for e in (ev.get("events") or []):
                        eid = int(e.get("id", 0))
                        if eid <= last_id:
                            continue
                        last_id = eid
                        elapsed = int(__import__("time").time() - t0)
                        detail = e.get("detail") or ""
                        ans = e.get("answer") or "—"
                        reason = e.get("reason") or ""
                        line = f"  [{elapsed:2d}s] {e.get('method','?'):20s} {detail}  → {ans}"
                        if reason:
                            line += f"  ({reason})"
                        fmt.out(line)
                        if e.get("method") == "RequestConfirmation" and "passkey=" in detail:
                            fmt.out("        ↳ Zahl am iDrive vergleichen und dort bestätigen")
                        # BF-G: Erfolg nur bei Agent-Ereignis "Paired" (nicht alter Kopfhörer)
                        if e.get("method") == "Paired":
                            paired = True
                            paired_dev = (e.get("device") or "").replace("_", ":")
                    if paired:
                        break
                    # Zusatz: neues Gerät in Paired-Liste (falls Event verpasst)
                    now_set = _paired_set()
                    neu = now_set - before
                    if neu:
                        paired = True
                        paired_dev = sorted(neu)[0]
                        elapsed = int(__import__("time").time() - t0)
                        fmt.out(f"  [{elapsed:2d}s] Paired                → {paired_dev}  (neu in BlueZ)")
                        break
                fmt.out("")
                if paired:
                    who = paired_dev or "?"
                    fmt.out(fmt.GREEN + f"✓ Gekoppelt: {who}" + fmt.RESET)
                else:
                    fmt.out("Timeout — kein neues Paired-Ereignis (pidrivectl bt agent)")
                sys.exit(EXIT_OK)

            dev = svc.bt_resolve(query)
            mac  = dev["mac"] if dev else query.strip()
            name = dev.get("name","") if dev else mac
            if use_json:
                svc.send("bt_repair:" + mac)
                fmt.print_json({"ok": True, "mac": mac, "action": "bt_repair"})
            else:
                fmt.out("Pairing mit " + (name + " (" + mac + ")" if name and name != mac else mac))
                agent = svc.ipc.read_json("/tmp/pidrive_bt_agent.json", {})
                fmt.out(f"Agent: {agent.get('kind','?')}, Regel={agent.get('mode','?')}, sichtbar=dauerhaft")
                fmt.out("Warte auf Anfragen des Fahrzeugs …")

                last_id = 0
                try:
                    ev0 = svc.ipc.read_json("/tmp/pidrive_bt_agent_events.json", {})
                    evs = ev0.get("events") or []
                    if evs:
                        last_id = int(evs[-1].get("id", 0))
                except Exception:
                    pass
                t0 = __import__("time").time()

                def _on_pair(d):
                    # Agent-Events seit letztem Stand
                    nonlocal last_id
                    ev = svc.ipc.read_json("/tmp/pidrive_bt_agent_events.json", {})
                    for e in (ev.get("events") or []):
                        eid = int(e.get("id", 0))
                        if eid <= last_id:
                            continue
                        last_id = eid
                        detail = e.get("detail") or ""
                        ans = e.get("answer") or "—"
                        reason = e.get("reason") or ""
                        line = f"  [{d['elapsed']:2d}s] {e.get('method','?'):20s} {detail}  → {ans}"
                        if reason:
                            line += f"  ({reason})"
                        fmt.out(line)
                        if e.get("method") == "RequestConfirmation" and "passkey=" in detail:
                            fmt.out("        ↳ Zahl am iDrive vergleichen und dort bestätigen")
                    fmt.out(f"  [{d['elapsed']:2d}s] state={d['state']}")

                result = svc.watch_bt_pair(mac, timeout=90, on_status=_on_pair)
                fmt.out("")
                if result == "paired":
                    fmt.out(fmt.GREEN + "✓ Gekoppelt und verbunden" + fmt.RESET)
                    fmt.out("  Verbinden: pidrivectl bt connect " + mac)
                elif result == "failed":
                    fmt.out(fmt.RED + "✗ Pairing fehlgeschlagen — pidrivectl bt agent" + fmt.RESET)
                else:
                    fmt.out("✗ Timeout — pidrivectl bt agent / bt scan")
        elif args.bt_cmd == "agent":
            agent = svc.ipc.read_json("/tmp/pidrive_bt_agent.json", {})
            ev = svc.ipc.read_json("/tmp/pidrive_bt_agent_events.json", {})
            if use_json:
                fmt.print_json({"agent": agent, "events": (ev.get("events") or [])[-20:]})
            else:
                fmt.out(f"Agent: kind={agent.get('kind','?')} ready={agent.get('ready')} "
                        f"mode={agent.get('mode','?')} window={agent.get('pair_window_s',0)}s "
                        f"events={agent.get('event_count',0)}")
                for e in (ev.get("events") or [])[-15:]:
                    fmt.out(f"  [{e.get('ts_human','')}] {e.get('method')} "
                            f"{e.get('detail','')} → {e.get('answer','—')} ({e.get('reason','')})")
        elif args.bt_cmd == "pair-window":
            try:
                secs = int(getattr(args, "seconds", 300) or 300)
            except Exception:
                secs = 300
            try:
                from modules.bluetooth.bt_agent_dbus import open_pair_window, pair_window_remaining
                until = open_pair_window(secs)
                rem = pair_window_remaining()
                fmt.out(f"Pairing-Fenster {secs}s geöffnet (noch {int(rem)}s)")
            except Exception as e:
                fmt.err(str(e)); sys.exit(EXIT_ERROR)
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
            svc.send(f"vol_set:{lvl}")
            actual = lvl
            for _ in range(10):
                _tv.sleep(0.15)
                d = svc.get_status()
                v = d.get("volume")
                if v is not None and int(v) == lvl:
                    actual = int(v)
                    break
                if v is not None:
                    actual = int(v)
            if use_json: fmt.print_json({"ok": True, "volume": actual, "requested": lvl})
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

    # spectrum
    if args.cmd == "spectrum":
        import re as _re_sp
        from settings import load_settings as _ls_sp
        _s_sp = _ls_sp()

        def _sp_ppm(cli_ppm):
            if cli_ppm is not None:
                return int(cli_ppm)
            return int(_s_sp.get("ppm_correction", _s_sp.get("ppm", 0)) or 0)

        def _sp_gain(cli_gain):
            if cli_gain is not None:
                return int(cli_gain)
            return int(_s_sp.get("scanner_gain", _s_sp.get("fm_gain", 25)))

        def _parse_range(text, start, stop):
            a = start if start is not None else _s_sp.get("spectrum_start_mhz", 87.5)
            b = stop if stop is not None else _s_sp.get("spectrum_stop_mhz", 108.0)
            if text:
                m = _re_sp.match(
                    r"^\s*([0-9]+(?:\.[0-9]+)?)\s*[-:]\s*([0-9]+(?:\.[0-9]+)?)\s*$",
                    text,
                )
                if not m:
                    fmt.out("Range ungültig — erwartet z.B. 87.5-108 oder 102.5:103.5")
                    sys.exit(1)
                a, b = float(m.group(1)), float(m.group(2))
            return float(a), float(b)

        scmd = args.spectrum_cmd
        if not scmd:
            fmt.out("Usage: pidrivectl spectrum scan|peek|last …")
            fmt.out("  scan [87.5-108] [-n 10] [--gain 25] [--ppm 49]")
            fmt.out("  peek 106.9")
            fmt.out("  last")
            sys.exit(EXIT_OK)

        if scmd == "last":
            from modules.radio import spectrum as _spmod
            data = _spmod.load_last_spectrum() or {}
            if use_json:
                slim = {k: v for k, v in data.items() if k != "spectrum_db"}
                fmt.print_json(slim)
            else:
                if not data:
                    fmt.out("Kein letztes Spektrum.")
                else:
                    fmt.out(f"mode={data.get('mode')} ok={data.get('ok')} "
                            f"gain={data.get('gain')} ppm={data.get('ppm')}")
                    peaks = data.get("peaks") or data.get("candidates") or []
                    for i, p in enumerate(peaks[:20], 1):
                        fmhz = p.get("freq_mhz", p.get("freq"))
                        lab = p.get("label") or ""
                        db = p.get("mean_db", p.get("db", p.get("peak_db")))
                        fmt.out(f"  {i:2d}. {fmhz} MHz  {db} dB  {lab}")
            sys.exit(EXIT_OK)

        # Stick braucht Idle — Hinweis wenn Radio läuft
        try:
            from modules import source_state as _ss_gate
            ok_gate, why = _ss_gate.rtl_capture_gate()
            if not ok_gate:
                fmt.out(f"Abbruch: {why}")
                sys.exit(1)
        except SystemExit:
            raise
        except Exception:
            try:
                st = svc.get_status()
                if st.get("radio_playing") or (st.get("source") or "") in ("fm", "dab", "scanner"):
                    fmt.out("Hinweis: Radio/Scanner aktiv — Capture kann fehlschlagen (Stick belegt).")
            except Exception:
                pass

        from modules.radio import spectrum as _spmod

        if scmd == "peek":
            ppm = _sp_ppm(getattr(args, "ppm", None))
            gain = _sp_gain(getattr(args, "gain", None))
            avg = int(args.avg if args.avg is not None else _s_sp.get("spectrum_avg", 2))
            fmt.out(f"Peek {args.freq} MHz  gain={gain} ppm={ppm} avg={avg} …")
            r = _spmod.peek_fm_channel(args.freq, ppm=ppm, gain=gain, avg_frames=avg)
            if use_json:
                fmt.print_json(r)
            elif not r.get("ok"):
                fmt.out("Fehler: " + str(r.get("error")))
                sys.exit(1)
            else:
                det = "JA" if r.get("detected") else "unsicher/schwach"
                lab = r.get("label") or ""
                e = r.get("energy") or {}
                fmt.out(f"{r.get('freq_mhz')} MHz  {lab}  detected={det}")
                fmt.out(f"  peak={e.get('peak_db')} dB @ {e.get('peak_f')}  "
                        f"mean={e.get('mean_db')}  snr≈{r.get('snr_db')}  "
                        f"margin={r.get('margin_db')}")
            sys.exit(EXIT_OK)

        if scmd == "scan":
            start, stop = _parse_range(
                getattr(args, "range", None),
                getattr(args, "start", None),
                getattr(args, "stop", None),
            )
            top_n = int(args.peaks if args.peaks is not None else _s_sp.get("spectrum_peaks", 10))
            ppm = _sp_ppm(getattr(args, "ppm", None))
            gain = _sp_gain(getattr(args, "gain", None))
            avg = int(args.avg if args.avg is not None else _s_sp.get("spectrum_avg", 2))
            fmt.out(f"Scan {start}–{stop} MHz  top={top_n}  gain={gain} ppm={ppm} avg={avg} …")
            r = _spmod.scan_fm_channels(
                start_mhz=start, stop_mhz=stop, top_n=top_n,
                ppm=ppm, gain=gain, avg_frames=avg,
            )
            if use_json:
                slim = {k: v for k, v in r.items() if k != "spectrum_db"}
                fmt.print_json(slim)
            elif not r.get("ok"):
                fmt.out("Fehler: " + str(r.get("error")))
                sys.exit(1)
            else:
                fmt.out(f"ok  floor={r.get('floor_db')} dB  thresh={r.get('thresh_db')} dB  "
                        f"clusters={r.get('peaks_all_count')}  "
                        f"win={r.get('windows_ok')}/{r.get('windows_total')}")
                for i, p in enumerate(r.get("peaks") or [], 1):
                    lab = ("  " + p["label"]) if p.get("label") else ""
                    fmt.out(f"  {i:2d}. {p['freq_mhz']:7.3f} MHz  "
                            f"mean={p['mean_db']:5.1f} dB  peak={p['peak_db']:5.1f}{lab}")
                if not r.get("peaks"):
                    fmt.out("  (keine Peaks über Schwelle — Gain/Bereich prüfen)")
            sys.exit(EXIT_OK)

        fmt.out("Unbekanntes spectrum-Subkommando")
        sys.exit(1)

    # audio
    if args.cmd == "audio":
        if not args.audio_cmd:
            d = svc.get_status()
            if use_json: fmt.print_json({"audio_out": d.get("audio_out"), "effective": d.get("audio_eff")})
            else: fmt.out(f"Audio: {d.get('audio_eff','–')} (angefordert: {d.get('audio_out','–')})")
            sys.exit(EXIT_OK)
        svc.require_online()
        if args.audio_cmd == "route":
            mode = "usb_gadget" if args.mode in ("usb", "usb_gadget") else args.mode
            trig = {
                "klinke": "audio_klinke",
                "bt": "audio_bt",
                "hdmi": "audio_hdmi",
                "auto": "audio_all",
                "usb_gadget": "audio_usb_gadget",
            }[mode]
            r = svc.send(trig)
            if use_json:
                fmt.print_json(r)
                sys.exit(EXIT_OK)
            import time as _t_ar
            _t_ar.sleep(1.0)
            try:
                from modules.audio import read_last_decision_file as _rld
                _ad = _rld()
            except Exception:
                _ad = {}
            new_out = _ad.get("effective") or svc.get_status().get("audio_effective") or mode
            sink = _ad.get("sink") or ""
            reason = _ad.get("reason") or ""
            ok = new_out == mode or (mode == "auto" and new_out not in ("none", "", "–"))
            if ok:
                fmt.out("Audio-Ausgang: " + fmt.GREEN + new_out + " ✓" + fmt.RESET)
                if sink:
                    fmt.out("  Sink: " + sink[:60])
                if mode == "usb_gadget":
                    fmt.out("  Hinweis: BMW-Ton über ESP/PUMP — Bridge muss laufen")
            else:
                fmt.out(fmt.RED + f"Audio-Ausgang: {mode} fehlgeschlagen" + fmt.RESET)
                if reason:
                    fmt.out("  Grund: " + reason)
                if mode == "bt":
                    fmt.out("  Tipp: pidrivectl bt connect <MAC>  dann erneut versuchen")
            sys.exit(EXIT_OK)
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
                    # A2DP-Sink suchen (PipeWire: bluez_output.* / Legacy: bluez_sink.*)
                    mac_u = mac.replace(":", "_")
                    bt_sinks = [
                        ln.split()[1] for ln in sinks_out.splitlines()
                        if ln.split() and (
                            "bluez_output" in ln or
                            ("bluez_sink" in ln and "a2dp" in ln)
                        ) and mac_u in ln.replace("-", "_").upper()
                    ]
                    if not bt_sinks:
                        bt_sinks = [
                            ln.split()[1] for ln in sinks_out.splitlines()
                            if ln.split() and (
                                "bluez_output" in ln or
                                ("bluez_sink" in ln and "a2dp" in ln)
                            )
                        ]
                    if bt_sinks:
                        fmt.out(OK + f"   A2DP-Sink: {bt_sinks[0]}")
                    else:
                        fmt.out(NOK + f"   Kein A2DP-Sink in PA")
                        fmt.out(f"     → Erwartet: bluez_output.{mac_u}.* oder bluez_sink.{mac_u}.a2dp_sink")
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

    # usb / ESP
    if args.cmd == "usb":
        if not args.usb_cmd or args.usb_cmd == "status":
            d = svc.get_status()
            usb = d.get("usb") or {}
            if use_json:
                fmt.print_json(usb)
            else:
                if usb.get("online"):
                    fmt.out(fmt.GREEN + "ESP: online" + fmt.RESET + (f"  FW {usb.get('fw')}" if usb.get("fw") else ""))
                else:
                    fmt.out("ESP: offline")
                fmt.out(
                    f"  OTG {'●' if usb.get('otg_up') else '○'}  "
                    f"PUMP {'●' if usb.get('pump_up') else '○'}  "
                    f"UART {'●' if usb.get('uart_up') else '○'}  "
                    f"MSC {'●' if usb.get('msc_ready') else '○'}"
                )
                if usb.get("serial_ports"):
                    fmt.out("  Serial: " + ", ".join(usb.get("serial_ports")[:4]))
                if usb.get("esp_host"):
                    fmt.out(f"  Host:   {usb.get('esp_host')}")
                if usb.get("playing_name"):
                    fmt.out(f"  Play:   {usb.get('playing_name')}")
                if usb.get("stream_cap"):
                    fmt.out(
                        f"  Stream: {usb.get('stream_bytes', 0)}/{usb.get('stream_cap')} B"
                        f"  ID3 {usb.get('id3_len', 0)} B"
                    )
                if usb.get("age_s") is not None:
                    fmt.out(f"  Age:    {usb.get('age_s')} s")
                if not usb:
                    fmt.out("  (kein usb-Status — usb_pump_client starten)")
            sys.exit(EXIT_OK)
        if args.usb_cmd == "probe":
            try:
                from integration.usb_pump_client import poll_once
                snap = poll_once(try_uart=False)
            except Exception as e:
                _exit_err(str(e))
            if use_json:
                fmt.print_json(snap)
            else:
                fmt.out("Probe geschrieben → /tmp/pidrive_usb_status.json")
                fmt.out(
                    ("online" if snap.get("online") else "offline")
                    + f"  http={snap.get('http_ok')} serial={snap.get('serial_present')}"
                    + (f"  fw={snap.get('fw')}" if snap.get("fw") else "")
                )
            sys.exit(EXIT_OK if snap.get("online") else EXIT_ERROR)

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

        BANDS = ["pmr446","freenet","lpd433","vhf","uhf","cb","fm","airband"]

        if sc_cmd is None or sc_cmd == "status":
            # scanner / scanner status
            r = svc.get_status()
            sc = r.get("scanner") or {}
            if not isinstance(sc, dict):
                sc = {}
            active = sc.get("active") or str(r.get("radio_type", "")).upper() == "SCANNER"
            if active:
                fmt.out(f"Scanner aktiv: Band={sc.get('band') or r.get('scanner_band','?')}  "
                        f"Freq={sc.get('freq','?')} MHz  Name={sc.get('name') or r.get('radio_name','?')}")
                fmt.out(f"  Squelch={sc.get('squelch', r.get('scanner_squelch', '?'))}  "
                        f"bw={sc.get('bandwidth_hz','?')} Hz  -s={sc.get('sample_rate','?')}")
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

        if sc_cmd == "monitor":
            mon = getattr(args, "mon_action", None) or "status"
            if mon == "start":
                # Setting + Start-Trigger
                try:
                    from settings import load_settings as _ls, save_settings as _ss
                    _s = _ls()
                    _s["scanner_pmr_autotune"] = not bool(getattr(args, "no_tune", False))
                    if getattr(args, "hold", None) is not None:
                        _s["scanner_pmr_hold_s"] = float(args.hold)
                    if getattr(args, "trigger_on", None) is not None:
                        _s["scanner_pmr_trigger_on_db"] = float(args.trigger_on)
                    if getattr(args, "trigger_off", None) is not None:
                        _s["scanner_pmr_trigger_off_db"] = float(args.trigger_off)
                    if getattr(args, "watch", None) is not None:
                        _s["scanner_pmr_watch_s"] = float(args.watch)
                    _ss(_s)
                except Exception as e:
                    fmt.err(f"Settings: {e}")
                svc.send("pmr_monitor_start")
                fmt.out("  PMR-Monitor gestartet (Log: /var/log/pidrive/pmr_monitor.jsonl)")
                sys.exit(EXIT_OK)
            if mon == "stop":
                svc.send("pmr_monitor_stop")
                fmt.out("  PMR-Monitor gestoppt")
                sys.exit(EXIT_OK)
            if mon == "log":
                n = int(getattr(args, "n", 40) or 40)
                path = "/var/log/pidrive/pmr_monitor.jsonl"
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in lines[-n:]:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            import json as _j
                            ev = _j.loads(line)
                            if ev.get("event") == "activity":
                                fmt.out(
                                    f"  {ev.get('ts','?')}  K{ev.get('ch','?')}  "
                                    f"+{ev.get('relative_db','?')} dB  "
                                    f"score={ev.get('score','?')}  "
                                    f"{ev.get('freq_mhz','?')} MHz  → {ev.get('action','')}"
                                )
                            else:
                                fmt.out(f"  {ev.get('ts','?')}  {ev.get('event')}  { {k:v for k,v in ev.items() if k not in ('ts','event','candidates')} }")
                        except Exception:
                            fmt.out("  " + line[:160])
                except FileNotFoundError:
                    fmt.out("  (noch kein Log)")
                except Exception as e:
                    fmt.err(str(e))
                sys.exit(EXIT_OK)
            # status
            try:
                import json as _j
                st = {}
                try:
                    st = _j.loads(open("/tmp/pidrive_pmr_monitor.json").read())
                except Exception:
                    pass
                if st.get("running"):
                    fmt.out(
                        f"  PMR-Monitor: AKTIV  band={st.get('band')}  "
                        f"autotune={st.get('autotune')}  "
                        f"state={st.get('monitor_effective_state', '?')}  "
                        f"cycles={st.get('cycles')}  hits={st.get('hits')}"
                    )
                    fmt.out(
                        f"  Trigger: on={st.get('trigger_on_db')} dB  "
                        f"off={st.get('trigger_off_db')} dB  "
                        f"peek={st.get('peek_count')}  "
                        f"activity={st.get('activity_count')}"
                    )
                    if st.get("last_peek_ch") is not None:
                        fmt.out(
                            f"  Peek: K{st.get('last_peek_ch')}  "
                            f"+{st.get('last_peek_relative_db')} dB"
                        )
                    if st.get("last_ch") is not None:
                        fmt.out(
                            f"  Zuletzt Hit: K{st.get('last_ch')}  "
                            f"+{st.get('last_relative_db')} dB  "
                            f"({st.get('last_event')})"
                        )
                    else:
                        fmt.out(f"  Zustand: {st.get('last_event', '?')}")
                    if st.get("capture_error_count"):
                        fmt.out(
                            f"  Errors: {st.get('capture_error_count')}  "
                            f"streak={st.get('capture_error_streak')}  "
                            f"class={st.get('last_error_class') or '-'}  "
                            f"usb_reset={st.get('usb_reset_count')}"
                        )
                    if st.get("last_detect_latency_ms") is not None:
                        fmt.out(
                            f"  Latenz: detect={st.get('last_detect_latency_ms')} ms  "
                            f"tune={st.get('last_tune_latency_ms')} ms  "
                            f"e2e={st.get('last_end_to_end_latency_ms')} ms"
                        )
                    fmt.out(f"  Log: {st.get('log_path', '/var/log/pidrive/pmr_monitor.jsonl')}")
                else:
                    fmt.out("  PMR-Monitor: inaktiv")
                    if st:
                        fmt.out(
                            f"  Letzter Lauf: hits={st.get('hits')}  "
                            f"peek={st.get('peek_count')}  "
                            f"cycles={st.get('cycles')}  event={st.get('last_event')}"
                        )
            except Exception as e:
                fmt.err(str(e))
            sys.exit(EXIT_OK)

        # Band-Kommandos: sc_cmd ist das Band
        band = sc_cmd
        if band in BANDS:
            if sc_action == "scan":
                verbose = bool(getattr(args, "verbose", False))
                if use_json:
                    fmt.print_json(svc.send(f"scan_next:{band}"))
                else:
                    fmt.out(f"  Scanner {band}: suche aktiven Kanal …")
                    if verbose:
                        fmt.out("  (--verbose: Core-Log parallel: journalctl -fu pidrive_core)")
                    def _sc_tick(elapsed, total):
                        print(f"  … scanne {band}  {elapsed}s", end="\r", flush=True)
                    res = svc.watch_scanner_scan(band, on_tick=_sc_tick)
                    print()  # Zeilenumbruch nach Fortschritt
                    st = res.get("status")
                    if st == "found":
                        _fr  = res.get("freq")
                        _frs = f"  ({_fr} MHz)" if _fr else ""
                        fmt.out(f"  ✓ Aktiver Kanal: {res.get('name','?')}{_frs} — gewechselt")
                        # Nach Treffer Statusfelder zeigen
                        try:
                            sc = svc.get_status().get("scanner") or {}
                            if sc:
                                fmt.out(f"  Status: bw={sc.get('bandwidth_hz')} Hz  -s={sc.get('sample_rate')}  "
                                        f"sq={sc.get('squelch')}")
                        except Exception:
                            pass
                    elif st == "none":
                        fmt.out("  ✗ Kein aktiver Kanal gefunden")
                    else:
                        fmt.out("  ⏳ Scan läuft noch — Status: pidrivectl scanner status")
            elif sc_action == "stop":
                svc.send("scanner_stop")
                fmt.out("  Scanner gestoppt")
            elif sc_action == "list" and band == "airband":
                try:
                    from modules.radio import scanner as _sc
                    chs = _sc.load_airband_stations()
                    if use_json:
                        fmt.print_json({"ok": True, "stations": chs})
                    else:
                        fmt.out(f"  Airband-Presets ({len(chs)}):")
                        for ch in chs:
                            fmt.out(
                                f"    K{ch['ch']:02d}  {ch['freq']:7.3f} MHz  {ch['name']}"
                            )
                        fmt.out("  Datei: pidrive/config/airband_stations.json")
                except Exception as e:
                    fmt.err(str(e))
                    sys.exit(EXIT_ERROR)
                sys.exit(EXIT_OK)
            elif sc_action == "monitor" and band == "airband":
                air_act = getattr(args, "air_mon_action", None)
                if air_act == "start":
                    try:
                        from settings import load_settings as _ls, save_settings as _ss
                        s = _ls()
                        if getattr(args, "no_tune", False):
                            s["scanner_airband_autotune"] = False
                        else:
                            s["scanner_airband_autotune"] = True
                        if getattr(args, "hold", None) is not None:
                            s["scanner_airband_hold_s"] = float(args.hold)
                        _ss(s)
                    except Exception as e:
                        fmt.err(str(e))
                    svc.send("airband_monitor_start")
                    fmt.out("  Airband-Monitor gestartet")
                elif air_act == "stop":
                    svc.send("airband_monitor_stop")
                    fmt.out("  Airband-Monitor gestoppt")
                elif air_act == "status":
                    try:
                        import json as _j
                        st = _j.loads(open("/tmp/pidrive_airband_monitor.json").read())
                    except Exception:
                        st = {"running": False}
                    if use_json:
                        fmt.print_json({"ok": True, "status": st})
                    else:
                        run = bool(st.get("running"))
                        fmt.out(f"  Airband-Monitor: {'läuft' if run else 'aus'}")
                        if st:
                            fmt.out(
                                f"  cycles={st.get('cycles')}  hits={st.get('hits')}  "
                                f"event={st.get('last_event')}  "
                                f"last={st.get('last_name') or '-'}"
                            )
                else:
                    fmt.err("Nutze: scanner airband monitor start|stop|status")
                    sys.exit(EXIT_USAGE)
                sys.exit(EXIT_OK)
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
                fmt.err(f"Unbekannte Aktion. Nutze: scan | ch N | freq F | next | prev | stop"
                        + (" | list | monitor" if band == "airband" else ""))
            sys.exit(EXIT_OK)
        sys.exit(EXIT_OK)

    # update (GitHub OTA)
    if args.cmd == "update":
        from modules import update as _upd
        info = _upd.check_for_update(fetch=True)
        if use_json:
            fmt.print_json(info)
            if not info.get("ok"):
                sys.exit(EXIT_ERROR)
            if getattr(args, "check", False) or not info.get("available"):
                sys.exit(EXIT_OK)
            # --json + apply nur mit --yes
            if not getattr(args, "yes", False):
                fmt.err("JSON-Modus: Update einspielen braucht --yes")
                sys.exit(EXIT_USAGE)
            res = _upd.apply_update(restart=True)
            fmt.print_json(res)
            sys.exit(EXIT_OK if res.get("ok") else EXIT_ERROR)

        if not info.get("ok"):
            fmt.err(info.get("error") or "Update-Prüfung fehlgeschlagen")
            sys.exit(EXIT_ERROR)

        lv = info.get("local_version", "?")
        rv = info.get("remote_version") or "?"
        lc = info.get("local_commit", "?")
        rc = info.get("remote_commit") or "?"
        fmt.out(f"PiDrive Update — {info.get('install_dir')}")
        fmt.out(f"  Lokal:  v{lv}  ({lc})")
        fmt.out(f"  GitHub: v{rv}  ({rc})  [origin/{info.get('branch','main')}]")

        if info.get("ahead", 0) > 0:
            fmt.out(f"  ⚠ Lokal {info['ahead']} Commit(s) voraus (werden bei Update verworfen)")

        if not info.get("available"):
            fmt.out("  ✓ Bereits aktuell — kein Update nötig")
            sys.exit(EXIT_OK)

        fmt.out(f"  → Update verfügbar ({info.get('behind', '?')} Commit(s) hinterher)")
        for line in (info.get("commits") or [])[:12]:
            fmt.out(f"      {line}")
        if len(info.get("commits") or []) > 12:
            fmt.out("      …")

        if getattr(args, "check", False):
            sys.exit(EXIT_OK)

        if not getattr(args, "yes", False):
            try:
                ans = input("Update jetzt einspielen und Services neu starten? [j/N] ").strip().lower()
            except EOFError:
                ans = ""
            if ans not in ("j", "ja", "y", "yes"):
                fmt.out("Abgebrochen.")
                sys.exit(EXIT_OK)

        fmt.out("Spiele Update ein…")
        res = _upd.apply_update(restart=True)
        if not res.get("ok"):
            fmt.err(res.get("error") or "Update fehlgeschlagen")
            sys.exit(EXIT_ERROR)
        fmt.out(f"✓ Update ok: v{res.get('before_version')} → v{res.get('after_version')}  "
                f"({res.get('before_commit')} → {res.get('after_commit')})")
        fmt.out("  Services neu gestartet (pidrive_core / pidrive_web)")
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

    # menu
    if args.cmd == "menu":
        from menu import menu_golden as _mg
        mc = getattr(args, "menu_cmd", None)
        if not mc:
            fmt.err("Unterbefehl fehlt: snapshot|verify|lint|walk|cost|report|tree|goto|activate|path|rebuild")
            sys.exit(EXIT_USAGE)
        if mc == "snapshot":
            sys.exit(_mg.cmd_snapshot(accept=getattr(args, "accept", False)))
        elif mc == "verify":
            sys.exit(_mg.cmd_verify())
        elif mc == "lint":
            sys.exit(_mg.cmd_lint())
        elif mc == "walk":
            sys.exit(_mg.cmd_walk())
        elif mc == "cost":
            sys.exit(_mg.cmd_cost(args.path_id))
        elif mc == "report":
            sys.exit(_mg.cmd_report(write_doc=getattr(args, "write_doc", False)))
        elif mc == "tree":
            sys.exit(_mg.cmd_tree(as_json=getattr(args, "json", False),
                                  depth=getattr(args, "depth", 0) or 0))
        elif mc == "goto":
            sys.exit(_mg.cmd_goto(args.path_id))
        elif mc == "activate":
            sys.exit(_mg.cmd_activate(args.uid))
        elif mc == "path":
            sys.exit(_mg.cmd_path())
        elif mc == "rebuild":
            sys.exit(_mg.cmd_rebuild_test())
        sys.exit(EXIT_USAGE)

    # webui (W0/W1 + Live-Smoke)
    if args.cmd == "webui":
        from web import webui_check as _wc
        wc = getattr(args, "webui_cmd", None)
        if not wc:
            fmt.err("Unterbefehl fehlt: check|selftest|routes|smoke")
            sys.exit(EXIT_USAGE)
        if wc == "check":
            sys.exit(_wc.run_check())
        elif wc == "selftest":
            sys.exit(_wc.run_selftest())
        elif wc == "routes":
            sys.exit(_wc.cmd_routes())
        elif wc == "smoke":
            import subprocess as _sp_smoke
            mode = getattr(args, "mode", "flows") or "flows"
            base = getattr(args, "base", "http://127.0.0.1:8080") or "http://127.0.0.1:8080"
            script = None
            _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            for cand in (
                os.path.join(os.path.dirname(_root), "tools", "webui_live_smoke.py"),
                os.path.join(_root, "tools", "webui_live_smoke.py"),
                "/home/pidrive/pidrive/tools/webui_live_smoke.py",
            ):
                if os.path.isfile(cand):
                    script = cand
                    break
            if not script:
                fmt.err("tools/webui_live_smoke.py nicht gefunden")
                sys.exit(EXIT_ERROR)
            cmd = ["python3", "-u", script, "--base", base,
                   "--json-out", "/tmp/pidrive_webui_smoke.json"]
            if mode == "quick":
                cmd.append("--quick")
            elif mode == "full":
                cmd.append("--full")
            fmt.out(f"WebUI Live-Smoke mode={mode} base={base}")
            rc = _sp_smoke.call(cmd)
            sys.exit(rc if rc in (0, 1) else EXIT_ERROR)
        sys.exit(EXIT_USAGE)

    # source (W7)
    if args.cmd == "source":
        from modules import source_state as _ss
        sc = getattr(args, "source_cmd", None) or "state"
        import json as _sj
        if sc == "state":
            mem = _ss.snapshot()
            disk = _ss.load_snapshot_file()
            match = _ss.memory_matches_file()
            age = None
            if mem.get("since"):
                import time as _t
                age = round(_t.time() - float(mem["since"]), 1) if mem.get("transition") else None
            out = {
                "source_current": mem.get("source_current"),
                "source_previous": mem.get("source_previous"),
                "transition": mem.get("transition"),
                "in_transition": _ss.in_transition(),
                "owner": mem.get("owner"),
                "source_target": mem.get("source_target"),
                "age_s": age,
                "memory_matches_file": match,
                "file_transition": disk.get("transition"),
                "file_owner": disk.get("owner"),
                "stale_cleared": mem.get("stale_cleared"),
                "transition_count": mem.get("transition_count"),
            }
            if use_json:
                fmt.print_json(out)
            else:
                icon = "✓" if match else "⚠"
                fmt.out(f"{icon} Quelle: {out['source_current']}  (vorher: {out['source_previous']})")
                tr = "JA" if out["in_transition"] else "nein"
                fmt.out(f"  Transition: {tr}  owner={out['owner'] or '–'}  target={out['source_target'] or '–'}")
                if age is not None:
                    fmt.out(f"  Alter: {age}s")
                fmt.out(f"  Speicher↔Datei: {'übereinstimmend' if match else 'ABWEICHEND'}")
                fmt.out(f"  Zähler: transitions={out['transition_count']} stale_cleared={out['stale_cleared']}")
            sys.exit(EXIT_OK)
        elif sc == "history":
            hist = _ss.history(20)
            if use_json:
                fmt.print_json({"history": hist})
            else:
                if not hist:
                    fmt.out("(keine Übergänge)")
                for e in hist:
                    import time as _t
                    ts = e.get("ts")
                    tstr = _t.strftime("%H:%M:%S", _t.localtime(ts)) if ts else "?"
                    fmt.out(
                        f"  {tstr}  {e.get('result','?'):16}  "
                        f"owner={e.get('owner','–')} → {e.get('target','–')}  "
                        f"dt={e.get('duration_s',0)}s"
                        + (f"  blocked_by={e['blocked_by']}" if e.get("blocked_by") else "")
                    )
            sys.exit(EXIT_OK)
        fmt.err("Unterbefehl fehlt: state|history")
        sys.exit(EXIT_USAGE)

    # idrive
    if args.cmd == "idrive":
        from menu import idrive_sim as _id
        offline = getattr(args, "offline", False)
        cmd = getattr(args, "idrive_cmd", None)
        arg = getattr(args, "idrive_arg", None)
        if not cmd:
            fmt.err("Nutzung: pidrivectl idrive <next|play|…> | script <datei> [--offline]")
            sys.exit(EXIT_USAGE)
        if cmd == "script":
            if not arg:
                fmt.err("Skript-Datei fehlt")
                sys.exit(EXIT_USAGE)
            sys.exit(_id.run_script(arg, offline=offline,
                                    settle=getattr(args, "settle", 0.35)))
        if cmd == "event":
            if not arg:
                fmt.err("Event-Name fehlt")
                sys.exit(EXIT_USAGE)
            sys.exit(_id.cmd_event(arg, offline=offline))
        # Kurzform: pidrivectl idrive next
        sys.exit(_id.cmd_event(cmd, offline=offline))

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
        elif cmd == "menu":     _ts.test_menu()
        elif cmd == "webui":    _ts.test_webui()
        sys.exit(EXIT_OK)

    if args.cmd == "debug":
        dbg = getattr(args, "dbg_cmd", None)
        import json as _dj

        def _dump(data):
            if use_json:
                fmt.print_json(data)
            else:
                fmt.out(_dj.dumps(data, indent=2, ensure_ascii=False))

        if dbg == "state" or dbg is None:
            _dump(svc.debug_state())
        elif dbg == "dab":
            _dump(svc.dab_status().get("data", {}))
        elif dbg == "bt":
            _dump({
                "known": svc.bt_known(),
                "discovered": svc.bt_discovered(),
                "status": svc.get_status(),
            })
        elif dbg == "audio":
            try:
                from web.shared.audio import get_audio_debug
                _dump(get_audio_debug())
            except Exception as e:
                _dump({"error": str(e)})
        elif dbg == "menu":
            _dump(svc.ipc.read_json("/tmp/pidrive_menu.json", {}))
        elif dbg == "source-state":
            _dump(svc.ipc.read_json(SOURCE_STATE_FILE, {}))
        elif dbg == "avrcp":
            try:
                _dump(svc.ipc.read_json("/tmp/pidrive_avrcp_events.json", {}))
            except Exception as e:
                _dump({"error": str(e)})
        elif dbg == "inject":
            trig = getattr(args, "trigger", None)
            if not trig:
                _exit_err("Trigger fehlt — z.B. pidrivectl debug inject next", EXIT_NOTFOUND)
            svc.require_online()
            svc.send(trig)
            fmt.out(f"✓ Trigger injiziert: {trig}")
        elif dbg == "mpris":
            _run_debug_mpris(args, fmt, use_json)
        else:
            _exit_err(f"Unbekannter debug-Befehl: {dbg}", EXIT_NOTFOUND)
        sys.exit(EXIT_OK)

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
