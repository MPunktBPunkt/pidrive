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
                        track_nr: int = 1, total: int = 1):
        """Neue Metadaten setzen und ans BMW-Display senden."""
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
            }, signature="sv")

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
        bus  = dbus.SessionBus()
        name = dbus.service.BusName(SERVICE_NAME, bus)

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

    # ── Spotify ──────────────────────────────────────────────────────────────
    if status.get("spotify"):
        title  = status.get("track",  status.get("spotify_track",  "")) or "Spotify"
        artist = status.get("artist", status.get("spotify_artist", "")) or "PiDrive"
        album  = status.get("album",  status.get("spotify_album",  "")) or "Spotify Connect"

    # ── Radio ────────────────────────────────────────────────────────────────
    elif status.get("radio_playing", status.get("radio", False)):
        station    = status.get("radio_station", status.get("radio_name", "")) or ""
        radio_name = status.get("radio_name", "") or station

        if radio_type == "FM":
            title  = radio_name or "FM Radio"
            # Frequenz aus station extrahieren wenn vorhanden, z.B. "Bayern 3 (95.8 MHz)"
            artist = "FM Radio"
            if "(" in station and "mhz" in station.lower():
                try:
                    artist = station.split("(")[-1].replace(")", "").strip()
                except Exception:
                    pass
            album  = "FM Radio"

        elif radio_type == "DAB":
            title  = radio_name or station or "DAB+"
            artist = "DAB+"
            album  = "PiDrive DAB+"

        elif radio_type == "WEB":
            title  = status.get("track", "") or radio_name or "Webradio"
            artist = status.get("artist", "") or radio_name or "Webradio"
            album  = radio_name or "PiDrive Webradio"

        elif radio_type == "SCANNER":
            rs = station or "Scanner"
            title  = radio_name or rs
            freq_txt = ""
            if "(" in rs and "mhz" in rs.lower():
                try:
                    freq_txt = rs.split("(")[-1].replace(")", "").strip()
                except Exception:
                    pass
            artist = freq_txt or "Scanner"
            rs_l   = rs.lower()
            if "cb" in rs_l:        album = "Scanner / CB-Funk"
            elif "pmr" in rs_l:     album = "Scanner / PMR446"
            elif "freenet" in rs_l: album = "Scanner / Freenet"
            elif "lpd" in rs_l:     album = "Scanner / LPD433"
            elif "vhf" in rs_l:     album = "Scanner / VHF"
            elif "uhf" in rs_l:     album = "Scanner / UHF"
            else:                   album = "Scanner"

        else:
            title  = station or "Radio"
            artist = "Radio"
            album  = "PiDrive Radio"

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
    _player.update_metadata(title, artist, album)
