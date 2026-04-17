"""
modules/webradio.py - Webradio Modul
PiDrive v0.8.10 - pygame-frei, Altlasten entfernt, load_stations dict-robust
"""

import subprocess
import json
import os
import time
import ipc
import log

STATIONS_FILE = os.path.join(os.path.dirname(__file__), "../config/stations.json")
_player_proc = None


def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def load_stations():
    try:
        with open(STATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("stations", [])
        if isinstance(data, list):
            return data
    except Exception as e:
        log.warn("webradio.load_stations: " + str(e))
    return []


def play_station(station, S, settings=None):
    global _player_proc

    if settings is not None:
        settings["last_web_station"] = station
        try:
            import json as _jw
            with open("/home/pi/pidrive/pidrive/config/settings.json", "w") as _fw:
                _jw.dump(settings, _fw, indent=2)
        except Exception:
            pass

    stop(S)

    url  = station.get("url", "")
    name = station.get("name", "?")
    if not url:
        log.error("webradio: keine URL fuer " + name)
        return

    try:
        from modules import audio as _audio
        import mpv_meta

        mpv_args = _audio.get_mpv_args(settings, source="webradio")

        # Strict Mode: abbrechen wenn PulseAudio inaktiv
        _adec = _audio.get_last_decision()
        if _adec.get("reason") == "pulseaudio_inactive" or _adec.get("effective") == "none":
            S["radio_playing"] = False
            S["radio_station"] = "Audiofehler: PulseAudio inaktiv"
            S["radio_name"]    = name
            S["radio_type"]    = "WEB"
            log.error(f"WEB strict-mode: Abbruch name={name!r} reason={_adec.get('reason','?')}")
            return
        mpv_meta.stop()
        sock = mpv_meta.MPV_SOCKET
        try:
            os.unlink(sock)
        except FileNotFoundError:
            pass

        _player_proc = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet",
             "--title=pidrive_radio",
             "--input-ipc-server=" + sock] + mpv_args + [url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        S["track"]         = ""
        S["artist"]        = ""
        S["album"]         = ""
        S["radio_playing"] = True
        S["radio_type"]    = "WEB"
        S["radio_station"] = name
        S["radio_name"]    = name

        mpv_meta.start(name, S, sock)
        log.action("WEB", f"Wiedergabe: {name}")

    except FileNotFoundError:
        S["radio_playing"] = False
        S["radio_station"] = "mpv fehlt!"
    except Exception as e:
        log.error("webradio.play_station: " + str(e))


def stop(S):
    global _player_proc
    try:
        import mpv_meta
        mpv_meta.stop()
    except Exception:
        pass
    _bg("pkill -f pidrive_radio 2>/dev/null")
    if _player_proc:
        try:
            _player_proc.terminate()
        except Exception:
            pass
        _player_proc = None
    if S.get("radio_type") == "WEB":
        S["radio_playing"] = False
        S["radio_station"] = ""
        S["radio_name"]    = ""
        S["track"]         = ""
        S["artist"]        = ""
        S["album"]         = ""
