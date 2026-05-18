#!/usr/bin/env python3
"""
mpris2.py - PiDrive MPRIS2 D-Bus Interface v0.7.10

Zwei Aufgaben:
1. SENDET Trackinfo ans BMW-Display (Sendername, Titel, Artist im iDrive)
2. EMPFÄNGT Steuerbefehle vom BMW iDrive (NEXT/PREV/PLAY/PAUSE/STOP)

BMW NBT EVO erkennt MPRIS2 automatisch wenn Pi als BT-Gerät verbunden ist.
Das iDrive zeigt dann Sendernamen und Titel wie bei einem echten iPod/Phone.

AVRCP 1.4 Kompatibilität: BlueZ setzt Version automatisch.
Optimale Kompatibilität Pi 3B + BMW NBT EVO: Version = 0x0105 (AVRCP 1.5)
"""

import os
import sys
import time
import json
import signal
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import log
import ipc

try:
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib
    DBUS_OK = True
except ImportError:
    DBUS_OK = False

# D-Bus Interfaces
MPRIS2_IFACE    = "org.mpris.MediaPlayer2"
PLAYER_IFACE    = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE     = "org.freedesktop.DBus.Properties"
SERVICE_NAME    = "org.mpris.MediaPlayer2.pidrive"


class PiDrivePlayer(dbus.service.Object):
    """
    MPRIS2 Player Interface.
    BMW NBT EVO erkennt diesen Service und zeigt Metadaten im iDrive-Display.
    """

    def __init__(self, bus, cmd_callback):
        dbus.service.Object.__init__(self, bus,
                                     "/org/mpris/MediaPlayer2")
        self._cmd_callback = cmd_callback
        self._metadata     = {}
        self._status       = "Playing"
        self._volume        = 1.0
        self._lock          = threading.Lock()

    def update_metadata(self, title: str, artist: str, album: str,
                        track_nr: int = 1, total: int = 1,
                        genre: str = ""):
        """Neue Metadaten setzen und ans BMW-Display senden.
        Rate-Limiting: max 1 PropertiesChanged pro 300ms (BMW-Stabilität).
        """
        import time as _time
        _now = _time.monotonic()
        # Track-ID hat gewechselt → immer sofort senden (TrackChanged Event)
        _track_changed = (track_nr != self._last_trackid)
        # Rate-Limit: max alle 300ms — verhindert Notification-Overflow im BMW
        if not _track_changed and (_now - self._last_emit) < 0.3:
            return
        self._last_emit    = _now
        self._last_trackid = track_nr

        with self._lock:
            self._metadata = dbus.Dictionary({
                "mpris:trackid":  dbus.ObjectPath(
                    f"/org/mpris/MediaPlayer2/Track/{track_nr}"),
                "mpris:length":   dbus.Int64(0),
                "xesam:title":    dbus.String(title[:64]),
                "xesam:artist":   dbus.Array([dbus.String(artist[:64])],
                                             signature="s"),
                "xesam:album":    dbus.String(album[:64]),
                "xesam:trackNumber": dbus.Int32(track_nr),
                "xesam:genre":    dbus.Array([dbus.String(genre[:32])],
                                             signature="s"),
                "xesam:url":      dbus.String(""),
            }, signature="sv")

        # Bei Track-Wechsel: kurz "Stopped" → dann neue Metadaten
        # Das hilft BMW das TrackChanged-Event korrekt zu verarbeiten
        if _track_changed:
            try:
                self.PropertiesChanged(
                    PLAYER_IFACE,
                    {"PlaybackStatus": dbus.String("Stopped")},
                    []
                )
            except Exception:
                pass

        # PropertiesChanged Signal → BMW-Display aktualisiert sich
        try:
            self.PropertiesChanged(
                PLAYER_IFACE,
                {"Metadata": self._metadata,
                 "PlaybackStatus": dbus.String(self._status)},
                []
            )
            log.info(f"MPRIS2: {title!r} | {artist!r} → BMW-Display")
        except Exception as e:
            log.warn(f"MPRIS2 PropertiesChanged: {e}")

    def set_status(self, playing: bool):
        self._status = "Playing" if playing else "Paused"
        try:
            self.PropertiesChanged(
                PLAYER_IFACE,
                {"PlaybackStatus": dbus.String(self._status)},
                []
            )
        except Exception:
            pass

    # ── MPRIS2 Root Interface ────────────────────────────────────────
    @dbus.service.method(MPRIS2_IFACE)
    def Raise(self): pass

    @dbus.service.method(MPRIS2_IFACE)
    def Quit(self): pass

    def _get_prop(self, interface, prop):
        """Einzelne MPRIS2-Property zurückgeben (von Get() genutzt)."""
        props = self.GetAll(interface)
        return props.get(prop)

    @dbus.service.method(PROPS_IFACE,
                         in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self._get_prop(interface, prop)

    @dbus.service.method(PROPS_IFACE,
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == MPRIS2_IFACE:
            return {
                "CanQuit":          dbus.Boolean(False),
                "CanRaise":         dbus.Boolean(False),
                "HasTrackList":     dbus.Boolean(False),
                "Identity":         dbus.String("PiDrive"),
                "SupportedUriSchemes": dbus.Array([], signature="s"),
                "SupportedMimeTypes":  dbus.Array([], signature="s"),
            }
        elif interface == PLAYER_IFACE:
            return {
                "PlaybackStatus": dbus.String(self._status),
                "LoopStatus":     dbus.String("None"),
                "Rate":           dbus.Double(1.0),
                "Shuffle":        dbus.Boolean(False),
                "Metadata":       self._metadata,
                "Volume":         dbus.Double(self._volume),
                "Position":       dbus.Int64(0),
                "MinimumRate":    dbus.Double(1.0),
                "MaximumRate":    dbus.Double(1.0),
                "CanGoNext":      dbus.Boolean(True),
                "CanGoPrevious":  dbus.Boolean(True),
                "CanPlay":        dbus.Boolean(True),
                "CanPause":       dbus.Boolean(True),
                "CanSeek":        dbus.Boolean(False),
                "CanControl":     dbus.Boolean(True),
            }
        return {}

    @dbus.service.method(PROPS_IFACE, in_signature="ssv")
    def Set(self, interface, prop, value):
        if interface == PLAYER_IFACE and prop == "Volume":
            self._volume = float(value)

    @dbus.service.signal(PROPS_IFACE,
                         signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    # ── MPRIS2 Player Controls (BMW sendet diese) ────────────────────
    @dbus.service.method(PLAYER_IFACE)
    def Next(self):
        log.info("MPRIS2 ← BMW: Next → down")
        self._cmd_callback("down")

    @dbus.service.method(PLAYER_IFACE)
    def Previous(self):
        log.info("MPRIS2 ← BMW: Previous → up")
        self._cmd_callback("up")

    @dbus.service.method(PLAYER_IFACE)
    def PlayPause(self):
        log.info("MPRIS2 ← BMW: PlayPause → enter")
        self._cmd_callback("enter")

    @dbus.service.method(PLAYER_IFACE)
    def Play(self):
        log.info("MPRIS2 ← BMW: Play → enter")
        self._cmd_callback("enter")

    @dbus.service.method(PLAYER_IFACE)
    def Pause(self):
        log.info("MPRIS2 ← BMW: Pause → enter")
        self._cmd_callback("enter")

    @dbus.service.method(PLAYER_IFACE)
    def Stop(self):
        log.info("MPRIS2 ← BMW: Stop → back")
        self._cmd_callback("back")

    @dbus.service.method(PLAYER_IFACE, in_signature="x")
    def Seek(self, offset): pass

    @dbus.service.method(PLAYER_IFACE, in_signature="ox")
    def SetPosition(self, track_id, position): pass

    @dbus.service.method(PLAYER_IFACE, in_signature="s")
    def OpenUri(self, uri): pass


# ── Globale Player-Instanz ────────────────────────────────────────────────────

_player: PiDrivePlayer | None = None
_loop:   GLib.MainLoop | None = None


def _write_trigger(cmd: str):
    """File-Trigger schreiben (von MPRIS2-Callback)."""
    try:
        with open(ipc.CMD_FILE, "w") as f:
            f.write(cmd.strip() + "\n")
    except Exception as e:
        log.error(f"mpris2 trigger: {e}")


def start_mpris2():
    """MPRIS2 D-Bus Service starten (in eigenem Thread)."""
    global _player, _loop

    if not DBUS_OK:
        log.warn("MPRIS2: dbus-python nicht verfügbar — kein BMW-Display")
        return None

    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        # v0.10.55: SystemBus für root-Systemdienste (SessionBus braucht X11/Display)
        # Fallback auf SessionBus für Desktop-Umgebungen
        try:
            bus = dbus.SystemBus()
        except Exception as _be:
            log.warn(f"MPRIS2: SystemBus nicht verfügbar ({_be}) — SessionBus-Fallback")
            bus = dbus.SessionBus()
        try:
            name = dbus.service.BusName(SERVICE_NAME, bus)
        except Exception as _ne:
            # AccessDenied: D-Bus Policy fehlt → /etc/dbus-1/system.d/pidrive-mpris2.conf
            if "AccessDenied" in str(_ne) or "not allowed to own" in str(_ne):
                log.warn(f"MPRIS2: Service-Name nicht erlaubt (D-Bus Policy fehlt?) — {_ne}")
                log.warn("MPRIS2: Installiere /etc/dbus-1/system.d/pidrive-mpris2.conf und führe 'systemctl reload dbus' aus")
            raise

        _player = PiDrivePlayer(bus, _write_trigger)
        _loop   = GLib.MainLoop()

        t = threading.Thread(target=_loop.run, daemon=True)
        t.start()

        log.info("MPRIS2: D-Bus Service gestartet")
        log.info(f"  Service: {SERVICE_NAME}")
        log.info("  BMW-Display erhält Metadaten automatisch")
        return _player

    except Exception as e:
        log.error(f"MPRIS2 Start: {e}")
        return None


def update(status: dict, menu: dict):
    """
    Status-Daten → MPRIS2 Metadaten → BMW-Display.
    Differenzierte Anzeige je Quelle.
    """
    if _player is None:
        return

    radio_type = (status.get("radio_type", "") or "").upper()
    playing    = (status.get("radio_playing", status.get("radio", False))
                  or status.get("spotify", False)
                  or status.get("library_playing", False))

    title  = "PiDrive"
    artist = ""
    album  = "PiDrive"
    genre  = ""

    # ── Spotify ──────────────────────────────────────────────────────────────
    if status.get("spotify"):
        title  = status.get("track",  status.get("spotify_track",  "")) or "Spotify"
        artist = status.get("artist", status.get("spotify_artist", "")) or "PiDrive"
        album  = status.get("album",  status.get("spotify_album",  "")) or "Spotify Connect"
        genre  = "Streaming"

    # ── Radio ────────────────────────────────────────────────────────────────
    elif status.get("radio_playing", status.get("radio", False)):
        station    = status.get("radio_station", status.get("radio_name", "")) or ""
        radio_name = status.get("radio_name", "") or station

        if radio_type == "FM":
            # BMW zeigt: Titel = Sendername, Artist = Frequenz
            title  = radio_name or "FM Radio"
            artist = station if station != radio_name else "FM Radio"
            album  = "UKW / FM"
            genre  = "FM Radio"

        elif radio_type == "DAB":
            title  = radio_name or station or "DAB+"
            artist = station if station != radio_name else "DAB+"
            album  = "DAB+"
            genre  = "DAB+ Radio"

        elif radio_type == "WEB":
            # Icy-Titel wenn verfügbar: "Interpret - Titel"
            icy = status.get("track", "") or ""
            if " - " in icy:
                parts  = icy.split(" - ", 1)
                title  = parts[1].strip() or radio_name
                artist = parts[0].strip() or radio_name
            else:
                title  = icy or radio_name or "Webradio"
                artist = radio_name or "Webradio"
            album  = radio_name or "Webradio"
            genre  = "Webradio"

        elif radio_type == "SCANNER":
            rs = station or "Scanner"
            title  = radio_name or rs
            # Frequenz als Artist — gut lesbar auf BMW-Display
            if "(" in rs and "mhz" in rs.lower():
                try:
                    artist = rs.split("(")[-1].replace(")", "").strip()
                except Exception:
                    artist = "Scanner"
            else:
                artist = rs
            rs_l = rs.lower()
            if "cb" in rs_l:        album = "CB-Funk"; genre = "CB"
            elif "pmr" in rs_l:     album = "PMR446";  genre = "PMR"
            elif "freenet" in rs_l: album = "Freenet"; genre = "Freenet"
            elif "lpd" in rs_l:     album = "LPD433";  genre = "LPD"
            elif "vhf" in rs_l:     album = "VHF";     genre = "VHF"
            elif "uhf" in rs_l:     album = "UHF";     genre = "UHF"
            elif "fm" in rs_l:      album = "FM";      genre = "FM"
            else:                   album = "Scanner"; genre = "Scanner"

        else:
            title  = station or "Radio"
            artist = "Radio"
            album  = "PiDrive Radio"
            genre  = "Radio"

    # ── Bibliothek ───────────────────────────────────────────────────────────
    elif status.get("library_playing", False):
        title  = status.get("library_track", status.get("lib_track", "")) or "Bibliothek"
        artist = "PiDrive"
        album  = "Bibliothek"

    # ── Menü-Navigation ──────────────────────────────────────────────────────
    else:
        path     = menu.get("path", [])
        cursor   = menu.get("cursor", 0)
        nodes    = menu.get("nodes", [])
        selected = ""
        if isinstance(nodes, list) and nodes and 0 <= cursor < len(nodes):
            try:
                selected = nodes[cursor].get("label", "")
            except Exception:
                pass
        title   = selected or (path[-1] if path else "PiDrive")
        artist  = " › ".join(path[1:]) if len(path) > 1 else "PiDrive"
        album   = "PiDrive Menü"
        playing = False

    _player.set_status(playing)
    _player.update_metadata(title, artist, album, genre=genre)
