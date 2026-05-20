"""
modules/webradio.py — Webradio via mpv (PulseAudio)
Aufrufer: main_core.py
Abhängig von: modules/audio.py, modules/source_state.py, ipc.py
Schreibt: settings[last_web_station], settings[last_source]
"""


import subprocess
import json
import os
import time
import ipc
import log

STATIONS_FILE  = os.path.join(os.path.dirname(__file__), "../config/stations.json")
SETTINGS_FILE  = os.path.join(os.path.dirname(__file__), "../config/settings.json")
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
            from settings import save_settings as _save_s
            _save_s(settings)
        except Exception as _e:
            log.warn(f"webradio: save_settings failed: {_e}")

    stop(S)

    url  = station.get("url", "")
    name = station.get("name", "?")
    if not url:
        log.error("webradio: keine URL fuer " + name)
        return False

    try:
        from modules import audio as _audio
        import mpv_meta

        mpv_meta.stop()
        sock = mpv_meta.MPV_SOCKET
        try:
            os.unlink(sock)
        except FileNotFoundError:
            pass

        # PA-Umgebung: System-Daemon + expliziter Sink
        import os as _os
        _mpv_env_dict = _os.environ.copy()
        _mpv_env_dict["PULSE_SERVER"]  = "unix:/var/run/pulse/native"
        _mpv_env_dict["XDG_RUNTIME_DIR"] = "/tmp"

        # Aktiven Sink ermitteln — warte bis zu 5s falls BT noch verbindet
        _target_sink = ""
        try:
            for _attempt in range(5):
                _bt_sink = _audio.get_bt_sink()
                if _bt_sink:
                    _target_sink = _bt_sink
                    break
                _alsa = _audio.get_alsa_sink()
                if _alsa:
                    _target_sink = _alsa
                    break
                import time as _tw; _tw.sleep(1)
            if _target_sink:
                _mpv_env_dict["PULSE_SINK"] = _target_sink
                log.info(f"[WEB] mpv PULSE_SINK={_target_sink}")
            else:
                # Kein expliziter Sink: PA-Default verwenden falls irgendein Sink da
                # (HDMI, Klinke, etc.) — sonst früh abbrechen
                import subprocess as _pchk
                _sinks_out = _pchk.run(
                    ["pactl", "list", "short", "sinks"],
                    capture_output=True, text=True,
                    env={**__import__("os").environ,
                         "PULSE_SERVER": "unix:/var/run/pulse/native"},
                    timeout=3
                ).stdout.strip()
                _has_any_sink = bool(_sinks_out)
                if not _has_any_sink:
                    log.warn("[WEB] Kein PA-Sink verfügbar — mpv-Start abgebrochen")
                    S["radio_playing"] = False
                    source_state.commit_source("idle", auto_end=True)
                    return False
                log.warn("[WEB] Kein expliziter PA-Sink — nutze PA-Default-Routing")
        except Exception as _se:
            log.warn(f"[WEB] Sink-Ermittlung: {_se}")

        mpv_args = ["--ao=pulse"]


        # Popen(list) + explizitem env — IPC-Socket wird zuverlässig erstellt
        _bt_sink_for_cmd = _target_sink
        _pa_device_arg = (f"--audio-device=pulse/{_bt_sink_for_cmd}"
                          if _bt_sink_for_cmd else "")
        _mpv_cmd = [
            "mpv", "--no-video", "--no-terminal",
            "--title=pidrive_radio",
            f"--input-ipc-server={sock}",
            "--ao=pulse",
        ]
        if _pa_device_arg:
            _mpv_cmd.append(_pa_device_arg)
        _mpv_cmd.append(url)
        _mpv_env = _mpv_env_dict.copy()
        _mpv_env["PULSE_SERVER"]    = "unix:/var/run/pulse/native"
        _mpv_env["XDG_RUNTIME_DIR"] = "/tmp"
        if _bt_sink_for_cmd:
            _mpv_env["PULSE_SINK"] = _bt_sink_for_cmd
        log.info(f"[WEB] mpv: url={url[:60]!r} sink={_bt_sink_for_cmd or chr(40)+chr(41)}")
        _player_proc = subprocess.Popen(
            _mpv_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=_mpv_env,
        )

        S["track"]         = ""
        S["artist"]        = ""
        S["album"]         = ""
        S["radio_playing"] = True
        S["radio_type"]    = "WEB"
        # metadata_unavailable Kette:
        #   webradio.py   → S["metadata_unavailable"] = True/False
        #   mpv_meta.py   → S["metadata_unavailable"] = False bei Socket-Verbindung
        #   ipc.py        → exportiert als status.json "metadata_unavailable"
        #   renderRuntimeInfo (index.html) → el('metaStatus').textContent
        S["metadata_unavailable"] = True   # initial — False wenn mpv stabil + Socket OK
        S["control_context"] = "radio_web"  # Phase 2 state
        S["radio_station"] = name
        S["radio_name"]    = name

        # v0.8.19: Boot-Resume — letzte Webradio-Station speichern
        try:
            if settings is not None:
                settings["last_source"]      = "webradio"
                settings["last_web_station"] = {"name": name, "url": url,
                                                "genre": station.get("genre", "")}
                from settings import save_settings
                save_settings(settings)
        except Exception:
            pass

        log.info(f"[WEB] mpv gestartet PID={_player_proc.pid} socket={sock}")
        # Zombie-Check: 5s warten (URL-Redirect + Buffer-Init + PA-Connect)
        import time as _t
        _t.sleep(5.0)
        if _player_proc.poll() is not None:
            rc = _player_proc.returncode
            S["radio_playing"] = False
            S["metadata_unavailable"] = True
            # mpv stderr lesen
            _mpv_err = ""
            try:
                _mpv_err = (_player_proc.stderr.read() or b"").decode("utf-8","replace").strip()[-300:]
            except Exception:
                pass
            if rc == -15:
                log.error(f"[WEB] mpv SIGTERM nach 5s — PA-Verbindung prüfen")
            else:
                log.error(f"[WEB] mpv rc={rc} nach 5s")
            log.error(f"  URL: {url[:80]!r}")
            if _mpv_err:
                log.error(f"  mpv stderr: {_mpv_err[:200]}")
            else:
                log.error(f"  (kein mpv stderr — PA erreichbar? pidrivectl audio test)")
            return False
        # Hintergrund-Monitor: prüft mpv alle 10s auf Lebenzeichen
        import threading as _thr
        def _mpv_watchdog(proc, state, station_name):
            for _ in range(18):   # 18 × 10s = 3min max
                _t.sleep(10.0)
                if proc.poll() is not None:
                    if state.get("radio_type") == "WEB" and state.get("radio_name") == station_name:
                        state["radio_playing"] = False
                        state["metadata_unavailable"] = True
                        log.warn(f"[WEB] mpv PID={proc.pid} beendet — stream abgebrochen name={station_name!r}")
                    break
        _thr.Thread(target=_mpv_watchdog, args=(_player_proc, S, name), daemon=True).start()
        S["metadata_unavailable"] = False
        mpv_meta.start(name, S, sock)
        log.action("WEB", f"Wiedergabe: {name}")
        return True

    except FileNotFoundError:
        S["radio_playing"] = False
        return False
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
