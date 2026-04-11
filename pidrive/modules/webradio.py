"""
modules/webradio.py - Webradio Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, json, os, time, ipc
from ui import Item

STATIONS_FILE = os.path.join(os.path.dirname(__file__), "../config/stations.json")
_player_proc = None

def _bg(cmd):
    try: subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def load_stations():
    try:
        with open(STATIONS_FILE) as f: return json.load(f)
    except: return []

def play_station(station, S):
    global _player_proc
    stop(S)
    url = station.get("url","")
    if not url:
        import log; log.error(f"webradio: keine URL für {station.get('name','?')}")
        return
    try:
        _player_proc = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet",
             "--audio-device=alsa/hw:1,0",   # explizit ALSA hw:1,0
             "--title=pidrive_radio", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        S["radio_playing"] = True; S["radio_type"] = "WEB"; S["radio_station"] = station["name"]
    except FileNotFoundError:
        S["radio_playing"] = False; S["radio_station"] = "mpv fehlt!"

def stop(S):
    global _player_proc
    _bg("pkill -f pidrive_radio 2>/dev/null")
    if _player_proc:
        try: _player_proc.terminate()
        except: pass
        _player_proc = None
    S["radio_playing"] = False; S["radio_station"] = ""

def build_items(screen, S):
    stations = load_stations()

    def select_station():
        names = [f"{st['name']} ({st['genre']})" for st in stations]
        if not names:
            ipc.write_progress("Webradio", "Keine Stationen konfiguriert", color="orange")
            time.sleep(2); ipc.clear_progress(); return
        chosen = ipc.headless_pick("Stationen", names)
        if chosen:
            idx = names.index(chosen)
            ipc.write_progress("Webradio", f"Lade: {stations[idx]['name']}...", color="blue")
            play_station(stations[idx], S)
            time.sleep(1); ipc.clear_progress()

    def stop_action():
        stop(S)
        ipc.write_progress("Webradio", "Gestoppt", color="orange"); time.sleep(1); ipc.clear_progress()

    return [
        Item("Station waehlen",
             sub=lambda: S.get("radio_station", "Keine") if S.get("radio_playing") else "Gestoppt",
             action=select_station),
        Item("Stop", action=stop_action),
    ]
